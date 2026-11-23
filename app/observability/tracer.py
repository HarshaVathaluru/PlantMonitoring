"""PlantGuard Distributed Tracing and Token/Cost Tracking Engine for Milestone 7."""
from __future__ import annotations

import contextvars
import json
import logging
import statistics
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Context variables for async/thread request-isolated tracing
_active_trace_cv: contextvars.ContextVar[Optional[Trace]] = contextvars.ContextVar("active_trace", default=None)
_current_span_stack_cv: contextvars.ContextVar[List[TraceSpan]] = contextvars.ContextVar("current_span_stack", default=[])


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
    session_id: Optional[str] = None
    user_id: Optional[str] = None
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

    @property
    def active_trace(self) -> Optional[Trace]:
        return _active_trace_cv.get()

    @active_trace.setter
    def active_trace(self, val: Optional[Trace]):
        _active_trace_cv.set(val)

    @property
    def _current_span_stack(self) -> List[TraceSpan]:
        val = _current_span_stack_cv.get()
        if val is None:
            val = []
            _current_span_stack_cv.set(val)
        return val

    def start_trace(
        self,
        name: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Trace:
        trace = Trace(
            name=name,
            session_id=session_id or f"SESS-{uuid.uuid4().hex[:8]}",
            user_id=user_id or "operator_system",
            metadata=metadata or {},
        )
        self.active_trace = trace
        _current_span_stack_cv.set([])
        return trace

    @contextmanager
    def trace_request(
        self,
        name: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Context manager to start a request root trace, nest spans, and automatically end/export it."""
        trace = self.start_trace(name=name, session_id=session_id, user_id=user_id, metadata=metadata)
        try:
            yield trace
        finally:
            try:
                self.end_trace()
            except Exception as e:
                logger.warning(f"Error ending trace {trace.trace_id}: {e}")

    @contextmanager
    def span(
        self,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
    ):
        stack = self._current_span_stack
        parent_id = stack[-1].span_id if stack else None
        span = TraceSpan(
            name=name,
            parent_span_id=parent_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost_usd,
            metadata=metadata or {},
        )
        stack.append(span)
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
            if stack:
                stack.pop()

            act = self.active_trace
            if act:
                act.spans.append(span)
                act.total_tokens += span.total_tokens
                act.total_cost_usd += span.cost_usd

    def end_trace(self) -> Trace:
        act = self.active_trace
        if not act:
            raise ValueError("No active trace to end.")

        act.end_time_iso = datetime.now(timezone.utc).isoformat()
        if act.spans:
            act.duration_ms = round(sum(s.duration_ms for s in act.spans), 2)

        # Export trace to disk
        trace_file = self.trace_dir / f"{act.trace_id}.json"
        with open(trace_file, "w", encoding="utf-8") as f:
            json.dump(act.model_dump(), f, indent=2)

        logger.info(f"Exported trace {act.trace_id} ({len(act.spans)} spans) to {trace_file}")
        self.active_trace = None
        _current_span_stack_cv.set([])
        return act

    def record_llm_usage(self, response: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Attach actual provider usage to the active span without storing prompt text."""
        trace = self.active_trace
        if trace is None:
            return
        stack = self._current_span_stack
        usage = {
            "provider": getattr(response, "provider", "unknown"),
            "model": getattr(response, "model", "unknown"),
            "used_fallback": bool(getattr(response, "used_fallback", False)),
            **(metadata or {}),
        }
        if stack:
            span = stack[-1]
            prompt_tokens = int(getattr(response, "prompt_tokens", 0) or 0)
            completion_tokens = int(getattr(response, "completion_tokens", 0) or 0)
            reported_total = int(getattr(response, "total_tokens", 0) or 0)
            if reported_total and prompt_tokens + completion_tokens == 0:
                completion_tokens = reported_total
            span.prompt_tokens += prompt_tokens
            span.completion_tokens += completion_tokens
            span.total_tokens = span.prompt_tokens + span.completion_tokens
            span.cost_usd += float(getattr(response, "cost_estimate_usd", 0.0) or 0.0)
            span.metadata.setdefault("llm_calls", []).append(usage)
        else:
            trace.total_tokens += int(getattr(response, "total_tokens", 0) or 0)
            trace.total_cost_usd += float(getattr(response, "cost_estimate_usd", 0.0) or 0.0)
            trace.metadata.setdefault("llm_calls", []).append(usage)

    def compute_dynamic_kpis(self) -> Dict[str, Any]:
        """Aggregate trace performance metrics across all recorded disk traces."""
        traces: List[Dict[str, Any]] = []
        if self.trace_dir.exists():
            for f in self.trace_dir.glob("*.json"):
                try:
                    with open(f, "r", encoding="utf-8") as fp:
                        traces.append(json.load(fp))
                except Exception:
                    pass

        intake_latencies = []
        rag_latencies = []
        total_tokens_list = []
        costs = []
        successful_spans = 0
        total_spans = 0

        for t in traces:
            if int(t.get("total_tokens", 0) or 0) > 0:
                total_tokens_list.append(t.get("total_tokens", 0))
                costs.append(t.get("total_cost_usd", 0.0))
            for s in t.get("spans", []):
                total_spans += 1
                if s.get("status") == "SUCCESS":
                    successful_spans += 1
                name = s.get("name", "")
                dur = s.get("duration_ms", 0.0)
                if "Ingest" in name or "intake" in name.lower():
                    intake_latencies.append(dur)
                elif "RAG" in name or "investigate" in name.lower() or "answer" in name.lower():
                    rag_latencies.append(dur)

        def pct(vals: List[float], p: float) -> Optional[float]:
            if not vals:
                return None
            s = sorted(vals)
            k = (len(s) - 1) * (p / 100.0)
            f = int(k)
            c = min(f + 1, len(s) - 1)
            d0 = s[f] * (c - k)
            d1 = s[c] * (k - f)
            return round(d0 + d1, 2)

        p50_intake = pct(intake_latencies, 50)
        p95_intake = pct(intake_latencies, 95)
        p99_intake = pct(intake_latencies, 99)
        p50_rag = pct(rag_latencies, 50)
        p95_rag = pct(rag_latencies, 95)
        avg_cost = round(statistics.mean(costs), 7) if costs else None
        success_rate = round(successful_spans / total_spans, 4) if total_spans else None
        uptime_pct = round((successful_spans / total_spans * 100.0), 2) if total_spans else None
        breaker_trips = sum(
            int(t.get("metadata", {}).get("circuit_breaker_trip_count", 0) or 0)
            for t in traces
        ) + sum(
            1 for t in traces if not t.get("metadata", {}).get("circuit_breaker_trip_count") and any(
                s.get("metadata", {}).get("circuit_breaker_state") == "OPEN"
                for s in t.get("spans", [])
            )
        )
        breaker_runs = [t for t in traces if int(t.get("metadata", {}).get("circuit_breaker_trip_count", 0) or 0) > 0]
        recovery_rate = round(
            sum(1 for t in breaker_runs if t.get("metadata", {}).get("circuit_breaker_recovered") is True) / len(breaker_runs), 4
        ) if breaker_runs else None
        targets = {"max_p95_latency_ms": 250.0, "min_success_rate": 0.99, "loto_bypass_leakage_tolerance": 0.0}
        enough_data = bool(total_spans and (intake_latencies or rag_latencies))
        latency_ok = (not rag_latencies or p95_rag <= targets["max_p95_latency_ms"]) and (not intake_latencies or p95_intake <= targets["max_p95_latency_ms"])
        success_ok = success_rate is not None and success_rate >= targets["min_success_rate"]

        return {
            "benchmark_date": datetime.now(timezone.utc).date().isoformat(),
            "total_recorded_traces": len(traces),
            "total_recorded_spans": total_spans,
            "sample_counts": {"intake_latency": len(intake_latencies), "rag_latency": len(rag_latencies), "span_status": total_spans},
            "metrics": {
                "uptime_percent": uptime_pct,
                "intake_p50_latency_ms": p50_intake,
                "intake_p95_latency_ms": p95_intake,
                "intake_p99_latency_ms": p99_intake,
                "rag_query_p50_latency_ms": p50_rag,
                "rag_query_p95_latency_ms": p95_rag,
                "token_cost_per_investigation_usd": avg_cost,
                "workflow_step_execution_success_rate": success_rate,
                "circuit_breaker_trip_count": breaker_trips,
                "circuit_breaker_recovery_success_rate": recovery_rate,
                "unauthorized_bypass_interception_rate": None,
            },
            "target_thresholds": targets,
            "target_evaluations": {
                "measured_latency_threshold": "PASS" if enough_data and latency_ok else "FAIL" if enough_data else "INSUFFICIENT_DATA",
                "measured_success_rate_threshold": "PASS" if success_ok else "FAIL" if success_rate is not None else "INSUFFICIENT_DATA",
                "loto_bypass_leakage_threshold": "NOT_MEASURED",
            },
            "compliance_status": "INSUFFICIENT_DATA" if not enough_data else ("MEASURED_TARGETS_WITHIN" if latency_ok and success_ok else "MEASURED_TARGETS_MISSED"),
        }

    def export_kpi_metrics(self, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """Compute and persist aggregated KPI metrics to evaluation/kpi_metrics.json."""
        kpis = self.compute_dynamic_kpis()
        target = output_path or (Path("evaluation") / "kpi_metrics.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(kpis, f, indent=2)
        return kpis
