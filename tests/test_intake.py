"""Tests for M1: Structured Intake and MaintenanceEvent schema."""
import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.maintenance_event import (
    EventSource,
    MaintenanceEvent,
    Priority,
    RiskLevel,
    SensorReadings,
    UncertaintyLevel,
)


def test_valid_maintenance_event_creation():
    """Test standard valid maintenance event parsing."""
    event = MaintenanceEvent(
        event_id="EVT-2026-0001",
        source=EventSource.SENSOR_ALERT,
        received_at=datetime.fromisoformat("2026-08-01T10:15:00"),
        raw_text="Vibration high alarm on drive end bearing, Tag: VPW-HYD-PRESS-02, RMS: 8.9 mm/s",
        asset_code="HYD-PRESS",
        asset_tag="VPW-HYD-PRESS-02",
        readings=SensorReadings(
            vibration_mm_s=8.9,
            temp_c=78.5,
            pressure_bar=195.0,
            current_a=45.2,
        ),
        severity=RiskLevel.HIGH,
        safety_critical=True,
    )
    assert event.event_id == "EVT-2026-0001"
    assert event.asset_tag == "VPW-HYD-PRESS-02"
    assert event.readings.vibration_mm_s == 8.9
    assert event.safety_critical is True
    assert event.requires_human_approval is True
    assert event.data_quality.has_impossible_readings is False


def test_cross_field_validation_impossible_readings():
    """Test adversarial probe P3: extreme vibration (912 mm/s) and temp (-40 C)."""
    event = MaintenanceEvent(
        event_id="EVT-ADV-001",
        source=EventSource.SENSOR_ALERT,
        received_at=datetime.fromisoformat("2026-08-01T12:00:00"),
        raw_text="Abnormal reading: Vibration 912 mm/s, Temp -40 C",
        asset_code="PUMP-CENT",
        asset_tag="VPW-PUMP-CENT-01",
        readings=SensorReadings(
            vibration_mm_s=912.0,
            temp_c=-40.0,
        ),
    )
    assert event.data_quality.has_impossible_readings is True
    assert event.uncertainty == UncertaintyLevel.INVALID
    assert len(event.data_quality.plausibility_issues) >= 2


def test_missing_asset_identifier():
    """Test record with missing asset tag and code."""
    event = MaintenanceEvent(
        event_id="EVT-MISSING-001",
        source=EventSource.OPERATOR_LOG,
        received_at=datetime.fromisoformat("2026-08-01T14:30:00"),
        raw_text="Motor seems warm and making humming noise on line 2",
    )
    assert event.data_quality.has_missing_required_fields is True
    assert "asset_identifier" in event.data_quality.missing_fields


def test_negative_vibration_validation_error():
    """Test that negative vibration raises validation error."""
    with pytest.raises(ValidationError):
        SensorReadings(vibration_mm_s=-2.5)


def test_intake_from_generated_dataset():
    """Validate loading records directly from data/plantguard/intake/records.jsonl."""
    records_file = Path(__file__).resolve().parent.parent / "data" / "plantguard" / "intake" / "records.jsonl"
    assert records_file.exists(), "intake records.jsonl must exist"

    loaded_events = []
    with open(records_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            # Map dataset schema to MaintenanceEvent
            readings_raw = data.get("readings") or {}
            evt = MaintenanceEvent(
                event_id=data.get("record_id") or data.get("event_id"),
                source=EventSource.OPERATOR_LOG if "shift" in data.get("raw_text", "").lower() else EventSource.SENSOR_ALERT,
                received_at=datetime.fromisoformat(data["received_at"]),
                raw_text=data["raw_text"],
                asset_code=data.get("asset_code"),
                asset_tag=data.get("asset_tag"),
                readings=SensorReadings(
                    vibration_mm_s=readings_raw.get("vibration_mm_s"),
                    temp_c=readings_raw.get("temp_c"),
                    pressure_bar=readings_raw.get("pressure_bar"),
                    current_a=readings_raw.get("current_a"),
                ),
                ground_truth=data.get("ground_truth"),
            )
            loaded_events.append(evt)

    assert len(loaded_events) == 200
    # Verify that some events properly detect missing fields
    events_with_missing = [e for e in loaded_events if e.data_quality.has_missing_required_fields]
    assert len(events_with_missing) > 0, "Intake dataset must include edge cases with missing fields"
