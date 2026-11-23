"""PlantGuard MCP server implemented with the official SDK stdio transport."""
from __future__ import annotations

import logging
import sys
from typing import Any, Dict

from mcp.server.mcpserver import MCPServer

from app.config.settings import get_settings
from app.tools.maintenance_tools import (
    TableDataLoader,
    calculate_downtime_cost as tool_calculate_downtime_cost,
    check_spare_parts_inventory as tool_check_spare_parts_inventory,
)

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("plantguard.mcp.server")
mcp_server = MCPServer("plantguard-mcp")


@mcp_server.tool()
def check_spare_parts_inventory(part_number: str) -> Dict[str, Any]:
    """Return stock, reorder point, unit cost, and supplier details for a part number."""
    if not part_number.strip():
        raise ValueError("part_number must not be empty")
    logger.info("MCP tool: check_spare_parts_inventory")
    return tool_check_spare_parts_inventory(part_number).model_dump(mode="json")


@mcp_server.tool()
def get_supplier_info(supplier_id: str) -> Dict[str, Any]:
    """Return a registered supplier's contact, lead-time, and reliability details."""
    if not supplier_id.strip():
        raise ValueError("supplier_id must not be empty")
    logger.info("MCP tool: get_supplier_info")
    loader = TableDataLoader()
    suppliers = loader.load_table("suppliers")
    query_id = supplier_id.strip().upper()
    for row in suppliers:
        row_id = str(row.get("supplier_id", "")).upper()
        if row_id == query_id or row_id.removeprefix("VPW-") == query_id.removeprefix("VPW-"):
            return {
                "supplier_id": row_id,
                "name": row.get("supplier_name") or row.get("name", "Unknown Supplier"),
                "tier": row.get("tier"),
                "city": row.get("city"),
                "lead_time_days": row.get("lead_time_days"),
                "status": "ACTIVE",
            }
    return {"supplier_id": query_id, "status": "NOT_FOUND", "error": "Supplier is not registered"}


@mcp_server.tool()
def calculate_downtime_cost(asset_tag: str, downtime_minutes: int) -> Dict[str, Any]:
    """Calculate downtime impact using the configured asset-specific hourly rate."""
    if not asset_tag.strip():
        raise ValueError("asset_tag must not be empty")
    if downtime_minutes < 0:
        raise ValueError("downtime_minutes must be non-negative")
    logger.info("MCP tool: calculate_downtime_cost")
    return tool_calculate_downtime_cost(asset_tag, downtime_minutes).model_dump(mode="json")


@mcp_server.resource("plantguard://policies/procurement_approval_matrix")
def get_procurement_approval_matrix() -> str:
    """Read authoritative purchase-order approval thresholds."""
    settings = get_settings()
    return f"""# PlantGuard Authoritative Procurement Approval Matrix

| Total PO amount (INR) | Approver |
|---|---|
| <= {settings.PROCUREMENT_AUTO_MAX_INR:,} | Automated system |
| {settings.PROCUREMENT_AUTO_MAX_INR + 1:,} to {settings.PROCUREMENT_MANAGER_MAX_INR:,} | Maintenance Manager |
| > {settings.PROCUREMENT_MANAGER_MAX_INR:,} | Plant Head |

Safety-critical work still requires human approval regardless of purchase amount.
Authority: Corporate Financial Authority Standard Cl-4.2.
"""


@mcp_server.prompt("loto_briefing")
def loto_briefing_prompt(asset_tag: str) -> str:
    """Prepare a LOTO briefing request for the specified asset."""
    if not asset_tag.strip():
        raise ValueError("asset_tag must not be empty")
    return (
        f"Retrieve the authorized LOTO procedure for {asset_tag}. List only verified isolation, "
        "lock placement, and zero-energy verification steps from SOP-LOTO-01, with source citations."
    )


def main() -> None:
    """Run the SDK-managed MCP JSON-RPC stdio transport."""
    mcp_server.run(transport="stdio")


if __name__ == "__main__":
    main()
