"""PlantGuard FastMCP Production Server for Milestone 6.

Exposes deterministic inventory, supplier, and downtime tools along with authoritative
policy resources via the Model Context Protocol (MCP).

CRITICAL ARCHITECTURAL RULE:
Logging is strictly directed to stderr (sys.stderr). Stdout is reserved exclusively
for JSON-RPC protocol framing to avoid transport corruption.
"""
from __future__ import annotations

import logging
import sys
from typing import Any, Dict

from mcp.server.mcpserver import MCPServer

from app.config.settings import get_settings
from app.tools.maintenance_tools import (
    calculate_downtime_cost as tool_calc_downtime,
    check_spare_parts_inventory as tool_check_inventory,
    TableDataLoader,
)

# ── Ensure Stderr-Only Logging ──
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("plantguard.mcp.server")

# ── Initialize MCP Server ──
mcp_server = MCPServer("plantguard-mcp")


# ── Tool 1: Spare Parts Inventory ──
@mcp_server.tool()
def check_spare_parts_inventory(part_number: str) -> Dict[str, Any]:
    """Check stock level, reorder point, unit cost, and supplier tier for a spare part."""
    logger.info(f"MCP Tool Call: check_spare_parts_inventory(part_number='{part_number}')")
    result = tool_check_inventory(part_number)
    return result.model_dump(mode="json")


# ── Tool 2: Supplier Info ──
@mcp_server.tool()
def get_supplier_info(supplier_id: str) -> Dict[str, Any]:
    """Retrieve vendor contact details, lead time, and reliability tier by supplier ID."""
    logger.info(f"MCP Tool Call: get_supplier_info(supplier_id='{supplier_id}')")
    loader = TableDataLoader()
    suppliers = loader.load_table("suppliers")
    query_id = supplier_id.strip().upper()
    for s in suppliers:
        s_id = str(s.get("supplier_id", "")).upper()
        if s_id == query_id or s_id.replace("VPW-", "") == query_id.replace("VPW-", ""):
            return {
                "supplier_id": s_id,
                "name": s.get("supplier_name") or s.get("name", "Unknown Supplier"),
                "tier": s.get("tier"),
                "city": s.get("city"),
                "lead_time_days": s.get("lead_time_days"),
                "status": "ACTIVE",
            }
    return {
        "supplier_id": supplier_id,
        "status": "NOT_FOUND",
        "error": f"Supplier {supplier_id} not registered in authorized vendor roster",
    }


# ── Tool 3: Downtime Cost Calculator ──
@mcp_server.tool()
def calculate_downtime_cost(asset_tag: str, downtime_minutes: int) -> Dict[str, Any]:
    """Calculate financial impact of equipment downtime using asset-specific hourly rate."""
    logger.info(f"MCP Tool Call: calculate_downtime_cost(asset='{asset_tag}', min={downtime_minutes})")
    result = tool_calc_downtime(asset_tag, downtime_minutes)
    return result.model_dump(mode="json")


# ── Resource: Procurement Approval Matrix ──
@mcp_server.resource("plantguard://policies/procurement_approval_matrix")
def get_procurement_approval_matrix() -> str:
    """Authoritative procurement authorization tiers and approval limits."""
    logger.info("MCP Resource Read: plantguard://policies/procurement_approval_matrix")
    settings = get_settings()
    return f"""# PlantGuard Authoritative Procurement Approval Matrix
Reference: Corporate Financial Authority Standard Cl-4.2
Last Updated: 2026-08-01

| Tier | Total PO Amount (INR) | Required Approval Authority | Workflow Routing |
|------|-----------------------|-----------------------------|------------------|
| 1    | <= {settings.PROCUREMENT_AUTO_MAX_INR:,} | Automated / System | `auto` |
| 2    | {settings.PROCUREMENT_AUTO_MAX_INR + 1:,} to {settings.PROCUREMENT_MANAGER_MAX_INR:,} | Maintenance Manager | `maintenance_manager` |
| 3    | > {settings.PROCUREMENT_MANAGER_MAX_INR:,} | Plant Head | `plant_head` |

Rules:
1. Under no circumstances may an automated agent issue a PO exceeding {settings.PROCUREMENT_AUTO_MAX_INR:,} INR without human sign-off.
2. Emergency POs must be confirmed in writing within 24 hours of issuance.
"""


