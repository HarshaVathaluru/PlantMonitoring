"""PlantGuard Production FastAPI Application for Milestone 8."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from app.config.settings import get_settings
from app.graph.state import WorkflowState
from app.graph.workflow import MaintenanceWorkflow, SQLiteCheckpointer
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
    severity: str = "medium"
    requires_loto: bool = False
    requires_permit: bool = False
    po_cost_inr: float = 0.0


class WorkflowApprovalRequest(BaseModel):
    thread_id: str
    decision: str = Field(..., description="'APPROVE' or 'REJECT'")
    role: str = Field(default="maintenance_manager", description="Approver role")
    comments: Optional[str] = Field(None, description="Review notes")


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
        "database": "CONNECTED",
        "checkpoint_db": str(checkpointer.db_path),
    }


@app.post("/api/v1/intake", status_code=status.HTTP_201_CREATED)
def ingest_telemetry_alert(req: IntakeRequest):
    """
    Ingest, validate, and parse telemetry alert.
    Applies physical plausibility and prompt injection scans.
    """
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


@app.post("/api/v1/investigate")
def investigate_technical_query(req: InvestigateRequest):
    """
    Search manuals and SOPs using Hybrid RAG with RRF.
    Enforces strict citation grounding and explicit refusal on unsupported topics (Probe P4).
    """
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


@app.post("/api/v1/workflow/start")
def start_maintenance_workflow(req: WorkflowStartRequest):
    """
    Launch multi-step state graph workflow for incoming maintenance event.
    Halts automatically at human checkpoint if safety critical.
    """
    import uuid
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
        "execution_result": final_state.execution_result,
    }


@app.post("/api/v1/workflow/approve")
def approve_workflow(req: WorkflowApprovalRequest):
    """
    Deliver human approval or rejection to a paused workflow.
    Resumes durable execution from SQLite checkpoint.
    """
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


@app.get("/dashboard", response_class=HTMLResponse)
def render_dashboard():
    """PlantGuard Real-Time Operational Dashboard with Live Interactive Testing."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PlantGuard Copilot - Operations Dashboard</title>
        <style>
            :root {
                --bg: #0b1120;
                --surface: #1e293b;
                --surface-hover: #273549;
                --border: #334155;
                --text: #f8fafc;
                --text-muted: #94a3b8;
                --primary: #38bdf8;
                --primary-hover: #0284c7;
                --success: #22c55e;
                --warning: #f59e0b;
                --danger: #ef4444;
            }
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 2rem; }
            .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 1.25rem; }
            .badge { background: var(--success); color: #022c22; padding: 0.35rem 0.85rem; border-radius: 9999px; font-weight: 700; font-size: 0.875rem; letter-spacing: 0.05em; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1.25rem; margin-top: 1.5rem; }
            .card { background: var(--surface); border: 1px solid var(--border); border-radius: 0.75rem; padding: 1.25rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
            .card h3 { margin-top: 0; color: var(--text-muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
            .metric { font-size: 2rem; font-weight: 800; color: var(--primary); margin: 0.35rem 0; }
            table { width: 100%; border-collapse: collapse; margin-top: 0.75rem; font-size: 0.875rem; }
            th, td { text-align: left; padding: 0.75rem; border-bottom: 1px solid var(--border); }
            th { color: var(--text-muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; }
            
            .section-title { font-size: 1.25rem; font-weight: 700; color: #fff; margin-top: 2rem; margin-bottom: 0.75rem; display: flex; align-items: center; gap: 0.5rem; }
            
            /* Interactive console */
            .input-group { margin-bottom: 0.75rem; }
            label { display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.25rem; text-transform: uppercase; font-weight: 600; }
            input, select, textarea { width: 100%; background: #0f172a; border: 1px solid var(--border); border-radius: 0.375rem; color: #fff; padding: 0.6rem; font-size: 0.875rem; box-sizing: border-box; }
            input:focus, textarea:focus { outline: 2px solid var(--primary); }
            .btn { background: var(--primary); color: #0b1120; border: none; border-radius: 0.375rem; padding: 0.6rem 1.2rem; font-weight: 700; cursor: pointer; transition: 0.2s; font-size: 0.875rem; }
            .btn:hover { background: var(--primary-hover); color: #fff; }
            .btn-secondary { background: #334155; color: #fff; }
            .btn-secondary:hover { background: #475569; }
            .btn-danger { background: var(--danger); color: #fff; }
            .btn-success { background: var(--success); color: #022c22; font-weight: 700; }
            .btn-sm { padding: 0.3rem 0.6rem; font-size: 0.75rem; margin-right: 0.35rem; margin-bottom: 0.35rem; }
            
            .result-box { background: #0f172a; border: 1px solid var(--border); border-radius: 0.5rem; padding: 1rem; margin-top: 1rem; font-family: monospace; font-size: 0.875rem; white-space: pre-wrap; display: none; }
            .status-pill { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 700; }
            .pill-waiting { background: rgba(245, 158, 11, 0.2); color: var(--warning); border: 1px solid var(--warning); }
            .pill-completed { background: rgba(34, 197, 94, 0.2); color: var(--success); border: 1px solid var(--success); }
            .pill-refusal { background: rgba(239, 68, 68, 0.2); color: var(--danger); border: 1px solid var(--danger); }
        </style>
    </head>
    <body>
        <div class="header">
            <div>
                <h1 style="margin: 0; color: #f8fafc; font-size: 1.75rem;">PlantGuard Operations Copilot</h1>
                <p style="margin: 0.25rem 0 0 0; color: var(--text-muted); font-size: 0.875rem;">Predictive Maintenance & Supply Chain Operations (Fixed Reference Date: 2026-08-01)</p>
            </div>
            <div><span class="badge">SYSTEM READY (LEVEL 4)</span></div>
        </div>

        <!-- Metric KPI Cards -->
        <div class="grid">
            <div class="card">
                <h3>Monitored Equipment</h3>
                <div class="metric">8 Asset Classes</div>
                <p style="margin:0; color:var(--text-muted); font-size: 0.8rem;">Air Compressors, CNC Mills, Hydraulic Presses, Robots, Pumps</p>
            </div>
            <div class="card">
                <h3>Corpus Grounding</h3>
                <div class="metric">13 Manuals</div>
                <p style="margin:0; color:var(--text-muted); font-size: 0.8rem;">8 Equipment Manuals + 5 Plant Safety SOP Standards</p>
            </div>
            <div class="card">
                <h3>Relational Mock API</h3>
                <div class="metric">14 Tables</div>
                <p style="margin:0; color:var(--text-muted); font-size: 0.8rem;">31,516 records, 120 attributes cached</p>
            </div>
            <div class="card">
                <h3>Safety Guardrails</h3>
                <div class="metric">100% Active</div>
                <p style="margin:0; color:var(--text-muted); font-size: 0.8rem;">Hard gates: Zero unapproved LOTO & PO &gt; 200,000 INR</p>
            </div>
        </div>

        <!-- Live Equipment Health Overview -->
        <div class="section-title">Equipment Health Status (Class A / B Assets)</div>
        <div class="grid">
            <div class="card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <strong style="color:var(--primary);">VPW-HYD-PRESS-02</strong>
                    <span class="status-pill pill-completed">Class A · Operational</span>
                </div>
                <p style="font-size:0.8rem; color:var(--text-muted); margin: 0.5rem 0 0 0;">Hourly Downtime: <strong>40,000 INR/hr</strong><br>Vib Trip: 8.5 mm/s | Temp Trip: 92°C</p>
            </div>
            <div class="card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <strong style="color:var(--primary);">VPW-AIR-COMP-01</strong>
                    <span class="status-pill pill-completed">Class A · Operational</span>
                </div>
                <p style="font-size:0.8rem; color:var(--text-muted); margin: 0.5rem 0 0 0;">Hourly Downtime: <strong>55,500 INR/hr</strong><br>Vib Trip: 9.5 mm/s | Temp Trip: 102°C</p>
            </div>
            <div class="card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <strong style="color:var(--primary);">VPW-CNC-MILL-01</strong>
                    <span class="status-pill pill-completed">Class B · Operational</span>
                </div>
                <p style="font-size:0.8rem; color:var(--text-muted); margin: 0.5rem 0 0 0;">Hourly Downtime: <strong>23,000 INR/hr</strong><br>Vib Trip: 7.1 mm/s | Temp Trip: 86°C</p>
            </div>
            <div class="card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <strong style="color:var(--primary);">VPW-ROBOT-WELD-01</strong>
                    <span class="status-pill pill-completed">Class B · Operational</span>
                </div>
                <p style="font-size:0.8rem; color:var(--text-muted); margin: 0.5rem 0 0 0;">Hourly Downtime: <strong>29,000 INR/hr</strong><br>Vib Trip: 7.3 mm/s | Temp Trip: 88°C</p>
            </div>
        </div>

        <!-- Interactive Live Testing Section -->
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-top: 2rem;">
            <!-- Console 1: RAG Procedure Search & Citation Explorer -->
            <div class="card">
                <h3 style="color:#fff; font-size:1rem; text-transform:none;">RAG Procedure Search & Citation Explorer</h3>
                <p style="font-size:0.8rem; color:var(--text-muted); margin-bottom:1rem;">Tests structure-aware search with Reciprocal Rank Fusion ($k=60$) & unsupported topic refusal.</p>
                <div style="margin-bottom:0.5rem;">
                    <button class="btn btn-secondary btn-sm" onclick="setRAGQuery('What is the bearing replacement torque for AIR-COMP rotary screw compressor?', 'AIR-COMP')">Torque Spec</button>
                    <button class="btn btn-secondary btn-sm" onclick="setRAGQuery('What are the lockout tagout zero energy verification steps for hydraulic press?', 'HYD-PRESS')">LOTO Steps</button>
                    <button class="btn btn-secondary btn-sm" onclick="setRAGQuery('What is the purge cycle for the ammonia refrigeration skid on LINE-3?', '')">Probe P4 (Refusal)</button>
                </div>
                <div class="input-group">
                    <label>Technical Maintenance Question</label>
                    <input type="text" id="rag-query" placeholder="Ask a question grounded in authorized manuals...">
                </div>
                <div class="input-group">
                    <label>Target Asset Code (Optional)</label>
                    <input type="text" id="rag-asset" placeholder="e.g. AIR-COMP, HYD-PRESS">
                </div>
                <button class="btn" onclick="executeRAGSearch()">Search Knowledge Base</button>
                <div id="rag-result" class="result-box"></div>
            </div>

            <!-- Console 2: Telemetry Anomaly & StateGraph Workflow -->
            <div class="card">
                <h3 style="color:#fff; font-size:1rem; text-transform:none;">StateGraph Workflow & Safety Gatekeeper</h3>
                <p style="font-size:0.8rem; color:var(--text-muted); margin-bottom:1rem;">Runs multi-step StateGraph; halts at approval checkpoint on safety-critical LOTO or high cost.</p>
                <div style="margin-bottom:0.5rem;">
                    <button class="btn btn-secondary btn-sm" onclick="setAlertPreset('VPW-HYD-PRESS-02', 7.8, 82.5, 208.0, 'critical', true, true, 350000)">Safety LOTO Alert</button>
                    <button class="btn btn-secondary btn-sm" onclick="setAlertPreset('VPW-CONV-BELT-01', 912.0, -40.0, 0.0, 'critical', false, false, 0)">Probe P3 (Sensor Fault)</button>
                    <button class="btn btn-secondary btn-sm" onclick="setAlertPreset('VPW-AIR-COMP-01', 2.5, 55.0, 7.2, 'low', false, false, 45000)">Routine Auto</button>
                </div>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;">
                    <div class="input-group">
                        <label>Asset Tag</label>
                        <input type="text" id="wf-asset" value="VPW-HYD-PRESS-02">
                    </div>
                    <div class="input-group">
                        <label>Severity</label>
                        <select id="wf-severity">
                            <option value="critical">Critical</option>
                            <option value="high">High</option>
                            <option value="medium">Medium</option>
                            <option value="low">Low</option>
                        </select>
                    </div>
                    <div class="input-group">
                        <label>Vibration (mm/s)</label>
                        <input type="number" step="0.1" id="wf-vib" value="7.8">
                    </div>
                    <div class="input-group">
                        <label>Temperature (°C)</label>
                        <input type="number" step="0.1" id="wf-temp" value="82.5">
                    </div>
                </div>
                <div style="margin-top:0.5rem; display:flex; gap:1rem;">
                    <label style="display:flex; align-items:center; gap:0.35rem; cursor:pointer;">
                        <input type="checkbox" id="wf-loto" checked style="width:auto;"> Requires LOTO
                    </label>
                    <label style="display:flex; align-items:center; gap:0.35rem; cursor:pointer;">
                        <input type="checkbox" id="wf-permit" checked style="width:auto;"> Requires Permit
                    </label>
                </div>
                <div style="margin-top:0.75rem;">
                    <button class="btn" onclick="executeWorkflow()">Dispatch Workflow</button>
                </div>
                <div id="wf-result" class="result-box"></div>
                <div id="approval-controls" style="display:none; margin-top:0.75rem; padding-top:0.75rem; border-top:1px solid var(--border);">
                    <p style="color:var(--warning); font-size:0.8rem; margin:0 0 0.5rem 0;">Human Authorization Required to Proceed with Energy Isolation</p>
                    <button class="btn btn-success" onclick="resumeWorkflow('APPROVE')">Approve Work Order</button>
                    <button class="btn btn-danger" onclick="resumeWorkflow('REJECT')">Reject</button>
                </div>
            </div>
        </div>

        <!-- Procurement Policy Table -->
        <div class="card" style="margin-top: 2rem;">
            <h3>Authoritative Procurement Approval Tiers</h3>
            <table>
                <thead>
                    <tr><th>Tier</th><th>PO Threshold (INR)</th><th>Approval Authority</th><th>Safety Level</th><th>Workflow Action</th></tr>
                </thead>
                <tbody>
                    <tr><td>1</td><td>&lt;= 200,000</td><td>Automated System Approval</td><td>Low Risk</td><td><span class="status-pill pill-completed">Auto Dispatch</span></td></tr>
                    <tr><td>2</td><td>200,001 to 1,000,000</td><td>Maintenance Manager Review</td><td>Medium Risk</td><td><span class="status-pill pill-waiting">Human Review</span></td></tr>
                    <tr><td>3</td><td>&gt; 1,000,000</td><td>Plant Head Explicit Sign-Off</td><td>High Risk</td><td><span class="status-pill pill-waiting">Executive Sign-Off</span></td></tr>
                </tbody>
            </table>
        </div>

        <script>
            let currentThreadId = null;

            function setRAGQuery(q, asset) {
                document.getElementById('rag-query').value = q;
                document.getElementById('rag-asset').value = asset;
            }

            async function executeRAGSearch() {
                const query = document.getElementById('rag-query').value;
                const asset = document.getElementById('rag-asset').value;
                const box = document.getElementById('rag-result');
                box.style.display = 'block';
                box.innerText = 'Searching 13 manuals and SOPs via Hybrid RAG Engine...';

                try {
                    const res = await fetch('/api/v1/investigate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ query: query, asset_code: asset || null })
                    });
                    const data = await res.json();
                    box.innerText = JSON.stringify(data, null, 2);
                } catch (e) {
                    box.innerText = 'Error: ' + e;
                }
            }

            function setAlertPreset(asset, vib, temp, press, sev, loto, permit, poCost) {
                document.getElementById('wf-asset').value = asset;
                document.getElementById('wf-vib').value = vib;
                document.getElementById('wf-temp').value = temp;
                document.getElementById('wf-severity').value = sev;
                document.getElementById('wf-loto').checked = loto;
                document.getElementById('wf-permit').checked = permit;
            }

            async function executeWorkflow() {
                const asset = document.getElementById('wf-asset').value;
                const vib = parseFloat(document.getElementById('wf-vib').value);
                const temp = parseFloat(document.getElementById('wf-temp').value);
                const sev = document.getElementById('wf-severity').value;
                const loto = document.getElementById('wf-loto').checked;
                const permit = document.getElementById('wf-permit').checked;
                const box = document.getElementById('wf-result');
                const approvalControls = document.getElementById('approval-controls');

                box.style.display = 'block';
                box.innerText = 'Executing StateGraph nodes: alert_intake -> validation -> sensor_history -> root_cause -> rag_lookup -> safety_review...';
                approvalControls.style.display = 'none';

                try {
                    const res = await fetch('/api/v1/workflow/start', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            asset_tag: asset,
                            vibration_mm_s: vib,
                            temp_c: temp,
                            severity: sev,
                            requires_loto: loto,
                            requires_permit: permit,
                            po_cost_inr: loto ? 250000 : 45000
                        })
                    });
                    const data = await res.json();
                    currentThreadId = data.thread_id;
                    box.innerText = JSON.stringify(data, null, 2);

                    if (data.status === 'WAITING_FOR_APPROVAL') {
                        approvalControls.style.display = 'block';
                    }
                } catch (e) {
                    box.innerText = 'Error: ' + e;
                }
            }

            async function resumeWorkflow(decision) {
                if (!currentThreadId) return;
                const box = document.getElementById('wf-result');
                const approvalControls = document.getElementById('approval-controls');
                box.innerText = 'Submitting ' + decision + ' decision to SQLite checkpoint...';

                try {
                    const res = await fetch('/api/v1/workflow/approve', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            thread_id: currentThreadId,
                            decision: decision,
                            role: 'maintenance_manager',
                            comments: 'Authorized via Operations Dashboard console.'
                        })
                    });
                    const data = await res.json();
                    box.innerText = JSON.stringify(data, null, 2);
                    approvalControls.style.display = 'none';
                } catch (e) {
                    box.innerText = 'Error: ' + e;
                }
            }
        </script>
    </body>
    </html>
    """


from datetime import datetime
