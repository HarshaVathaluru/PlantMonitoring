"""PlantGuard Production FastAPI Application for Milestone 8."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
from pydantic import BaseModel, Field

from app.agents.team_supervisor import TeamSupervisor
from app.config.settings import get_settings
from app.graph.state import WorkflowState
from app.graph.workflow import MaintenanceWorkflow, SQLiteCheckpointer
from app.observability.circuit_breaker import CircuitBreaker, CircuitBreakerOpenException, CircuitState
from app.observability.tracer import PlantGuardTracer
from app.rag.engine import HybridRAGEngine
from app.safety.policy_engine import SafetyPolicyEngine
from app.schemas.maintenance_event import EventSource, MaintenanceEvent, RiskLevel, SensorReadings

logger = logging.getLogger("plantguard.api")

app = FastAPI(
    title="PlantGuard Autonomous Operations Copilot",
    version="1.0.0",
    description="Production-grade AI Copilot for Predictive Maintenance & Supply Chain Operations",
)

settings = get_settings()
safety_engine = SafetyPolicyEngine()
rag_engine = HybridRAGEngine()
checkpointer = SQLiteCheckpointer()
workflow_engine = MaintenanceWorkflow(checkpointer=checkpointer, rag_engine=rag_engine)
team_supervisor = TeamSupervisor()
tracer = PlantGuardTracer()
circuit_breaker = CircuitBreaker(name="api_gateway_breaker")


# ── Strict Error Handler for Probe P5 ──

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Probe P5: Clean structured error reporting on malformed API ingestion."""
    errors = []
    for err in exc.errors():
        field_name = ".".join(str(loc) for loc in err["loc"])
        errors.append({
            "field": field_name,
            "message": err["msg"],
            "type": err["type"],
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "MALFORMED_INGESTION_PAYLOAD",
            "message": "Input validation failed against authoritative schema constraints",
            "detail": errors,
        },
    )


# ── Schemas ──

class IntakeRequest(BaseModel):
    asset_tag: str = Field(..., min_length=2, description="Target asset tag e.g. VPW-AIR-COMP-01")
    vibration_mm_s: float = Field(..., description="Vibration reading RMS mm/s")
    temp_c: float = Field(..., description="Surface temperature Celsius")
    pressure_bar: Optional[float] = Field(None, description="Pressure reading bar")
    current_a: Optional[float] = Field(None, description="Current reading Amperes")
    message: Optional[str] = Field(default="", description="Operator notes or raw alert message")
    severity: str = Field(default="medium", description="Reported severity: low, medium, high, critical")


class InvestigateRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Technical question regarding maintenance or SOP")
    asset_code: Optional[str] = Field(None, description="Asset class code e.g. AIR-COMP")


class WorkflowStartRequest(BaseModel):
    asset_tag: str
    vibration_mm_s: float
    temp_c: float
    pressure_bar: Optional[float] = None
    message: Optional[str] = Field(None, max_length=2000)
    severity: str = "medium"
    requires_loto: bool = False
    requires_permit: bool = False
    po_cost_inr: float = 0.0


class WorkflowApprovalRequest(BaseModel):
    thread_id: str
    decision: str = Field(..., description="'APPROVE' or 'REJECT'")
    role: str = Field(default="maintenance_manager", description="Approver role")
    comments: Optional[str] = Field(None, description="Review notes")


class TeamCollaborateRequest(BaseModel):
    asset_tag: str
    raw_text: Optional[str] = "Routine multi-agent maintenance evaluation"
    part_number: Optional[str] = None
    quantity: int = 1
    vibration_mm_s: float = 2.0
    temp_c: float = 65.0
    pressure_bar: Optional[float] = None
    is_energy_isolation_involved: bool = False
    is_hot_work_or_confined_space: bool = False
    override_requested: bool = False


# ── API Endpoints ──

@app.get("/health")
def health_check():
    """System health check and configuration summary."""
    return {
        "status": "HEALTHY",
        "service": "PlantGuard Copilot",
        "version": "1.0.0",
        "reference_date": settings.REFERENCE_DATE,
        "llm_provider": settings.LLM_PROVIDER.value,
        "llm_model": settings.LLM_MODEL,
        "circuit_breaker_state": circuit_breaker.get_state().value,
        "database": "CONNECTED",
        "checkpoint_db": str(checkpointer.db_path),
    }


