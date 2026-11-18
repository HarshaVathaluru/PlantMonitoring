"""Tests for Milestone 8: FastAPI Endpoints & Probe P5 Ingestion Validation."""
import pytest
from pydantic import ValidationError
from app.main import (
    IntakeRequest,
    health_check,
    ingest_telemetry_alert,
    investigate_technical_query,
    render_dashboard,
    InvestigateRequest,
)


def test_api_health_endpoint():
    data = health_check()
    assert data["status"] == "HEALTHY"
    assert data["reference_date"] == "2026-08-01"
    assert "service" in data


def test_api_valid_intake():
    req = IntakeRequest(
        asset_tag="VPW-AIR-COMP-01",
        vibration_mm_s=2.8,
        temp_c=58.0,
        severity="low",
        message="Routine morning telemetry check",
    )
    res = ingest_telemetry_alert(req)
    assert res["asset_tag"] == "VPW-AIR-COMP-01"
    assert res["severity"] == "low"
    assert res["plausibility"]["is_plausible"] is True


def test_probe_p5_malformed_api_ingestion_validation():
    """Probe P5: Incomplete or invalid schema payload fails Pydantic schema validation."""
    # Missing vibration_mm_s and temp_c, asset_tag too short
    with pytest.raises(ValidationError) as exc_info:
        IntakeRequest(asset_tag="X")  # type: ignore

    errors = exc_info.value.errors()
    field_names = [e["loc"][0] for e in errors]
    assert "vibration_mm_s" in field_names
    assert "temp_c" in field_names
    assert "asset_tag" in field_names  # string too short


def test_api_investigate_undocumented_topic_refusal():
    req = InvestigateRequest(query="What is the purge cycle for the ammonia refrigeration unit?")
    res = investigate_technical_query(req)
    assert res["is_supported"] is False
    assert res["confidence"] == "refusal"
    assert "cannot verify" in res["answer"].lower()


def test_api_dashboard_endpoint():
    html_res = render_dashboard()
    assert isinstance(html_res, str)
    assert "PlantGuard Operations Copilot" in html_res
    assert "SYSTEM READY (LEVEL 4)" in html_res


def test_api_team_collaborate_endpoint():
    """Level 4: Test API endpoint exercising multi-agent TeamSupervisor over MCP."""
    from app.main import TeamCollaborateRequest, run_multi_agent_team
    req = TeamCollaborateRequest(
        asset_tag="AC-01",
        part_number="SKF-6205-2RSH",
        quantity=1,
        vibration_mm_s=2.5,
        temp_c=62.0,
    )
    res = run_multi_agent_team(req)
    assert res["hop_count"] >= 4
    assert res["intake_data"] is not None
    assert res["rag_data"] is not None
    assert res["recommendation_data"] is not None
    assert res["procurement_data"] is not None
    assert res["safety_data"] is not None
    assert res["final_decision"] in ["AUTO_APPROVED", "HUMAN_APPROVAL_REQUIRED"]
