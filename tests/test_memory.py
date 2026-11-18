"""Tests for M3: Persistent Memory Engine (Standard Tests T1 through T9)."""
import gc
import os
import tempfile
from pathlib import Path
import pytest

from app.memory.persistent_memory import PersistentMemoryManager


@pytest.fixture
def temp_db_file():
    """Create a temporary sqlite database file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    gc.collect()
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def test_persistent_memory_t1_through_t9(temp_db_file):
    """
    Execute standard evaluation test sequence T1-T9 as defined in
    PlantGuard Capstone Evaluation Guide Section 5.1.
    """
    # ── Phase 1: Pre-restart storage ──
    mem = PersistentMemoryManager(db_path=temp_db_file)

    # T1: Record stable fact "Pump P-101 is a critical asset."
    fact = mem.store_fact(
        asset_tag="P-101",
        fact_key="criticality",
        fact_value="CRITICAL",
        updated_by="engineer_alice",
        identity_id="user_alice",
    )
    assert fact.asset_tag == "P-101"
    assert fact.fact_value == "CRITICAL"
    assert fact.version == 1

    # T2: Complete an event: bearing replaced on P-101 under a work order
    rec = mem.record_maintenance_event(
        asset_tag="P-101",
        event_type="bearing_replacement",
        summary="Drive-end roller bearing replaced and lubricated under work order VPW-WO-00042",
        work_order_id="VPW-WO-00042",
        details={"part_fitted": "VPW-P-00123", "hours_taken": 3.5},
        identity_id="user_alice",
        timestamp="2026-08-01T11:00:00",
    )
    assert rec.work_order_id == "VPW-WO-00042"
    assert rec.asset_tag == "P-101"

    # T3: Store LOTO procedural steps for pump maintenance
    mem.store_procedure_step(
        procedure_name="pump_loto",
        asset_code="PUMP-CENT",
        step_number=1,
        instruction="Notify affected production supervisor on Line 2",
        requires_loto=True,
    )
    mem.store_procedure_step(
        procedure_name="pump_loto",
        asset_code="PUMP-CENT",
        step_number=2,
        instruction="Isolate 415V electrical feed at MCC-02 Breaker 4 and apply red padlock",
        safety_hazard="electrical",
        requires_loto=True,
    )
    mem.store_procedure_step(
        procedure_name="pump_loto",
        asset_code="PUMP-CENT",
        step_number=3,
        instruction="Close suction and discharge valves, bleed residual pressure via drain cock",
        safety_hazard="hydraulic_pressure",
        requires_loto=True,
    )

    loto_steps = mem.get_procedure_steps("pump_loto")
    assert len(loto_steps) == 3
    assert loto_steps[1].step_number == 2
    assert "padlock" in loto_steps[1].instruction

    # ── SIMULATED PROCESS RESTART ──
    # Destroy mem object completely to verify disk persistence
    del mem

    # ── Phase 2: Post-restart recovery ──
    mem_restarted = PersistentMemoryManager(db_path=temp_db_file)

    # T4: New thread recalls bearing replacement and work-order specifics
    history = mem_restarted.get_recent_history(asset_tag="P-101", identity_id="user_alice")
    assert len(history) == 1
    assert history[0].work_order_id == "VPW-WO-00042"
    assert "roller bearing" in history[0].summary
    assert history[0].details.get("part_fitted") == "VPW-P-00123"

    # T5: Ask a task where P-101 criticality matters without restating it
    p101_fact = mem_restarted.get_fact(asset_tag="P-101", fact_key="criticality", identity_id="user_alice")
    assert p101_fact is not None
    assert p101_fact.fact_value == "CRITICAL"

    # T6: Retrieve and apply stored LOTO procedure
    restarted_loto = mem_restarted.get_procedure_steps("pump_loto")
    assert len(restarted_loto) == 3
    assert restarted_loto[0].instruction.startswith("Notify")

    # T7: Change the stored fact and verify newest fact overrides old value (supersession)
    updated_fact = mem_restarted.store_fact(
        asset_tag="P-101",
        fact_key="criticality",
        fact_value="CLASS_A_EXTREME",
        updated_by="plant_head",
        identity_id="user_alice",
    )
    assert updated_fact.fact_value == "CLASS_A_EXTREME"
    assert updated_fact.version == 2

    retrieved_fact = mem_restarted.get_fact(asset_tag="P-101", fact_key="criticality", identity_id="user_alice")
    assert retrieved_fact.fact_value == "CLASS_A_EXTREME"
    assert retrieved_fact.version == 2

    # T8: Use separate identity B and verify identity isolation (zero data leakage)
    fact_identity_b = mem_restarted.get_fact(asset_tag="P-101", fact_key="criticality", identity_id="user_bob")
    assert fact_identity_b is None

    history_identity_b = mem_restarted.get_recent_history(asset_tag="P-101", identity_id="user_bob")
    assert len(history_identity_b) == 0

    # T9: Add 15+ filler turns in session, early fact remains available in durable memory
    session_id = "session_test_filler"
    for turn in range(1, 20):
        mem_restarted.add_session_message(
            session_id=session_id,
            role="user" if turn % 2 == 1 else "assistant",
            content=f"Filler message turn {turn} discussing unrelated maintenance shift notes",
            identity_id="user_alice",
            max_history=10,  # Session trim budget
        )

    # Session messages trimmed to 10
    session_msgs = mem_restarted.get_session_history(session_id=session_id, identity_id="user_alice")
    assert len(session_msgs) == 10

    # But durable fact for P-101 survives unaffected!
    stable_fact_after_filler = mem_restarted.get_fact(
        asset_tag="P-101", fact_key="criticality", identity_id="user_alice"
    )
    assert stable_fact_after_filler is not None
    assert stable_fact_after_filler.fact_value == "CLASS_A_EXTREME"
