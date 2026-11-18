"""Tests for M2: Operational Tools and Tool-Enabled Single Agent."""
import pytest

from app.agents.single_agent import MaintenanceSingleAgent
from app.schemas.maintenance_event import EventSource, MaintenanceEvent, RiskLevel, SensorReadings
from app.tools.maintenance_tools import (
    calculate_downtime_cost,
    check_spare_parts_inventory,
    get_sensor_history,
    schedule_technician,
)


def test_sensor_history_valid_asset():
    """Test retrieving telemetry and limits for VPW-HYD-PRESS-02."""
    res = get_sensor_history("VPW-HYD-PRESS-02", hours=48)
    assert res.error is None
    assert res.asset_tag == "VPW-HYD-PRESS-02"
    assert res.asset_code == "HYD-PRESS"
    assert res.vibration_trip_mm_s == 8.5
    assert res.points_retrieved == 48
    assert len(res.recent_readings) == 48
    # Pressure should be present for HYD-PRESS
    assert res.recent_readings[0].pressure_bar is not None


def test_sensor_history_unknown_asset():
    """Test sensor history gracefully handles unknown asset without crashing."""
    res = get_sensor_history("VPW-UNKNOWN-MACHINE-99", hours=24)
    assert res.error is not None
    assert "not found" in res.error.lower()
    assert res.points_retrieved == 0


def test_downtime_cost_asset_specific_vs_default():
    """Test asset-specific downtime cost vs class default fallback."""
    # VPW-HYD-PRESS-02 is a Class A machine with 40,000 INR/hr
    res_asset = calculate_downtime_cost("VPW-HYD-PRESS-02", downtime_minutes=120)
    assert res_asset.rate_source == "asset_specific"
    assert res_asset.hourly_rate_inr >= 30000
    assert res_asset.total_cost_inr == res_asset.hourly_rate_inr * 2

    # Unknown asset should use Class B default rate (18,000 INR/hr)
    res_unknown = calculate_downtime_cost("UNKNOWN-TAG", downtime_minutes=60)
    assert res_unknown.rate_source == "class_default"
    assert res_unknown.hourly_rate_inr == 18000
    assert res_unknown.total_cost_inr == 18000


def test_spare_parts_inventory_lookup():
    """Test inventory lookup for valid and invalid parts."""
    # Load first part number from inventory table to ensure test integrity
    from app.tools.maintenance_tools import get_table_loader
    inventory = get_table_loader().load_table("inventory")
    assert len(inventory) == 280
    sample_part = inventory[0]["part_number"]

    res = check_spare_parts_inventory(sample_part)
    assert res.error is None
    assert res.part_number == sample_part
    assert res.unit_cost_inr > 0
    assert res.supplier_tier in ("T1", "T2", "T3")

    # Invalid part lookup
    res_invalid = check_spare_parts_inventory("VPW-INVALID-99999")
    assert res_invalid.error is not None
    assert "not found" in res_invalid.error.lower()


def test_technician_scheduling_calendar():
    """Test querying available technicians by skill and hours on 2026-08-01."""
    res = schedule_technician(
        required_skill="Mechanical",
        estimated_hours=4,
        date_str="2026-08-01",
        shift="A",
    )
    assert res.error is None
    assert res.count > 0
    # Every returned technician must have available_hours >= 4
    for slot in res.available_technicians:
        assert slot.available_hours >= 4
        assert slot.shift == "A"
        assert slot.primary_skill == "Mechanical" or slot.secondary_skill == "Mechanical"


def test_technician_scheduling_invalid_skill():
    """Test technician scheduling rejects invalid trade."""
    res = schedule_technician(required_skill="SoftwareEngineer", estimated_hours=2)
    assert res.error is not None
    assert "invalid skill" in res.error.lower()


def test_single_agent_tool_execution():
    """Test single agent executing a multi-step investigation using bounded tool selection."""
    class MockDecisionAdapter:
        def __init__(self):
            self.step = 0

        def generate_structured(self, messages, output_schema, **kwargs):
            self.step += 1
            if self.step == 1:
                return (
                    ToolCallDecision(
                        thought="Need to check sensor history for vibration and pressure readings.",
                        action="get_sensor_history",
                        action_input={"asset_tag": "VPW-HYD-PRESS-02", "hours": 24},
                    ),
                    LLMResponse(content="", model="mock", provider="mock"),
                )
            elif self.step == 2:
                return (
                    ToolCallDecision(
                        thought="Now calculate downtime cost for 90 minutes downtime.",
                        action="calculate_downtime_cost",
                        action_input={"asset_tag": "VPW-HYD-PRESS-02", "downtime_minutes": 90},
                    ),
                    LLMResponse(content="", model="mock", provider="mock"),
                )
            else:
                return (
                    ToolCallDecision(
                        thought="Information collected. Finishing investigation.",
                        action="finish",
                        action_input={},
                    ),
                    LLMResponse(content="", model="mock", provider="mock"),
                )

        def generate(self, messages, **kwargs):
            return LLMResponse(
                content="Investigation completed: VPW-HYD-PRESS-02 shows telemetry within normal band. Total downtime cost is Rs. 60,000.",
                model="mock",
                provider="mock",
            )

    from app.agents.single_agent import ToolCallDecision
    from app.adapters.llm_adapter import LLMResponse

    agent = MaintenanceSingleAgent(llm_adapter=MockDecisionAdapter())  # type: ignore
    result = agent.run(
        query="Check sensor history and calculate downtime for VPW-HYD-PRESS-02 for 90 minutes downtime."
    )
    assert result.steps_executed == 2
    assert len(result.tools_called) == 2
    assert result.stop_reason == "completed"
    assert "get_sensor_history" in result.findings
    assert "calculate_downtime_cost" in result.findings
    assert result.requires_human_approval is True  # Cost >= 30,000 INR triggers approval

