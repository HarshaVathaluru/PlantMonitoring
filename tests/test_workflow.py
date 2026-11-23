"""Tests for Milestone 5: Stateful Maintenance Workflow Engine."""
import uuid
import pytest
from pathlib import Path
from app.graph.state import WorkflowState
from app.graph.workflow import MaintenanceWorkflow, SQLiteCheckpointer
from app.rag.engine import HybridRAGEngine
from app.adapters.llm_adapter import LLMAdapter, LLMResponse


class MockRAGAdapter(LLMAdapter):
    def generate(self, messages, temperature=None, max_tokens=None, **kwargs) -> LLMResponse:
        return LLMResponse(
            content="According to [manual-air-comp-sec01], follow zero energy isolation steps.",
            model="mock-rag",
            provider="mock",
            total_tokens=100,
        )


@pytest.fixture
def temp_checkpointer(tmp_path):
    db_path = tmp_path / "test_checkpoints.db"
    return SQLiteCheckpointer(db_path=db_path)


@pytest.fixture
def workflow(temp_checkpointer):
    rag = HybridRAGEngine(llm_adapter=MockRAGAdapter())
    return MaintenanceWorkflow(checkpointer=temp_checkpointer, rag_engine=rag)


def test_workflow_auto_route_routine(workflow):
    """Routine maintenance without LOTO or permits routes to auto-execution."""
    thread_id = str(uuid.uuid4())
    state = WorkflowState(
        thread_id=thread_id,
        raw_alert={
            "asset_identifier": "VPW-AIR-COMP-01",
            "vibration_mm_s": 2.5,
            "temp_c": 55.0,
            "pressure_bar": 7.2,
            "severity": "LOW",
            "requires_loto": False,
            "requires_permit": False,
            "po_cost_inr": 50000.0,
        },
    )

    final_state = workflow.run_until_pause_or_complete(state)

    assert final_state.status == "COMPLETED"
    assert final_state.current_node == "execution"
    assert final_state.execution_completed is True
    assert final_state.execution_result["outcome"] == "SUCCESS"
    assert final_state.requires_human_approval is False


def test_workflow_fails_physical_validation(workflow):
    """Event violating physical bounds fails at validation node."""
    thread_id = str(uuid.uuid4())
    state = WorkflowState(
        thread_id=thread_id,
        raw_alert={
            "asset_identifier": "VPW-AIR-COMP-01",
            "vibration_mm_s": 950.0,  # Physically impossible (> 100 mm/s)
            "temp_c": -45.0,           # Physically impossible (< -20 C)
            "severity": "CRITICAL",
        },
    )

    final_state = workflow.run_until_pause_or_complete(state)

    assert final_state.status == "FAILED"
    assert final_state.validation_passed is False
    assert len(final_state.errors) > 0


def test_workflow_halts_for_energy_isolation(workflow):
    """Safety-critical event requiring LOTO must halt for human approval."""
    thread_id = str(uuid.uuid4())
    state = WorkflowState(
        thread_id=thread_id,
        raw_alert={
            "asset_identifier": "VPW-HYD-PRESS-02",
            "vibration_mm_s": 8.2,
            "temp_c": 82.0,
            "pressure_bar": 210.0,
            "severity": "CRITICAL",
            "requires_loto": True,
            "requires_permit": True,
            "po_cost_inr": 350000.0,
        },
    )

    final_state = workflow.run_until_pause_or_complete(state)

    assert final_state.status == "WAITING_FOR_APPROVAL"
    assert final_state.current_node == "human_approval_interrupt"
    assert final_state.requires_human_approval is True
    assert "ENERGY_ISOLATION_REQUIRED" in final_state.approval_reason
    assert "PO_VALUE_ABOVE_AUTO_LIMIT" in final_state.approval_reason
    assert final_state.execution_completed is False