# ── Level 4 Prompt 1: LOTO Safety Briefing ──
@mcp_server.prompt("loto_briefing")
def loto_briefing_prompt(asset_tag: str) -> str:
    """Standardized safety briefing prompt for LOTO isolation of industrial machinery."""
    return f"Provide the mandatory zero-energy verification steps, lock placement locations, and electrical isolation breakers for {asset_tag} under PlantGuard SOP-LOTO-01."


def handle_jsonrpc_request(req_data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute JSON-RPC 2.0 requests across MCP transport boundary."""
    method = req_data.get("method")
    req_id = req_data.get("id", 1)
    params = req_data.get("params", {})

    if method == "prompts/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "prompts": [
                    {
                        "name": "loto_briefing",
                        "description": "Standardized safety briefing prompt for LOTO isolation of industrial machinery.",
                        "arguments": [{"name": "asset_tag", "description": "Target equipment asset identifier", "required": True}],
                    }
                ]
            },
        }

    if method == "prompts/get":
        name = params.get("name")
        args = params.get("arguments", {})
        if name == "loto_briefing":
            tag = args.get("asset_tag", "VPW-GEN-01")
            text = loto_briefing_prompt(tag)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "description": "LOTO Safety Briefing",
                    "messages": [{"role": "user", "content": {"type": "text", "text": text}}],
                },
            }
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": f"Prompt not found: {name}"}}

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "check_spare_parts_inventory",
                        "description": "Check stock level, reorder point, unit cost, and supplier tier for a spare part.",
                        "inputSchema": {"type": "object", "properties": {"part_number": {"type": "string"}}, "required": ["part_number"]},
                    },
                    {
                        "name": "get_supplier_info",
                        "description": "Retrieve vendor contact details, lead time, and reliability tier by supplier ID.",
                        "inputSchema": {"type": "object", "properties": {"supplier_id": {"type": "string"}}, "required": ["supplier_id"]},
                    },
                    {
                        "name": "calculate_downtime_cost",
                        "description": "Calculate financial impact of equipment downtime using asset-specific hourly rate.",
                        "inputSchema": {"type": "object", "properties": {"asset_tag": {"type": "string"}, "downtime_minutes": {"type": "integer"}}, "required": ["asset_tag"]},
                    },
                ]
            },
        }

    if method == "resources/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "resources": [
                    {
                        "uri": "plantguard://policies/procurement_approval_matrix",
                        "name": "Procurement Approval Matrix",
                        "mimeType": "text/markdown",
                    }
                ]
            },
        }

    if method == "resources/read":
        uri = params.get("uri")
        if uri == "plantguard://policies/procurement_approval_matrix":
            content = get_procurement_approval_matrix()
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": content}]},
            }
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": f"Resource not found: {uri}"}}

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        if name == "check_spare_parts_inventory":
            res = check_spare_parts_inventory(args.get("part_number", ""))
        elif name == "get_supplier_info":
            res = get_supplier_info(args.get("supplier_id", ""))
        elif name == "calculate_downtime_cost":
            res = calculate_downtime_cost(args.get("asset_tag", ""), int(args.get("downtime_minutes", 60)))
        else:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method/Tool {name} not found"}}

        return {"jsonrpc": "2.0", "id": req_id, "result": res}

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}


def main():
    """Run the MCP server over stdio or JSON-RPC transport."""
    import argparse
    import json
    parser = argparse.ArgumentParser(description="PlantGuard FastMCP Server")
    parser.add_argument("--jsonrpc", type=str, help="Single JSON-RPC request to execute and return output to stdout")
    parser.add_argument("--stdio", action="store_true", help="Run standard stdio loop")
    args = parser.parse_args()

    if args.jsonrpc:
        try:
            req_data = json.loads(args.jsonrpc)
            resp = handle_jsonrpc_request(req_data)
            print(json.dumps(resp))
            sys.exit(0)
        except Exception as e:
            err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(e)}}
            print(json.dumps(err_resp))
            sys.exit(1)

    logger.info("Starting PlantGuard MCP Server over stdio...")
    mcp_server.run()


if __name__ == "__main__":
    main()
