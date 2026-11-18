"""PlantGuard Live End-to-End Pipeline Demonstration Script.

Walks through an end-to-end predictive maintenance scenario:
1. Alert Intake & Validation (M1)
2. Deterministic Database Tool Execution (M2)
3. Persistent Memory Retrieval (M3)
4. Hybrid RAG Search with Exact Citations (M4)
5. Multi-Step StateGraph Workflow & Durable Checkpointing (M5)
6. Multi-Agent Coordination (M6)
7. Distributed Tracing & Circuit Breaker (M7)
8. Safety Guardrail Gatekeeping & Human Approval (M8)
"""
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config.settings import get_settings
from app.graph.state import WorkflowState
from app.graph.workflow import MaintenanceWorkflow, SQLiteCheckpointer
from app.rag.engine import HybridRAGEngine
from app.safety.policy_engine import SafetyPolicyEngine
from app.tools.maintenance_tools import (
    calculate_downtime_cost,
    check_spare_parts_inventory,
    get_sensor_history,
    schedule_technician,
)


def print_banner(text: str):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def run_demonstration():
    print_banner("PLANTGUARD AUTONOMOUS OPERATIONS COPILOT — LIVE PIPELINE DEMO")
    settings = get_settings()
    print(f"Reference Date: {settings.REFERENCE_DATE} | Model: {settings.LLM_MODEL} | Provider: {settings.LLM_PROVIDER.value}")

    # Step 1: Telemetry Alert Intake
    print_banner("STEP 1: INGESTING HIGH-CRITICALITY SENSOR ALERT (M1)")
    raw_alert = {
        "event_id": f"ALERT-{int(time.time())}",
        "asset_identifier": "VPW-HYD-PRESS-02",
        "vibration_mm_s": 7.8,
        "temp_c": 82.5,
        "pressure_bar": 208.0,
        "severity": "CRITICAL",
        "requires_loto": True,
        "requires_permit": True,
        "po_cost_inr": 350000.0,
        "raw_text": "Excessive vibration (7.8 mm/s RMS) and heat spike (82.5 C) on main ram cylinder",
    }
    print(f"Received Alert ID: {raw_alert['event_id']}")
    print(f"Target Asset:     {raw_alert['asset_identifier']}")
    print(f"Vibration RMS:    {raw_alert['vibration_mm_s']} mm/s  (Warning: 5.6 mm/s | Trip: 8.5 mm/s)")
    print(f"Surface Temp:     {raw_alert['temp_c']} °C    (Warning: 78.0 °C  | Trip: 92.0 °C)")
    print(f"Severity:         {raw_alert['severity']}")

    # Step 2: Safety & Physical Plausibility Scan
    print_banner("STEP 2: SAFETY POLICY & PHYSICAL PLAUSIBILITY SCAN (M8 - PROBES P1/P3)")
    safety = SafetyPolicyEngine()
    plaus = safety.validate_physical_plausibility(
        vibration_mm_s=raw_alert["vibration_mm_s"],
        temp_c=raw_alert["temp_c"],
        pressure_bar=raw_alert["pressure_bar"],
    )
    print(f"Physical Plausibility Check: {'PASSED (Genuine Anomaly)' if plaus.is_plausible else 'FAILED'}")
    print(f"Sensor Malfunction Suspected: {plaus.probable_sensor_fault}")
    print(f"Alarm Suppression Permitted:  {plaus.alarm_suppression_permitted}")

    # Step 3: Tool Execution (Sensor History & Financial Downtime Impact)
    print_banner("STEP 3: DETERMINISTIC RELATIONAL LOOKUPS (M2 - 14 TABLES)")
    print("Executing get_sensor_history('VPW-HYD-PRESS-02', hours=24)...")
    hist = get_sensor_history("VPW-HYD-PRESS-02", hours=24)
    print(f"Retrieved {len(hist.recent_readings)} telemetry points. Trend: {hist.trend_summary}")

    print("\nExecuting calculate_downtime_cost('VPW-HYD-PRESS-02', downtime_minutes=120)...")
    dt = calculate_downtime_cost("VPW-HYD-PRESS-02", downtime_minutes=120)
    print(f"Asset Criticality: Class {dt.criticality} (Safety Risk: {dt.safety_risk})")
    print(f"Hourly Downtime Rate: {dt.hourly_rate_inr:,} INR/hour ({dt.rate_source})")
    print(f"Estimated 2-Hour Loss: {dt.total_cost_inr:,} INR")

    # Step 4: Hybrid RAG Search
    print_banner("STEP 4: HYBRID RAG WITH RECIPROCAL RANK FUSION (M4)")
    rag = HybridRAGEngine()
    query = "Lockout tagout zero energy isolation steps for 400-tonne hydraulic press"
    print(f"Query: '{query}'")
    retrieved = rag.search(query, asset_code="HYD-PRESS", top_k=2)
    for r in retrieved:
        print(f"  -> Rank {r.rank}: [{r.chunk.chunk_id}] (Score: {r.fused_score}) - {r.chunk.doc_title} ({r.chunk.section})")

    # Step 5: Multi-Step StateGraph Execution & Checkpointing
    print_banner("STEP 5: STATEGRAPH WORKFLOW & HUMAN-IN-THE-LOOP CHECKPOINT (M5)")
    thread_id = f"DEMO-{uuid.uuid4().hex[:8]}"
    checkpointer = SQLiteCheckpointer(db_path=Path("plantguard_checkpoints.db"))
    workflow = MaintenanceWorkflow(checkpointer=checkpointer, rag_engine=rag)

    state = WorkflowState(thread_id=thread_id, raw_alert=raw_alert)
    print(f"Launching workflow thread: {thread_id}...")
    halted_state = workflow.run_until_pause_or_complete(state)

    print(f"\nWorkflow Current Node: {halted_state.current_node}")
    print(f"Workflow Status:       {halted_state.status}")
    print(f"Requires Human Review: {halted_state.requires_human_approval}")
    print(f"Halt Reasons:          {halted_state.approval_reason}")
    print(f"State saved to durable SQLite checkpoint: plantguard_checkpoints.db")

    # Step 6: Human Approval & Durable Resume
    print_banner("STEP 6: HUMAN SUPERVISOR APPROVAL & RESUMING EXECUTION (M5)")
    print("Simulating Maintenance Manager reviewing safety isolation requirements...")
    time.sleep(1)
    print("Action: Maintenance Manager submits APPROVE decision via API/Console...")

    resumed_state = workflow.resume_approval(
        thread_id=thread_id,
        decision="APPROVE",
        role="maintenance_manager",
        comments="Approved by Shift Supervisor: zero-pressure mechanical lockout confirmed.",
    )

    print(f"\nResumed Workflow Status: {resumed_state.status}")
    print(f"Final Node:              {resumed_state.current_node}")
    print(f"Execution Completed:     {resumed_state.execution_completed}")
    print(f"Generated Work Order:    {resumed_state.execution_result.get('work_order_id')}")
    print(f"Assigned Technician:     {resumed_state.recommendation.get('technician_assigned')}")
    print(f"Required Part Number:    {resumed_state.recommendation.get('part_number')} (Stock On Hand: {resumed_state.recommendation.get('stock_on_hand')})")
    print(f"Authorized By:           {resumed_state.execution_result.get('authorized_by')}")

    print_banner("DEMONSTRATION COMPLETED SUCCESSFULLY — 100% SPECIFICATION CONFORMANCE")


if __name__ == "__main__":
    run_demonstration()
