"""PlantGuard Procurement Agent for Milestone 6.

Specialized agent responsible for stock level checks, supplier evaluations,
and enforcing authoritative procurement approval thresholds:
- <= 200,000 INR: Auto approval
- 200,001 - 1,000,000 INR: Maintenance Manager approval
- > 1,000,000 INR: Plant Head approval
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.config.settings import get_settings
from app.mcp.client import PlantGuardMCPClient

logger = logging.getLogger(__name__)


class ProcurementAgent:
    """Specialized Procurement Agent executing via MCP transport boundary."""

    def __init__(self, mcp_client: Optional[PlantGuardMCPClient] = None):
        self.settings = get_settings()
        self.mcp_client = mcp_client

    def evaluate_purchase_order(
        self,
        part_number: str,
        quantity: int,
    ) -> Dict[str, Any]:
        """Evaluate purchase order against inventory and determine required approval authority."""
        if self.mcp_client is not None:
            # Query inventory tool via MCP transport
            part = self.mcp_client.call_tool("check_spare_parts_inventory", {"part_number": part_number})
            unit_cost = float(part.get("unit_cost_inr", 0.0))
            description = part.get("description", "")
            supplier_id = part.get("supplier_id")
            supplier_tier = part.get("supplier_tier")
            on_hand = part.get("on_hand", 0)
            reorder_point = part.get("reorder_point", 0)

            # Query supplier tool via MCP transport
            supplier_info = None
            if supplier_id:
                supplier_info = self.mcp_client.call_tool("get_supplier_info", {"supplier_id": supplier_id})

            # Read authoritative MCP policy resource
            matrix_doc = self.mcp_client.read_resource("plantguard://policies/procurement_approval_matrix")
        else:
            from app.tools.maintenance_tools import check_spare_parts_inventory
            part_obj = check_spare_parts_inventory(part_number)
            unit_cost = part_obj.unit_cost_inr
            description = part_obj.description
            supplier_id = part_obj.supplier_id
            supplier_tier = part_obj.supplier_tier
            on_hand = part_obj.on_hand
            reorder_point = part_obj.reorder_point
            supplier_info = None
            matrix_doc = None

        total_cost = unit_cost * quantity

        # Determine authorization level strictly from settings
        if total_cost <= self.settings.PROCUREMENT_AUTO_MAX_INR:
            approval_tier = "auto"
            requires_human_approval = False
            approver_role = "system_auto"
        elif total_cost <= self.settings.PROCUREMENT_MANAGER_MAX_INR:
            approval_tier = "maintenance_manager"
            requires_human_approval = True
            approver_role = "maintenance_manager"
        else:
            approval_tier = "plant_head"
            requires_human_approval = True
            approver_role = "plant_head"

        return {
            "part_number": part_number,
            "description": description,
            "quantity": quantity,
            "unit_cost_inr": unit_cost,
            "total_cost_inr": total_cost,
            "supplier_id": supplier_id,
            "supplier_tier": supplier_tier,
            "supplier_details": supplier_info,
            "current_stock_on_hand": on_hand,
            "reorder_point": reorder_point,
            "approval_tier": approval_tier,
            "requires_human_approval": requires_human_approval,
            "approver_role": approver_role,
            "matrix_verified": bool(matrix_doc),
            "status": "EVALUATED",
        }
