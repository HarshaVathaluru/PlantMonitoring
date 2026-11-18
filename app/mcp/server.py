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


def main():
    """Run the MCP server over stdio transport."""
    logger.info("Starting PlantGuard MCP Server over stdio...")
    mcp_server.run()


if __name__ == "__main__":
    main()
