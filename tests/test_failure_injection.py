"""Tests for PlantGuard Circuit Breaker, Resilience, and Tracing (Milestone 7 Level 4)."""
import time
import pytest
from app.observability.circuit_breaker import CircuitBreaker, CircuitBreakerOpenException, CircuitState
from app.observability.tracer import PlantGuardTracer


def test_circuit_breaker_transitions_and_fast_fail():
    breaker = CircuitBreaker(
        name="test_service",
        failure_threshold=2,
        recovery_timeout_seconds=0.5,
        half_open_max_calls=1,
    )

    assert breaker.get_state() == CircuitState.CLOSED

    # Failure 1
    breaker.record_failure()
    assert breaker.get_state() == CircuitState.CLOSED
    assert breaker.failure_count == 1

    # Failure 2 -> Trips to OPEN
    breaker.record_failure()
    assert breaker.get_state() == CircuitState.OPEN
    assert breaker.total_trips == 1

    # Under OPEN state: fast-fail or fallback
    with pytest.raises(CircuitBreakerOpenException):
        breaker.execute(lambda: "SHOULD_NOT_EXECUTE")

    # Fallback works without executing underlying failing function
    fallback_result = breaker.execute(lambda: "UNDERLYING", fallback_func=lambda: "FALLBACK_VALUE")
    assert fallback_result == "FALLBACK_VALUE"

    # Sleep recovery timeout
    time.sleep(0.6)
    assert breaker.get_state() == CircuitState.HALF_OPEN

    # Probe success -> Recovers to CLOSED
    probe_res = breaker.execute(lambda: "PROBE_SUCCESS")
    assert probe_res == "PROBE_SUCCESS"
    assert breaker.get_state() == CircuitState.CLOSED


def test_tracer_spans_and_export(tmp_path):
    tracer = PlantGuardTracer(trace_dir=tmp_path)
    trace = tracer.start_trace("TestTrace", metadata={"user": "operator"})

    with tracer.span("step_1", prompt_tokens=50, completion_tokens=20, cost_usd=0.001):
        time.sleep(0.01)

    with tracer.span("step_2", prompt_tokens=30, completion_tokens=10, cost_usd=0.0005):
        time.sleep(0.01)

    ended = tracer.end_trace()
    assert len(ended.spans) == 2
    assert ended.total_tokens == 110
    assert ended.total_cost_usd == 0.0015
    assert (tmp_path / f"{ended.trace_id}.json").exists()
