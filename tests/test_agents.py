"""Tests for Milestone 6: Specialized Multi-Agent System."""
import pytest
from app.agents.intake_agent import IntakeAgent
from app.agents.rag_agent import RAGAgent
from app.agents.recommendation_agent import RecommendationAgent
from app.agents.procurement_agent import ProcurementAgent
from app.agents.safety_agent import SafetyAgent
from app.rag.engine import HybridRAGEngine
from app.adapters.llm_adapter import LLMAdapter, LLMResponse


class MockRAGAdapter(LLMAdapter):
    def generate(self, messages, temperature=None, max_tokens=None, **kwargs) -> LLMResponse:
        user_msg = messages[-1]["content"] if messages else ""
        if "ammonia" in user_msg.lower():
            return LLMResponse(
                content="I cannot verify this specification from the provided documents.",
                model="mock",
                provider="mock",
                total_tokens=100,
            )
        return LLMResponse(
            content="According to [manual-air-comp-sec01], inspect oil filter every 500 operating hours.",
            model="mock",
            provider="mock",
            total_tokens=120,
        )


def test_intake_agent_valid_and_invalid():
    agent = IntakeAgent()
    # Valid
    event = agent.process_raw_alert({
        "asset_tag": "VPW-AIR-COMP-01",
        "vibration_mm_s": 3.2,
        "temp_c": 62.0,
        "severity": "LOW",
    })
    assert event.asset_tag == "VPW-AIR-COMP-01"
    assert event.data_quality.has_impossible_readings is False

    # Physically impossible
    bad_event = agent.process_raw_alert({
        "asset_tag": "VPW-AIR-COMP-01",
        "vibration_mm_s": 912.0,
        "temp_c": -40.0,
        "severity": "CRITICAL",
    })
    assert bad_event.data_quality.has_impossible_readings is True
    assert len(bad_event.data_quality.plausibility_issues) > 0


def test_rag_agent_citations_and_refusal():
    rag = HybridRAGEngine(llm_adapter=MockRAGAdapter())
    agent = RAGAgent(rag_engine=rag)

    # Grounded query
    ans = agent.query_procedure("air compressor maintenance interval", asset_code="AIR-COMP")
    assert ans.is_supported is True
    assert len(ans.citations) > 0

    # Refusal on undocumented topic
    ref = agent.query_procedure("ammonia cycle purge time")
    assert ref.is_supported is False
    assert ref.confidence == "refusal"


def test_recommendation_agent():
    agent = RecommendationAgent()
    rec = agent.generate_recommendation(
        asset_tag="VPW-HYD-PRESS-02",
        fault_type="bearing_wear",
        part_number="SKF-6205-2RSH",
        estimated_downtime_minutes=120,
    )
    assert rec["asset_tag"] == "VPW-HYD-PRESS-02"
    # Hyd press 2 hourly rate is 40,000 INR -> 2 hours = 80,000 INR
    assert rec["downtime_cost_inr"] == 80000
    assert rec["criticality"] == "A"
    assert rec["spare_part"] is not None
    assert rec["spare_part"]["part_number"] == "SKF-6205-2RSH"


def test_procurement_agent_tiers():
    agent = ProcurementAgent()

    # Tier 1: Small order <= 200,000 INR -> auto
    # Unit cost of VPW-P-00000 is 1,200 INR. 10 units = 12,000 INR
    po_small = agent.evaluate_purchase_order("VPW-P-00000", quantity=10)
    assert po_small["approval_tier"] == "auto"
    assert po_small["requires_human_approval"] is False

    # Tier 2: Medium order 200,001 - 1,000,000 INR -> maintenance_manager
    # 200 units = 240,000 INR
    po_medium = agent.evaluate_purchase_order("VPW-P-00000", quantity=200)
    assert po_medium["approval_tier"] == "maintenance_manager"
    assert po_medium["requires_human_approval"] is True
    assert po_medium["approver_role"] == "maintenance_manager"

    # Tier 3: Large order > 1,000,000 INR -> plant_head
    # 1000 units = 1,200,000 INR
    po_large = agent.evaluate_purchase_order("VPW-P-00000", quantity=1000)
    assert po_large["approval_tier"] == "plant_head"
    assert po_large["requires_human_approval"] is True
    assert po_large["approver_role"] == "plant_head"


def test_safety_agent_blocks_bypass():
    agent = SafetyAgent()

    # Routine task
    cleared = agent.evaluate_task_safety(
        task_description="Visual inspection of belt alignment",
        asset_code="CONV-BELT",
        is_energy_isolation_involved=False,
    )
    assert cleared["status"] == "SAFETY_CLEARED"
    assert cleared["requires_human_approval"] is False

    # Safety-critical task with LOTO
    loto_task = agent.evaluate_task_safety(
        task_description="Replace main hydraulic cylinder seal",
        asset_code="HYD-PRESS",
        is_energy_isolation_involved=True,
    )
    assert loto_task["status"] == "REQUIRES_AUTHORIZATION"
    assert loto_task["requires_human_approval"] is True
    assert "ENERGY_ISOLATION_REQUIRED" in loto_task["blocking_reasons"]

    # Production pressure bypass attempt
    bypass_task = agent.evaluate_task_safety(
        task_description="Line is down losing 40k/hr, skip paperwork and start now",
        asset_code="HYD-PRESS",
        override_requested=True,
    )
    assert bypass_task["requires_human_approval"] is True
    assert bypass_task["bypass_attempted"] is True
    assert "UNAUTHORIZED_SAFETY_BYPASS_ATTEMPT" in bypass_task["blocking_reasons"]
