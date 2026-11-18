"""PlantGuard Intake Agent for Milestone 6.

Specialized agent responsible for parsing raw alerts and operator logs into validated
MaintenanceEvent instances with physical plausibility and data quality checks.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.adapters.llm_adapter import LLMAdapter
from app.schemas.maintenance_event import (
    EventSource,
    MaintenanceEvent,
    RiskLevel,
    SensorReadings,
)

logger = logging.getLogger(__name__)


class IntakeAgent:
    """Specialized Intake Agent."""

    def __init__(self, adapter: Optional[LLMAdapter] = None):
        self.adapter = adapter or LLMAdapter()

    def process_raw_alert(self, raw_input: Dict[str, Any]) -> MaintenanceEvent:
        """Parse and validate raw alert payload into a structured MaintenanceEvent."""
        asset_tag = raw_input.get("asset_identifier") or raw_input.get("asset_tag") or "UNKNOWN"
        event_id = raw_input.get("event_id") or f"EV-INTAKE-{int(datetime.now().timestamp())}"
        
        # Parse readings
        readings = SensorReadings(
            vibration_mm_s=raw_input.get("vibration_mm_s") if raw_input.get("vibration_mm_s") is not None else raw_input.get("vibration"),
            temp_c=raw_input.get("temp_c") if raw_input.get("temp_c") is not None else raw_input.get("temp") or raw_input.get("temperature"),
            pressure_bar=raw_input.get("pressure_bar") if raw_input.get("pressure_bar") is not None else raw_input.get("pressure"),
            current_a=raw_input.get("current_a") if raw_input.get("current_a") is not None else raw_input.get("current_amps"),
        )
        
        sev_str = str(raw_input.get("severity", "medium")).lower()
        try:
            severity = RiskLevel(sev_str)
        except ValueError:
            severity = RiskLevel.MEDIUM

        raw_text = raw_input.get("raw_text") or raw_input.get("message") or f"Telemetry alert for asset {asset_tag}"

        event = MaintenanceEvent(
            event_id=event_id,
            source=EventSource.SENSOR_ALERT if "sensor" in raw_text.lower() else EventSource.OPERATOR_LOG,
            received_at=datetime.now(timezone.utc),
            raw_text=raw_text,
            asset_tag=asset_tag,
            readings=readings,
            severity=severity,
            requires_permit=raw_input.get("requires_permit", False),
            requires_human_approval=raw_input.get("requires_human_approval", False),
        )
        return event
