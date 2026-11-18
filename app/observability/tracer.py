"""PlantGuard Distributed Tracing and Token/Cost Tracking Engine for Milestone 7."""
from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TraceSpan(BaseModel):
    span_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    parent_span_id: Optional[str] = None
    start_time_iso: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time_iso: Optional[str] = None
    duration_ms: float = 0.0
    status: str = "SUCCESS"  # "SUCCESS" or "ERROR"
    error_message: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Trace(BaseModel):
    trace_id: str = Field(default_factory=lambda: f"TR-{uuid.uuid4().hex[:16]}")
    name: str
    start_time_iso: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time_iso: Optional[str] = None
    duration_ms: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    spans: List[TraceSpan] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PlantGuardTracer:
    """Production tracer managing structured spans and persistent trace exports."""

    def __init__(self, trace_dir: Optional[Path] = None):
        self.trace_dir = trace_dir or Path("evaluation") / "traces"
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.active_trace: Optional[Trace] = None
        self._current_span_stack: List[TraceSpan] = []

    def start_trace(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> Trace:
        trace = Trace(name=name, metadata=metadata or {})
        self.active_trace = trace
        self._current_span_stack = []
        return trace

    @contextmanager
    def span(
        self,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
    ):
        parent_id = self._current_span_stack[-1].span_id if self._current_span_stack else None
        span = TraceSpan(
            name=name,
            parent_span_id=parent_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost_usd,
            metadata=metadata or {},
        )
        self._current_span_stack.append(span)
        start_t = time.perf_counter()

        try:
            yield span
        except Exception as e:
            span.status = "ERROR"
            span.error_message = str(e)
            raise
        finally:
            duration_ms = (time.perf_counter() - start_t) * 1000.0
            span.duration_ms = round(duration_ms, 2)
            span.end_time_iso = datetime.now(timezone.utc).isoformat()
            self._current_span_stack.pop()

            if self.active_trace:
                self.active_trace.spans.append(span)
                self.active_trace.total_tokens += span.total_tokens
                self.active_trace.total_cost_usd += span.cost_usd

    def end_trace(self) -> Trace:
        if not self.active_trace:
            raise ValueError("No active trace to end.")

        trace = self.active_trace
        trace.end_time_iso = datetime.now(timezone.utc).isoformat()
        if trace.spans:
            trace.duration_ms = sum(s.duration_ms for s in trace.spans)

        # Export trace to disk
        trace_file = self.trace_dir / f"{trace.trace_id}.json"
        with open(trace_file, "w", encoding="utf-8") as f:
            json.dump(trace.model_dump(), f, indent=2)

        logger.info(f"Exported trace {trace.trace_id} ({len(trace.spans)} spans) to {trace_file}")
        self.active_trace = None
        return trace
