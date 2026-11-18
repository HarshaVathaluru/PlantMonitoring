"""PlantGuard Typed Workflow State for Milestone 5."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkflowState(BaseModel):
    """Authoritative typed state for the PlantGuard multi-step maintenance graph."""
    thread_id: str
    current_node: str = "alert_intake"
    status: str = "INITIALIZED"  # INITIALIZED, PROCESSING, WAITING_FOR_APPROVAL, APPROVED, REJECTED, COMPLETED, FAILED
    
    # Input & Validation
    raw_alert: Dict[str, Any] = Field(default_factory=dict)
    maintenance_event: Optional[Dict[str, Any]] = None
    validation_passed: bool = False
    
    # Telemetry & Diagnostics
    sensor_history: List[Dict[str, Any]] = Field(default_factory=list)
    root_cause_analysis: Optional[str] = None
    
    # RAG Grounding
    rag_citations: List[str] = Field(default_factory=list)
    rag_procedure: Optional[str] = None
    
    # Action Plan & Scheduling
    recommendation: Optional[Dict[str, Any]] = None
    spare_parts_checked: List[Dict[str, Any]] = Field(default_factory=list)
    technician_scheduled: Optional[Dict[str, Any]] = None
    estimated_downtime_cost: Optional[float] = None
    
    # Safety & Human-in-the-Loop Routing
    safety_review: Optional[Dict[str, Any]] = None
    requires_human_approval: bool = False
    approval_reason: Optional[str] = None
    approval_decision: Optional[str] = None  # None, APPROVE, REJECT
    approval_role: Optional[str] = None
    approver_role: Optional[str] = None
    approver_comments: Optional[str] = None
    approval_comments: Optional[str] = None
    
    # Execution & Audit
    execution_result: Optional[Dict[str, Any]] = None
    execution_completed: bool = False
    errors: List[str] = Field(default_factory=list)
    
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
