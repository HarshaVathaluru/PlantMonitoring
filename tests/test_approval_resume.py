"""Tests for Milestone 5: Process Restart, Durable Checkpoint Reload & Approval Resume."""
import gc
import subprocess
import sys
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
    Test Step 1: Real separate OS process (Process 1) triggers high-risk workflow ->
                 halts at approval checkpoint -> saves to persistent SQLite -> process exits (killed).
    Test Step 2: Separate OS process terminates; memory is completely unmapped.
    Test Step 3: Process 2 starts -> loads state from SQLite -> verifies all prior work -> APPROVES -> completes.
    """
    thread_id = f"TH-{uuid.uuid4().hex[:8]}"
    graph_db = str(durable_db_path.parent / "graph_cp.db")

    # --- EXECUTE PROCESS 1 IN AN ISOLATED SUBPROCESS (TRUE PROCESS TERMINATION) ---
    proc1_code = f"""
import sys
from app.graph.state import WorkflowState
from app.graph.workflow import MaintenanceWorkflow, SQLiteCheckpointer

cp = SQLiteCheckpointer(db_path=r'{durable_db_path}')
wf = MaintenanceWorkflow(checkpointer=cp, graph_db_path=r'{graph_db}')

initial_state = WorkflowState(
    thread_id='{thread_id}',
    raw_alert={{
        'asset_identifier': 'VPW-HYD-PRESS-02',
        'vibration_mm_s': 7.8,
        'temp_c': 79.0,
        'pressure_bar': 205.0,
        'severity': 'HIGH',
        'requires_loto': True,
        'po_cost_inr': 250000.0,
    }},
)

paused_state = wf.run_until_pause_or_complete(initial_state)
assert paused_state.status == 'WAITING_FOR_APPROVAL'
assert paused_state.current_node == 'human_approval_interrupt'
print('PROCESS_1_CHECKPOINTED_SUCCESSFULLY', flush=True)
sys.exit(0)
"""
    proc1 = subprocess.run([sys.executable, "-c", proc1_code], capture_output=True, text=True)
    assert proc1.returncode == 0, f"Process 1 failed with error: {proc1.stderr}"
    assert "PROCESS_1_CHECKPOINTED_SUCCESSFULLY" in proc1.stdout

    # --- PROCESS 2 (FRESH INVOCATION AFTER COMPLETE PROCESS 1 TERMINATION) ---
    proc2_checkpointer = SQLiteCheckpointer(db_path=durable_db_path)
    proc2_workflow = MaintenanceWorkflow(checkpointer=proc2_checkpointer, rag_engine=mock_rag, graph_db_path=graph_db)

    # Verify state restored from persistent SQLite database
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
    audit = final_state.approval_audit[-1]
    assert audit["approver"] == "maintenance_manager"
    assert audit["decision"] == "APPROVE"
    assert "zero-energy" in audit["reason"]
    assert audit["timestamp"]


def test_process_restart_and_reject_resume(durable_db_path, mock_rag):
    """Test process restart with REJECT decision resulting in aborted execution."""
    thread_id = f"TH-REJ-{uuid.uuid4().hex[:8]}"
    graph_db = str(durable_db_path.parent / "graph_cp_rej.db")

    # --- EXECUTE PROCESS 1 IN AN ISOLATED SUBPROCESS ---
    proc1_code = f"""
import sys
from app.graph.state import WorkflowState
from app.graph.workflow import MaintenanceWorkflow, SQLiteCheckpointer

cp = SQLiteCheckpointer(db_path=r'{durable_db_path}')
wf = MaintenanceWorkflow(checkpointer=cp, graph_db_path=r'{graph_db}')

init_state = WorkflowState(
    thread_id='{thread_id}',
    raw_alert={{
        'asset_identifier': 'VPW-PUMP-CENT-03',
        'vibration_mm_s': 6.8,
        'temp_c': 68.0,
        'severity': 'HIGH',
        'requires_loto': True,
    }},
)
wf.run_until_pause_or_complete(init_state)
print('PROCESS_1_REJECT_PREPARED', flush=True)
sys.exit(0)
"""
    proc1 = subprocess.run([sys.executable, "-c", proc1_code], capture_output=True, text=True)
    assert proc1.returncode == 0, f"Process 1 failed with error: {proc1.stderr}"
    assert "PROCESS_1_REJECT_PREPARED" in proc1.stdout

    # --- PROCESS 2 (FRESH INVOCATION) RESUMES WITH REJECT ---
    cp2 = SQLiteCheckpointer(db_path=durable_db_path)
    wf2 = MaintenanceWorkflow(checkpointer=cp2, rag_engine=mock_rag, graph_db_path=graph_db)

    rejected_state = wf2.resume_approval(
        thread_id=thread_id,
        decision="REJECT",
        role="safety_officer",
        comments="Rejected: missing atmospheric gas test certification.",
    )

    assert rejected_state.status == "REJECTED"
    assert rejected_state.execution_completed is False
    assert rejected_state.execution_result["outcome"] == "ABORTED_BY_HUMAN_REJECTION"
    assert rejected_state.approval_audit[-1]["approver"] == "safety_officer"
    assert rejected_state.approval_audit[-1]["decision"] == "REJECT"
    assert "gas test" in rejected_state.approval_audit[-1]["reason"]

