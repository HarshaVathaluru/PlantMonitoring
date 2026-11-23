"""Tests for Milestone 7: Distributed Tracing, Circuit Breaker & Resilience."""
import json
import time
import pytest
from pathlib import Path
from app.observability.tracer import PlantGuardTracer
from app.observability.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenException,
    CircuitState,
)


def test_tracer_spans_tokens_and_file_export(tmp_path):
    tracer = PlantGuardTracer(trace_dir=tmp_path)
    trace = tracer.start_trace("maintenance_investigation", metadata={"asset": "VPW-AIR-COMP-01"})

    with tracer.span("sensor_lookup", prompt_tokens=100, completion_tokens=50, cost_usd=0.0001) as s1:
        time.sleep(0.01)
        assert s1.name == "sensor_lookup"

    with tracer.span("rag_search", prompt_tokens=200, completion_tokens=80, cost_usd=0.0002) as s2:
        time.sleep(0.01)

    completed_trace = tracer.end_trace()

    assert completed_trace.trace_id == trace.trace_id
    assert len(completed_trace.spans) == 2
    assert completed_trace.total_tokens == 430
    assert completed_trace.total_cost_usd == pytest.approx(0.0003)
    assert completed_trace.duration_ms > 0

    # Verify JSON export
    exported_file = tmp_path / f"{completed_trace.trace_id}.json"
    assert exported_file.exists()
    data = json.loads(exported_file.read_text(encoding="utf-8"))
    assert data["trace_id"] == completed_trace.trace_id
    assert len(data["spans"]) == 2


def test_tracer_records_span_errors(tmp_path):
    tracer = PlantGuardTracer(trace_dir=tmp_path)
    tracer.start_trace("error_trace")

    with pytest.raises(ValueError):
        with tracer.span("faulty_step"):
            raise ValueError("Upstream sensor database timeout")

    t = tracer.end_trace()
    assert len(t.spans) == 1
    assert t.spans[0].status == "ERROR"
    assert "Upstream sensor database timeout" in t.spans[0].error_message


def test_tracer_attaches_real_llm_usage_to_active_span(tmp_path):
    from types import SimpleNamespace

    tracer = PlantGuardTracer(trace_dir=tmp_path)
    tracer.start_trace("llm_trace")
    with tracer.span("rag_answer") as span:
        tracer.record_llm_usage(SimpleNamespace(
            provider="gemini", model="test-model", used_fallback=False,
            prompt_tokens=12, completion_tokens=7, total_tokens=19, cost_estimate_usd=0.001,
        ), {"attempt": 2})
    trace = tracer.end_trace()
    assert span.total_tokens == 19
    assert trace.total_tokens == 19
    assert trace.total_cost_usd == pytest.approx(0.001)
    assert span.metadata["llm_calls"][0]["attempt"] == 2
    assert span.metadata["llm_calls"][0]["provider"] == "gemini"


def test_circuit_breaker_transitions_and_fast_fail():
    cb = CircuitBreaker(
        name="test_llm",
        failure_threshold=3,
        recovery_timeout_seconds=0.1,  # Short timeout for testing
        half_open_max_calls=2,
    )

    def failing_upstream():
        raise ConnectionError("Remote API unavailable")

    def healthy_upstream():
        return "SUCCESSFUL_PAYLOAD"

    # 1. Starts CLOSED
    assert cb.get_state() == CircuitState.CLOSED

    # 2. Trigger failures until threshold
    for _ in range(3):
        with pytest.raises(ConnectionError):
            cb.execute(failing_upstream)

    # 3. Circuit is now OPEN
    assert cb.get_state() == CircuitState.OPEN

    # 4. Fast-failing without calling upstream
    with pytest.raises(CircuitBreakerOpenException):
        cb.execute(failing_upstream)

    # 5. Fallback handler engages gracefully during OPEN state
    fallback_res = cb.execute(
        failing_upstream,
        fallback_func=lambda: "FALLBACK_CACHED_RESPONSE",
    )
    assert fallback_res == "FALLBACK_CACHED_RESPONSE"

    # 6. Wait for recovery timeout -> transitions to HALF_OPEN
    time.sleep(0.15)
    assert cb.get_state() == CircuitState.HALF_OPEN

    # 7. Two successful probe calls in HALF_OPEN restore to CLOSED
    res1 = cb.execute(healthy_upstream)
    assert res1 == "SUCCESSFUL_PAYLOAD"
    assert cb.get_state() == CircuitState.HALF_OPEN

    res2 = cb.execute(healthy_upstream)
    assert res2 == "SUCCESSFUL_PAYLOAD"
    assert cb.get_state() == CircuitState.CLOSED