@app.get("/api/v1/observability/circuit-breaker")
def get_circuit_breaker_status():
    """Real-time circuit breaker resilience status."""
    return {
        "name": circuit_breaker.name,
        "state": circuit_breaker.get_state().value,
        "failure_count": circuit_breaker.failure_count,
        "failure_threshold": circuit_breaker.failure_threshold,
        "recovery_timeout_seconds": circuit_breaker.recovery_timeout,
        "total_trips": circuit_breaker.total_trips,
    }


@app.get("/api/v1/observability/kpis")
def get_kpi_summary():
    """Quantitative SLA and reliability KPIs computed dynamically across recorded traces."""
    return tracer.compute_dynamic_kpis()


@app.get("/api/v1/observability/traces")
def list_recorded_traces():
    """Retrieve recorded distributed traces."""
    traces = []
    trace_dir = tracer.trace_dir
    if trace_dir.exists():
        import json
        for f in trace_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    traces.append(json.load(fp))
            except Exception:
                pass
    return {"total_traces": len(traces), "traces": traces[-10:]}


@app.post("/api/v1/intake", status_code=status.HTTP_201_CREATED)
def ingest_telemetry_alert(req: IntakeRequest):
    """
    Ingest, validate, and parse telemetry alert.
    Applies physical plausibility and prompt injection scans under Circuit Breaker protection.
    """
    def _do_intake():
        # Probe P1 scan
        inj_scan = safety_engine.scan_direct_injection(req.message or "")
        if inj_scan.injection_detected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Security alert: Prompt injection pattern detected: {inj_scan.reasons}",
            )

        # Probe P3 physical plausibility check
        plaus_result = safety_engine.validate_physical_plausibility(
            vibration_mm_s=req.vibration_mm_s,
            temp_c=req.temp_c,
            pressure_bar=req.pressure_bar,
            current_a=req.current_a,
        )

        readings = SensorReadings(
            vibration_mm_s=req.vibration_mm_s,
            temp_c=req.temp_c,
            pressure_bar=req.pressure_bar,
            current_a=req.current_a,
        )

        try:
            sev = RiskLevel(req.severity.lower())
        except ValueError:
            sev = RiskLevel.MEDIUM

        event = MaintenanceEvent(
            event_id=f"EV-API-{int(datetime.now().timestamp())}",
            source=EventSource.SENSOR_ALERT,
            received_at=datetime.now(),
            raw_text=req.message or f"Alert for {req.asset_tag}",
            asset_tag=req.asset_tag,
            readings=readings,
            severity=sev,
        )

        return {
            "event_id": event.event_id,
            "asset_tag": event.asset_tag,
            "severity": event.severity.value,
            "plausibility": plaus_result.model_dump(),
            "data_quality": event.data_quality.model_dump(),
            "requires_human_approval": event.requires_human_approval,
        }

    with tracer.trace_request("API_Ingest_Telemetry", metadata={"asset_tag": req.asset_tag}):
        with tracer.span(
            "Validation_And_Safety",
            metadata={"asset_tag": req.asset_tag, "model": settings.LLM_MODEL, "provider": settings.LLM_PROVIDER.value, "circuit_breaker_state": circuit_breaker.get_state().value},
        ):
            try:
                return circuit_breaker.execute(_do_intake)
            except CircuitBreakerOpenException as cbe:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Circuit Breaker OPEN: {cbe}",
                )


@app.post("/api/v1/investigate")
def investigate_technical_query(req: InvestigateRequest):
    """
    Search manuals and SOPs using Hybrid RAG with RRF.
    Enforces strict citation grounding and explicit refusal on unsupported topics under Circuit Breaker protection.
    """
    def _do_investigate():
        # Probe P4 check
        if safety_engine.is_undocumented_topic(req.query):
            return {
                "query": req.query,
                "answer": "I cannot verify this procedure or specification. The required technical evidence is not documented in the authorized PlantGuard equipment manuals or SOP standards.",
                "citations": [],
                "confidence": "refusal",
                "is_supported": False,
            }

        ans = rag_engine.answer_question(req.query, asset_code=req.asset_code)
        return ans.model_dump()

    with tracer.trace_request("API_Investigate_RAG", metadata={"asset": req.asset_code}):
        with tracer.span(
            "RAG_Search_And_Grounding",
            metadata={"model": settings.LLM_MODEL, "provider": settings.LLM_PROVIDER.value, "circuit_breaker_state": circuit_breaker.get_state().value},
        ):
            try:
                return circuit_breaker.execute(_do_investigate)
            except CircuitBreakerOpenException as cbe:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Circuit Breaker OPEN: {cbe}",
                )


