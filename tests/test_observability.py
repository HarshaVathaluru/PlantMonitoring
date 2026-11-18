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