def test_failure_injection_reliability_comparison():
    """
    Quantitatively compares:
    - Without Circuit Breaker / Fallback: 100% crash rate
    - With Circuit Breaker & Fallback: 100% availability / graceful degradation
    """
    total_calls = 10

    def flaky_service():
        raise TimeoutError("504 Gateway Timeout")

    def local_rule_fallback():
        return {"status": "DEGRADED", "data": "CACHED_DIAGNOSTIC_ESTIMATE"}

    # Without circuit breaker: all calls fail
    crashes = 0
    for _ in range(total_calls):
        try:
            flaky_service()
        except TimeoutError:
            crashes += 1
    unprotected_availability = (total_calls - crashes) / total_calls
    assert unprotected_availability == 0.0

    # With circuit breaker and fallback: all calls return graceful degraded responses
    cb = CircuitBreaker(name="resilience_eval", failure_threshold=2, recovery_timeout_seconds=5.0)
    successes = 0
    for _ in range(total_calls):
        result = cb.execute(flaky_service, fallback_func=local_rule_fallback)
        if result["status"] == "DEGRADED":
            successes += 1

    protected_availability = successes / total_calls
    assert protected_availability == 1.0
    assert cb.get_state() == CircuitState.OPEN


def test_fastapi_request_level_tracing_and_kpis(tmp_path):
    from app.main import (
        IntakeRequest,
        InvestigateRequest,
        health_check,
        ingest_telemetry_alert,
        investigate_technical_query,
        tracer,
    )

    # Temporarily set trace_dir to tmp_path
    original_trace_dir = tracer.trace_dir
    tracer.trace_dir = tmp_path
    try:
        # 1. Health check call
        resp_health = health_check()
        assert resp_health["status"] == "HEALTHY"

        # 2. Ingest telemetry call
        req_intake = IntakeRequest(
            asset_tag="VPW-AIR-COMP-01",
            vibration_mm_s=4.5,
            temp_c=62.0,
            severity="medium",
        )
        resp_ingest = ingest_telemetry_alert(req_intake)
        assert resp_ingest["asset_tag"] == "VPW-AIR-COMP-01"

        # 3. Investigate query call
        req_inv = InvestigateRequest(query="What is the trip threshold for vibration on 400-Tonne Hydraulic Press?")
        resp_inv = investigate_technical_query(req_inv)
        assert resp_inv["is_supported"] is True

        # Verify that actual request trace files were generated
        trace_files = list(tmp_path.glob("TR-*.json"))
        assert len(trace_files) >= 2, f"Expected at least 2 traces, found {len(trace_files)}"

        # Verify trace structure
        sample_file = trace_files[0]
        data = json.loads(sample_file.read_text(encoding="utf-8"))
        assert "trace_id" in data
        assert "spans" in data
        assert len(data["spans"]) >= 1
        assert any("Validation_And_Safety" in s["name"] or "RAG" in s["name"] for s in data["spans"])

        # Verify dynamic KPI computation
        kpis = tracer.compute_dynamic_kpis()
        assert "metrics" in kpis
        assert kpis["total_recorded_traces"] >= 2
        assert kpis["metrics"]["uptime_percent"] > 99.0
        assert "intake_p50_latency_ms" in kpis["metrics"]
    finally:
        tracer.trace_dir = original_trace_dir


