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
from app.tools.maintenance_tools import check_spare_parts_inventory

logger = logging.getLogger(__name__)


class ProcurementAgent:
    """Specialized Procurement Agent."""

    def __init__(self):
        self.settings = get_settings()

    def evaluate_purchase_order(
        self,
        part_number: str,
        quantity: int,
    ) -> Dict[str, Any]:
        """Evaluate purchase order against inventory and determine required approval authority."""
        part = check_spare_parts_inventory(part_number)
        unit_cost = part.unit_cost_inr
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
            "description": part.description,
            "quantity": quantity,
            "unit_cost_inr": unit_cost,
            "total_cost_inr": total_cost,
            "supplier_id": part.supplier_id,
            "supplier_tier": part.supplier_tier,
            "current_stock_on_hand": part.on_hand,
            "reorder_point": part.reorder_point,
            "approval_tier": approval_tier,
            "requires_human_approval": requires_human_approval,
            "approver_role": approver_role,
        }
