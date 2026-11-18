"""PlantGuard Circuit Breaker & Resilience Subsystem for Milestone 7."""
from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"        # Normal operations
    OPEN = "OPEN"            # Tripped; reject calls fast or use fallback
    HALF_OPEN = "HALF_OPEN"  # Testing recovery


class CircuitBreakerOpenException(Exception):
    """Raised when an operation is attempted while the circuit is in OPEN state."""
    pass


class CircuitBreaker:
    """Production 3-state Circuit Breaker protecting external LLM and database calls."""

    def __init__(
        self,
        name: str = "default",
        failure_threshold: Optional[int] = None,
        recovery_timeout_seconds: Optional[float] = None,
        half_open_max_calls: Optional[int] = None,
    ):
        settings = get_settings()
        self.name = name
        self.failure_threshold = failure_threshold or settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD
        self.recovery_timeout = recovery_timeout_seconds or settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS
        self.half_open_max_calls = half_open_max_calls or settings.CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.total_trips = 0

    def get_state(self) -> CircuitState:
        """Evaluate and return the current circuit state, checking for timeout transition."""
        if self.state == CircuitState.OPEN and self.last_failure_time is not None:
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.recovery_timeout:
                logger.info(f"CircuitBreaker '{self.name}': Recovery timeout elapsed ({elapsed:.1f}s >= {self.recovery_timeout}s). Transitioning to HALF_OPEN.")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
        return self.state

    def record_success(self) -> None:
        """Record successful invocation."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            logger.info(f"CircuitBreaker '{self.name}': Probe success ({self.success_count}/{self.half_open_max_calls}) in HALF_OPEN.")
            if self.success_count >= self.half_open_max_calls:
                logger.info(f"CircuitBreaker '{self.name}': Probe threshold met. Recovered to CLOSED.")
                self.reset()
        else:
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record failed invocation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        logger.warning(f"CircuitBreaker '{self.name}': Failure recorded ({self.failure_count}/{self.failure_threshold}).")

        if self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN) and self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.total_trips += 1
            logger.error(f"CircuitBreaker '{self.name}': Failure threshold exceeded! Circuit TRIPPED to OPEN.")

    def reset(self) -> None:
        """Manually or automatically reset the breaker to pristine CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None

    def execute(
        self,
        func: Callable[..., T],
        *args: Any,
        fallback_func: Optional[Callable[..., T]] = None,
        **kwargs: Any,
    ) -> T:
        """Execute a function under circuit breaker protection."""
        current_state = self.get_state()

        if current_state == CircuitState.OPEN:
            if fallback_func is not None:
                logger.info(f"CircuitBreaker '{self.name}': OPEN state active. Routing call to fallback handler.")
                return fallback_func(*args, **kwargs)
            raise CircuitBreakerOpenException(
                f"CircuitBreaker '{self.name}' is OPEN. Fast failing to prevent upstream cascade."
            )

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            if fallback_func is not None:
                logger.info(f"CircuitBreaker '{self.name}': Invocation error ({e}). Engaging fallback handler.")
                return fallback_func(*args, **kwargs)
            raise
