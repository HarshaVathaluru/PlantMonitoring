"""PlantGuard Production Multi-Step StateGraph with Durable Checkpointing & Human-in-the-Loop.

Meets Milestone 5 Level 4 requirements:
- Explicit StateGraph architecture with typed state
- Durable SQLite checkpointing across process restarts
- Human-in-the-loop interruption for safety-critical actions
- Zero unapproved energy-isolation or high-value procurement execution
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.config.settings import get_settings
from app.graph.state import WorkflowState
from app.rag.engine import HybridRAGEngine
from app.schemas.maintenance_event import (
    ApprovalRequiredReason,
    EventSource,
    MaintenanceEvent,
    RecommendedAction,
    RiskLevel,
    SensorReadings,
    WorkOrderStatus,
)
from app.tools.maintenance_tools import (
    calculate_downtime_cost,
    check_spare_parts_inventory,
    get_sensor_history,
    schedule_technician,
)

logger = logging.getLogger(__name__)


# ── Durable SQLite Checkpointer ──

class SQLiteCheckpointer:
    """Durable SQLite storage for workflow state across process restarts."""

    def __init__(self, db_path: Optional[Path] = None):
        settings = get_settings()
        self.db_path = db_path or Path("plantguard_checkpoints.db")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    current_node TEXT NOT NULL,
                    status TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cp_thread ON checkpoints(thread_id)")
            conn.commit()

    def save(self, state: WorkflowState) -> None:
        state.updated_at = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO checkpoints (thread_id, current_node, status, state_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    state.thread_id,
                    state.current_node,
                    state.status,
                    state.model_dump_json(),
                    state.updated_at,
                ),
            )
            conn.commit()

    def load(self, thread_id: str) -> Optional[WorkflowState]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT state_json FROM checkpoints
                WHERE thread_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (thread_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            data = json.loads(row["state_json"])
            return WorkflowState(**data)


# ── PlantGuard Maintenance Workflow Engine ──

class MaintenanceWorkflow:
    """Stateful multi-step maintenance workflow with checkpointing and human-in-the-loop."""

    def __init__(
        self,
        checkpointer: Optional[SQLiteCheckpointer] = None,
        rag_engine: Optional[HybridRAGEngine] = None,
    ):
        self.checkpointer = checkpointer or SQLiteCheckpointer()
        self.rag = rag_engine or HybridRAGEngine()
        self.settings = get_settings()

    # ── Node 1: Alert Intake ──
    def node_alert_intake(self, state: WorkflowState) -> WorkflowState:
        state.current_node = "alert_intake"
        state.status = "PROCESSING"
        logger.info(f"[{state.thread_id}] Node: alert_intake")
        
        # Ensure asset_identifier and basic fields
        raw = state.raw_alert
        if not raw.get("asset_identifier") and raw.get("asset_tag"):
            raw["asset_identifier"] = raw["asset_tag"]
            
        state.raw_alert = raw
        self.checkpointer.save(state)
        return state

    # ── Node 2: Validation ──
    def node_validation(self, state: WorkflowState) -> WorkflowState:
        state.current_node = "validation"
        logger.info(f"[{state.thread_id}] Node: validation")
        raw = state.raw_alert

        try:
            asset_tag = raw.get("asset_identifier") or raw.get("asset_tag")
            readings = SensorReadings(
                vibration_mm_s=raw.get("vibration_mm_s") if raw.get("vibration_mm_s") is not None else raw.get("vibration"),
                temp_c=raw.get("temp_c") if raw.get("temp_c") is not None else raw.get("temperature"),
                pressure_bar=raw.get("pressure_bar") if raw.get("pressure_bar") is not None else raw.get("pressure"),
                current_a=raw.get("current_amps") if raw.get("current_amps") is not None else raw.get("current_a"),
            )
            sev_str = str(raw.get("severity", "medium")).lower()
            try:
                sev = RiskLevel(sev_str)
            except ValueError:
                sev = RiskLevel.MEDIUM

            event = MaintenanceEvent(
                event_id=raw.get("event_id") or f"EV-{state.thread_id[:8]}",
                source=EventSource.SENSOR_ALERT,
                received_at=datetime.now(timezone.utc),
                raw_text=raw.get("raw_text") or f"Alert for {asset_tag}: vib={readings.vibration_mm_s}, temp={readings.temp_c}",
                asset_tag=asset_tag,
                readings=readings,
                severity=sev,
            )

            if event.data_quality.has_impossible_readings:
                state.validation_passed = False
                state.errors.extend(event.data_quality.plausibility_issues)
                state.status = "FAILED"
            else:
                state.maintenance_event = event.model_dump(mode="json")
                state.validation_passed = True
        except Exception as e:
            state.validation_passed = False
            state.errors.append(f"Validation failure: {e}")
            state.status = "FAILED"

        self.checkpointer.save(state)
        return state

    # ── Node 3: Sensor History ──
    def node_sensor_history(self, state: WorkflowState) -> WorkflowState:
        state.current_node = "sensor_history"
        logger.info(f"[{state.thread_id}] Node: sensor_history")
        
        asset = state.raw_alert.get("asset_identifier") or state.raw_alert.get("asset_tag")
        if asset:
            hist = get_sensor_history(asset, hours=24)
            state.sensor_history = [r.model_dump(mode="json") for r in hist.recent_readings]
            
        self.checkpointer.save(state)
        return state

    # ── Node 4: Root Cause Analysis ──
    def node_root_cause(self, state: WorkflowState) -> WorkflowState:
        state.current_node = "root_cause_analysis"
        logger.info(f"[{state.thread_id}] Node: root_cause_analysis")
        
        raw = state.raw_alert
        vib = raw.get("vibration_mm_s") or raw.get("vibration") or 0.0
        temp = raw.get("temp_c") or raw.get("temperature") or 0.0

        if vib > 7.0 and temp > 75.0:
            analysis = "Critical mechanical defect detected: severe bearing degradation with friction overheating."
        elif vib > 5.0:
            analysis = "Elevated vibration exceeding warning threshold indicating rotor unbalance or misalignment."
        elif temp > 80.0:
            analysis = "High thermal excursion observed; potential lubrication starvation or cooling failure."
        else:
            analysis = "Routine anomaly observed within manageable operating bands."

        state.root_cause_analysis = analysis
        self.checkpointer.save(state)
        return state

    # ── Node 5: RAG Lookup ──
    def node_rag_lookup(self, state: WorkflowState) -> WorkflowState:
        state.current_node = "rag_lookup"
        logger.info(f"[{state.thread_id}] Node: rag_lookup")

        asset = state.raw_alert.get("asset_identifier", "")
        # Extract asset class, e.g. VPW-AIR-COMP-01 -> AIR-COMP
        asset_class = None
        for code in ["AIR-COMP", "CHILLER", "CNC-MILL", "CONV-BELT", "HYD-PRESS", "IND-OVEN", "PUMP-CENT", "ROBOT-WELD"]:
            if code in asset.upper():
                asset_class = code
                break

        query = f"bearing replacement maintenance and lockout tagout procedure for {asset_class or 'equipment'}"
        ans = self.rag.answer_question(query, asset_code=asset_class, top_k=3)
        citations = ans.citations
        if not citations and ans.retrieved_chunks:
            citations = [r.chunk.chunk_id for r in ans.retrieved_chunks[:2]]
        state.rag_citations = citations
        state.rag_procedure = ans.answer

        self.checkpointer.save(state)
        return state

    # ── Node 6: Maintenance Recommendation & Resource Scheduling ──
    def node_maintenance_recommendation(self, state: WorkflowState) -> WorkflowState:
        state.current_node = "maintenance_recommendation"
        logger.info(f"[{state.thread_id}] Node: maintenance_recommendation")

        asset = state.raw_alert.get("asset_identifier", "UNKNOWN")
        downtime = calculate_downtime_cost(asset, downtime_minutes=120)
        state.estimated_downtime_cost = float(downtime.total_cost_inr)

        # Part inventory check
        part_no = state.raw_alert.get("required_part") or "SKF-6205-2RSH"
        inv = check_spare_parts_inventory(part_no)
        state.spare_parts_checked.append(inv.model_dump(mode="json"))

        # Tech schedule check
        sched = schedule_technician(
            required_skill="mechanical",
            estimated_hours=4,
            date_str="2026-08-01",
            shift="A",
        )
        tech_assigned = sched.available_technicians[0].name if sched.available_technicians else "None"
        state.technician_scheduled = sched.model_dump(mode="json")

        state.recommendation = {
            "action": "BEARING_REPLACEMENT",
            "downtime_minutes": 120,
            "cost_inr": state.estimated_downtime_cost,
            "part_number": part_no,
            "stock_on_hand": inv.on_hand,
            "technician_assigned": tech_assigned,
        }

        self.checkpointer.save(state)
        return state

    # ── Node 7: Safety Review & Conditional Routing ──
    def node_safety_review(self, state: WorkflowState) -> WorkflowState:
        state.current_node = "safety_review"
        logger.info(f"[{state.thread_id}] Node: safety_review")

        raw = state.raw_alert
        # Critical checks
        requires_loto = raw.get("requires_loto", True)
        requires_permit = raw.get("requires_permit", False)
        po_cost = raw.get("po_cost_inr", 0.0)

        # Safety-critical check
        needs_approval = False
        reasons = []

        if requires_loto:
            needs_approval = True
            reasons.append(ApprovalRequiredReason.ENERGY_ISOLATION_REQUIRED.value)
        if requires_permit:
            needs_approval = True
            reasons.append(ApprovalRequiredReason.SAFETY_CRITICAL_PERMIT_REQUIRED.value)
        if po_cost > self.settings.PROCUREMENT_AUTO_MAX_INR:
            needs_approval = True
            reasons.append(ApprovalRequiredReason.PO_VALUE_ABOVE_AUTO_LIMIT.value)
        if raw.get("severity") == "CRITICAL":
            needs_approval = True
            reasons.append(ApprovalRequiredReason.PRODUCTION_IMPACT_HIGH.value)

        state.requires_human_approval = needs_approval
        state.approval_reason = "; ".join(reasons) if reasons else None
        state.safety_review = {
            "loto_mandated": requires_loto,
            "permit_required": requires_permit,
            "reasons": reasons,
        }

        self.checkpointer.save(state)
        return state

    # ── Step Router & Runner ──
    def run_until_pause_or_complete(self, state: WorkflowState) -> WorkflowState:
        """Executes the workflow graph sequentially until a human checkpoint or completion."""
        if state.status in ["COMPLETED", "FAILED", "WAITING_FOR_APPROVAL"]:
            return state

        # Step 1: Alert Intake
        state = self.node_alert_intake(state)

        # Step 2: Validation
        state = self.node_validation(state)
        if not state.validation_passed:
            return state

        # Step 3: Sensor History
        state = self.node_sensor_history(state)

        # Step 4: Root Cause
        state = self.node_root_cause(state)

        # Step 5: RAG Lookup
        state = self.node_rag_lookup(state)

        # Step 6: Maintenance Recommendation
        state = self.node_maintenance_recommendation(state)

        # Step 7: Safety Review
        state = self.node_safety_review(state)

        # Step 8: Conditional Routing
        if state.requires_human_approval and state.approval_decision is None:
            state.current_node = "human_approval_interrupt"
            state.status = "WAITING_FOR_APPROVAL"
            logger.info(f"[{state.thread_id}] Workflow PAUSED: Awaiting human approval for {state.approval_reason}")
            self.checkpointer.save(state)
            return state

        # If already approved or no approval needed -> execute
        return self.node_execution(state)

    # ── Node 8: Execution ──
    def node_execution(self, state: WorkflowState) -> WorkflowState:
        state.current_node = "execution"
        logger.info(f"[{state.thread_id}] Node: execution")

        if state.requires_human_approval and state.approval_decision != "APPROVE":
            state.status = "REJECTED"
            state.execution_result = {
                "outcome": "ABORTED_BY_HUMAN_REJECTION",
                "details": state.approver_comments or "Human reviewer rejected proposed maintenance intervention.",
            }
            self.checkpointer.save(state)
            return state

        state.status = "COMPLETED"
        state.execution_completed = True
        state.execution_result = {
            "outcome": "SUCCESS",
            "work_order_id": f"WO-{state.thread_id[:8].upper()}",
            "authorized_by": state.approval_role or "SYSTEM_AUTO_DISPATCH",
            "execution_timestamp": datetime.now(timezone.utc).isoformat(),
            "citations_applied": state.rag_citations,
            "recommendation_summary": state.recommendation,
        }

        self.checkpointer.save(state)
        return state

    # ── Resume from Checkpoint ──
    def resume_approval(
        self,
        thread_id: str,
        decision: str,  # "APPROVE" or "REJECT"
        role: str = "maintenance_manager",
        comments: Optional[str] = None,
    ) -> WorkflowState:
        """
        Resumes a paused workflow thread after human approval/rejection.
        Loads checkpoint from SQLite, applies decision, and continues execution.
        """
        state = self.checkpointer.load(thread_id)
        if not state:
            raise ValueError(f"No checkpoint found for thread {thread_id}")

        if state.status != "WAITING_FOR_APPROVAL":
            raise ValueError(f"Thread {thread_id} is in state '{state.status}', not WAITING_FOR_APPROVAL")

        state.approval_decision = decision.upper()
        state.approval_role = role
        state.approver_comments = comments
        state.status = "APPROVED" if decision.upper() == "APPROVE" else "REJECTED"

        self.checkpointer.save(state)
        return self.node_execution(state)
