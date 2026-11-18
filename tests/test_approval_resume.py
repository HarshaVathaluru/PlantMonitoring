"""Tests for Milestone 5: Process Restart, Durable Checkpoint Reload & Approval Resume."""
import gc
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
            content="Follow LOTO standard [lockout-tagout-sec01].",
            model="mock-rag",
            provider="mock",
            total_tokens=100,
        )


@pytest.fixture
def durable_db_path(tmp_path):
    return tmp_path / "durable_checkpoints.db"


@pytest.fixture
def mock_rag():
    return HybridRAGEngine(llm_adapter=MockRAGAdapter())


def test_process_restart_and_approve_resume(durable_db_path, mock_rag):
    """
    Test Step 1: Process 1 triggers high-risk workflow -> halts at approval checkpoint -> saves to SQLite.
    Test Step 2: Simulate process termination (kill process 1 objects).
    Test Step 3: Process 2 starts -> loads state from SQLite -> verifies all prior work -> APPROVES -> completes.
    """
    thread_id = f"TH-{uuid.uuid4().hex[:8]}"

    # --- SIMULATE PROCESS 1 ---
    proc1_checkpointer = SQLiteCheckpointer(db_path=durable_db_path)
    proc1_workflow = MaintenanceWorkflow(checkpointer=proc1_checkpointer, rag_engine=mock_rag)

    initial_state = WorkflowState(
        thread_id=thread_id,
        raw_alert={
            "asset_identifier": "VPW-HYD-PRESS-02",
            "vibration_mm_s": 7.8,
            "temp_c": 79.0,
            "pressure_bar": 205.0,
            "severity": "HIGH",
            "requires_loto": True,
            "po_cost_inr": 250000.0,
        },
    )

    paused_state = proc1_workflow.run_until_pause_or_complete(initial_state)
    assert paused_state.status == "WAITING_FOR_APPROVAL"
    assert paused_state.current_node == "human_approval_interrupt"
    assert paused_state.recommendation is not None
    assert len(paused_state.sensor_history) > 0

    # Kill Process 1 objects
    del proc1_workflow
    del proc1_checkpointer
    del paused_state
    del initial_state
    gc.collect()

    # --- SIMULATE PROCESS 2 (FRESH INVOCATION AFTER RESTART) ---
    proc2_checkpointer = SQLiteCheckpointer(db_path=durable_db_path)
    proc2_workflow = MaintenanceWorkflow(checkpointer=proc2_checkpointer, rag_engine=mock_rag)

    # Verify state restored from SQLite
    restored_state = proc2_checkpointer.load(thread_id)
    assert restored_state is not None
    assert restored_state.thread_id == thread_id
    assert restored_state.status == "WAITING_FOR_APPROVAL"
    assert restored_state.current_node == "human_approval_interrupt"
    assert restored_state.recommendation["action"] == "BEARING_REPLACEMENT"

    # Human reviewer delivers APPROVE decision
    final_state = proc2_workflow.resume_approval(
        thread_id=thread_id,
        decision="APPROVE",
        role="maintenance_manager",
        comments="Approved by M. Rao after verifying zero-energy pressure discharge.",
    )

    assert final_state.status == "COMPLETED"
    assert final_state.current_node == "execution"
    assert final_state.execution_completed is True
    assert final_state.execution_result["outcome"] == "SUCCESS"
    assert final_state.execution_result["authorized_by"] == "maintenance_manager"
    assert "WO-" in final_state.execution_result["work_order_id"]


def test_process_restart_and_reject_resume(durable_db_path, mock_rag):
    """Test process restart with REJECT decision resulting in aborted execution."""
    thread_id = f"TH-REJ-{uuid.uuid4().hex[:8]}"

    # Process 1
    cp1 = SQLiteCheckpointer(db_path=durable_db_path)
    wf1 = MaintenanceWorkflow(checkpointer=cp1, rag_engine=mock_rag)

    init_state = WorkflowState(
        thread_id=thread_id,
        raw_alert={
            "asset_identifier": "VPW-PUMP-CENT-03",
            "vibration_mm_s": 6.8,
            "temp_c": 68.0,
            "severity": "HIGH",
            "requires_loto": True,
        },
    )
    wf1.run_until_pause_or_complete(init_state)

    del wf1
    del cp1
    gc.collect()

    # Process 2 resumes with REJECT
    cp2 = SQLiteCheckpointer(db_path=durable_db_path)
    wf2 = MaintenanceWorkflow(checkpointer=cp2, rag_engine=mock_rag)

    rejected_state = wf2.resume_approval(
        thread_id=thread_id,
        decision="REJECT",
        role="safety_officer",
        comments="Rejected: missing atmospheric gas test certification.",
    )

    assert rejected_state.status == "REJECTED"
    assert rejected_state.execution_completed is False
    assert rejected_state.execution_result["outcome"] == "ABORTED_BY_HUMAN_REJECTION"
