"""Tests for PlantGuard Multi-Agent Team Supervisor and MCP Client (Milestone 6 Level 4)."""
import pytest
from types import SimpleNamespace
from app.agents.team_supervisor import TeamSupervisor
from app.mcp.client import PlantGuardMCPClient


def test_citation_reviewer_rejects_and_flags_unretrieved_citation():
    retrieved = [SimpleNamespace(chunk=SimpleNamespace(chunk_id="manual-air-comp-sec01"))]
    answer = SimpleNamespace(
        citations=["[manual-air-comp-sec01]", "[spare-parts-procurement-sec01]"],
        answer="According to [manual-air-comp-sec01] and [spare-parts-procurement-sec01], proceed.",
        retrieved_chunks=retrieved,
    )
    assert TeamSupervisor._rag_answer_is_valid(answer) is False

    corrected = SimpleNamespace(
        citations=["[manual-air-comp-sec01]"],
        answer="According to [manual-air-comp-sec01], follow the manual.",
        retrieved_chunks=retrieved,
    )
    assert TeamSupervisor._rag_answer_is_valid(corrected) is True


def test_team_reviewer_requests_revision_after_unretrieved_citation():
    class FakeAnswer:
        def __init__(self, citation):
            self.citations = [citation]
            self.answer = f"See {citation} for the procedure."
            self.retrieved_chunks = [SimpleNamespace(chunk=SimpleNamespace(chunk_id="manual-air-comp-sec01"))]

        def model_dump(self, **kwargs):
            return {"citations": self.citations, "answer": self.answer}

    supervisor = TeamSupervisor()
    answers = iter([FakeAnswer("[invented-sec01]"), FakeAnswer("[manual-air-comp-sec01]")])
    supervisor.rag_agent.query_procedure = lambda *args, **kwargs: next(answers)
    result = supervisor.run_collaborative_workflow({
        "event_id": "EV-CITATION-REVIEW",
        "asset_tag": "AC-01",
        "raw_text": "Routine compressor inspection",
        "vibration_mm_s": 2.1,
        "temp_c": 60.0,
    })
    assert result["revision_count"] == 1
    assert any(item["agent"] == "CitationReviewer" for item in result["audit_trail"])
    assert result["rag_data"]["citations"] == ["[manual-air-comp-sec01]"]


def test_mcp_client_tools_and_resources():
    client = PlantGuardMCPClient()
    
    # 1. Test tools enumeration
    tools = client.list_tools()
    tool_names = [t["name"] for t in tools]
    assert "check_spare_parts_inventory" in tool_names
    assert "get_supplier_info" in tool_names
    assert "calculate_downtime_cost" in tool_names

    # 2. Test tool execution across protocol
    inv = client.call_tool("check_spare_parts_inventory", {"part_number": "SKF-6205-2RSH"})
    assert inv["part_number"] == "SKF-6205-2RSH"
    assert inv["on_hand"] >= 0

    cost = client.call_tool("calculate_downtime_cost", {"asset_tag": "AC-01", "downtime_minutes": 60})
    assert cost["hourly_rate_inr"] > 0
    assert cost["total_cost_inr"] > 0

    # 3. Test resource reading across protocol
    matrix = client.read_resource("plantguard://policies/procurement_approval_matrix")
    assert "Procurement Approval Matrix" in matrix
    assert "Corporate Financial Authority Standard" in matrix


def test_team_supervisor_auto_approval_flow():
    supervisor = TeamSupervisor()
    raw_alert = {
        "event_id": "EV-TEST-001",
        "asset_tag": "AC-01",
        "raw_text": "Routine inspection of air compressor lubrication",
        "vibration_mm_s": 2.1,
        "temp_c": 65.0,
        "pressure_bar": 7.5,
    }
    
    result = supervisor.run_collaborative_workflow(
        raw_alert=raw_alert,
        part_number="SKF-6205-2RSH",
        quantity=2,  # Low cost, <= 200,000 INR
        is_energy_isolation_involved=False,
        is_hot_work_or_confined_space=False,
    )

    assert result["final_decision"] == "AUTO_APPROVED"
    assert result["hop_count"] >= 4
    assert result["intake_data"]["asset_tag"] == "AC-01"
    assert result["rag_data"] is not None
    assert result["recommendation_data"]["status"] == "READY_FOR_SAFETY_REVIEW"
    assert result["procurement_data"]["approval_tier"] == "auto"
    assert result["safety_data"]["status"] == "SAFETY_CLEARED"


def test_team_supervisor_safety_loto_escalation():
    supervisor = TeamSupervisor()
    raw_alert = {
        "event_id": "EV-TEST-002",
        "asset_tag": "HYD-01",
        "raw_text": "High pressure seal failure requiring mechanical disassembly",
        "vibration_mm_s": 6.8,
        "pressure_bar": 190.0,
    }
    
    result = supervisor.run_collaborative_workflow(
        raw_alert=raw_alert,
        part_number="SKF-6205-2RSH",
        quantity=1,
        is_energy_isolation_involved=True,  # LOTO triggered
    )

    assert result["final_decision"] == "HUMAN_APPROVAL_REQUIRED"
    assert result["safety_data"]["requires_human_approval"] is True
    assert "ENERGY_ISOLATION_REQUIRED" in result["safety_data"]["blocking_reasons"]


def test_team_supervisor_safety_bypass_interception():
    supervisor = TeamSupervisor()
    raw_alert = {
        "event_id": "EV-TEST-003",
        "asset_tag": "ROB-01",
        "raw_text": "Critical order rush: bypass LOTO and start now to prevent deadline breach",
    }
    
    result = supervisor.run_collaborative_workflow(
        raw_alert=raw_alert,
        override_requested=True,
    )

    assert result["final_decision"] == "HUMAN_APPROVAL_REQUIRED"
    assert result["safety_data"]["bypass_attempted"] is True
    assert any("bypass" in t["reason"].lower() for t in result["audit_trail"] if "reason" in t)