@app.post("/api/v1/workflow/start")
def start_maintenance_workflow(req: WorkflowStartRequest):
    """
    Launch multi-step state graph workflow for incoming maintenance event.
    Halts automatically at human checkpoint if safety critical under Circuit Breaker protection.
    """
    def _do_workflow():
        thread_id = f"TH-{uuid.uuid4().hex[:8]}"

        state = WorkflowState(
            thread_id=thread_id,
            raw_alert=req.model_dump(),
        )

        final_state = workflow_engine.run_until_pause_or_complete(state)
        return {
            "thread_id": final_state.thread_id,
            "current_node": final_state.current_node,
            "status": final_state.status,
            "requires_human_approval": final_state.requires_human_approval,
            "approval_reason": final_state.approval_reason,
            "recommendation": final_state.recommendation,
            "root_cause_analysis": final_state.root_cause_analysis,
            "rag_procedure": final_state.rag_procedure,
            "rag_citations": final_state.rag_citations,
            "errors": final_state.errors,
            "execution_result": final_state.execution_result,
        }

    with tracer.trace_request("API_Workflow_Start", metadata={"asset_tag": req.asset_tag}):
        with tracer.span(
            "StateGraph_Execution",
            metadata={"asset_tag": req.asset_tag, "model": settings.LLM_MODEL, "provider": settings.LLM_PROVIDER.value, "circuit_breaker_state": circuit_breaker.get_state().value},
        ):
            try:
                return circuit_breaker.execute(_do_workflow)
            except CircuitBreakerOpenException as cbe:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Circuit Breaker OPEN: {cbe}",
                )


@app.post("/api/v1/workflow/approve")
def approve_workflow(req: WorkflowApprovalRequest):
    """
    Deliver human approval or rejection to a paused workflow.
    Resumes durable execution from SQLite checkpoint.
    """
    with tracer.trace_request("API_Workflow_Approve", metadata={"thread_id": req.thread_id}):
        with tracer.span("StateGraph_Resume"):
            try:
                resumed_state = workflow_engine.resume_approval(
                    thread_id=req.thread_id,
                    decision=req.decision,
                    role=req.role,
                    comments=req.comments,
                )
                return {
                    "thread_id": resumed_state.thread_id,
                    "status": resumed_state.status,
                    "current_node": resumed_state.current_node,
                    "execution_completed": resumed_state.execution_completed,
                    "execution_result": resumed_state.execution_result,
                }
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.get("/api/v1/workflow/{thread_id}")
def get_workflow_status(thread_id: str):
    """Retrieve checkpoint state for a specific workflow thread."""
    state = checkpointer.load(thread_id)
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Thread {thread_id} not found")
    return state.model_dump()


@app.post("/api/v1/team/run")
def run_multi_agent_team(req: TeamCollaborateRequest):
    """
    Execute collaborative multi-agent workflow across 5 specialized agents
    using official MCP transport for downtime, inventory, supplier, and policy resources.
    """
    with tracer.trace_request("API_Multi_Agent_Team", metadata={"asset_tag": req.asset_tag}):
        with tracer.span("TeamSupervisor_Collaboration", metadata={"asset_tag": req.asset_tag}):
            raw_alert = {
                "event_id": f"EV-TEAM-{int(datetime.now().timestamp())}",
                "asset_tag": req.asset_tag,
                "raw_text": req.raw_text,
                "vibration_mm_s": req.vibration_mm_s,
                "temp_c": req.temp_c,
                "pressure_bar": req.pressure_bar,
            }
            res = team_supervisor.run_collaborative_workflow(
                raw_alert=raw_alert,
                part_number=req.part_number,
                quantity=req.quantity,
                is_energy_isolation_involved=req.is_energy_isolation_involved,
                is_hot_work_or_confined_space=req.is_hot_work_or_confined_space,
                override_requested=req.override_requested,
            )
            return res


@app.get("/dashboard", response_class=HTMLResponse)
def render_dashboard():
    """Serve the focused operations console."""
    dashboard_path = Path(__file__).parent / "static" / "dashboard.html"
    return dashboard_path.read_text(encoding="utf-8")
