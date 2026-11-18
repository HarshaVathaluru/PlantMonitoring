"""PlantGuard Recommendation Agent for Milestone 6.

Specialized agent responsible for calculating downtime costs, checking spare parts inventory,
and scheduling appropriate certified technicians.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.tools.maintenance_tools import (
    calculate_downtime_cost,
    check_spare_parts_inventory,
    schedule_technician,
)

logger = logging.getLogger(__name__)


class RecommendationAgent:
    """Specialized Recommendation Agent."""

    def generate_recommendation(
        self,
        asset_tag: str,
        fault_type: str,
        part_number: Optional[str] = None,
        estimated_downtime_minutes: int = 120,
        skill_required: str = "mechanical",
        estimated_hours: int = 4,
        date_str: str = "2026-08-01",
        shift: str = "A",
    ) -> Dict[str, Any]:
        """Synthesize cost, inventory, and technician scheduling into a recommendation."""
        cost_info = calculate_downtime_cost(asset_tag, estimated_downtime_minutes)
        part_info = check_spare_parts_inventory(part_number) if part_number else None
        tech_sched = schedule_technician(
            required_skill=skill_required,
            estimated_hours=estimated_hours,
            date_str=date_str,
            shift=shift,
        )

        return {
            "asset_tag": asset_tag,
            "fault_type": fault_type,
            "estimated_downtime_minutes": estimated_downtime_minutes,
            "downtime_cost_inr": cost_info.total_cost_inr,
            "criticality": cost_info.criticality,
            "spare_part": part_info.model_dump(mode="json") if part_info else None,
            "technician_assignment": {
                "assigned_count": tech_sched.count,
                "recommended_technician": tech_sched.available_technicians[0].name if tech_sched.available_technicians else None,
            },
            "status": "READY_FOR_SAFETY_REVIEW",
        }
