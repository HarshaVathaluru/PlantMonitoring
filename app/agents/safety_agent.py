"""PlantGuard Safety Agent for Milestone 6.

Specialized agent responsible for enforcing safety policies, Lockout/Tagout (LOTO)
standards, and Permit to Work (PTW) requirements. Enforces hard safety blocks.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.schemas.maintenance_event import ApprovalRequiredReason

logger = logging.getLogger(__name__)


class SafetyAgent:
    """Specialized Safety Gatekeeper Agent."""

    def evaluate_task_safety(
        self,
        task_description: str,
        asset_code: str,
        is_energy_isolation_involved: bool = False,
        is_hot_work_or_confined_space: bool = False,
        override_requested: bool = False,
    ) -> Dict[str, Any]:
        """
        Evaluate safety constraints for a proposed maintenance task.
        Guarantees that production pressure cannot bypass safety sign-offs.
        """
        blocking_reasons: List[str] = []
        requires_human_approval = False

        if is_energy_isolation_involved:
            requires_human_approval = True
            blocking_reasons.append(ApprovalRequiredReason.ENERGY_ISOLATION_REQUIRED.value)

        if is_hot_work_or_confined_space:
            requires_human_approval = True
            blocking_reasons.append(ApprovalRequiredReason.SAFETY_CRITICAL_PERMIT_REQUIRED.value)

        bypass_attempted = False
        desc_lower = task_description.lower()
        if override_requested or any(phrase in desc_lower for phrase in ["skip paperwork", "skip permit", "start now", "bypass loto", "suppress alarm"]):
            bypass_attempted = True
            requires_human_approval = True
            blocking_reasons.append("UNAUTHORIZED_SAFETY_BYPASS_ATTEMPT")

        status = "REQUIRES_AUTHORIZATION" if requires_human_approval else "SAFETY_CLEARED"

        return {
            "asset_code": asset_code,
            "status": status,
            "requires_human_approval": requires_human_approval,
            "bypass_attempted": bypass_attempted,
            "blocking_reasons": blocking_reasons,
            "mandated_standards": [
                "Lockout/Tagout and Energy Isolation Standard",
                "Permit to Work and Safety-Critical Task Standard",
            ] if requires_human_approval else [],
        }
