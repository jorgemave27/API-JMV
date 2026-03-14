from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import pybreaker

logger = logging.getLogger(__name__)


class LoggingCircuitBreakerListener(pybreaker.CircuitBreakerListener):
    """
    Listener para loguear cambios de estado del circuit breaker.
    """

    def state_change(
        self,
        cb: pybreaker.CircuitBreaker,
        old_state: pybreaker.CircuitBreakerState | None,
        new_state: pybreaker.CircuitBreakerState,
    ) -> None:
        old_name = old_state.name if old_state else "UNKNOWN"
        new_name = new_state.name if new_state else "UNKNOWN"

        logger.warning(
            "Circuit breaker state change | name=%s | from=%s | to=%s | fail_counter=%s",
            cb.name,
            old_name,
            new_name,
            cb.fail_counter,
        )

    def failure(
        self,
        cb: pybreaker.CircuitBreaker,
        exc: BaseException,
    ) -> None:
        logger.error(
            "Circuit breaker failure | name=%s | fail_counter=%s | error=%s",
            cb.name,
            cb.fail_counter,
            repr(exc),
        )

    def success(self, cb: pybreaker.CircuitBreaker) -> None:
        logger.info(
            "Circuit breaker success | name=%s | fail_counter=%s | state=%s",
            cb.name,
            cb.fail_counter,
            cb.current_state,
        )


_listeners = [LoggingCircuitBreakerListener()]

tipo_cambio_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    listeners=_listeners,
    name="tipo_cambio",
)

webhooks_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    listeners=_listeners,
    name="webhooks",
)

BREAKERS: dict[str, pybreaker.CircuitBreaker] = {
    "tipo_cambio": tipo_cambio_breaker,
    "webhooks": webhooks_breaker,
}


def get_breaker(name: str) -> pybreaker.CircuitBreaker:
    breaker = BREAKERS.get(name)
    if not breaker:
        raise ValueError(f"Circuit breaker no registrado: {name}")
    return breaker


def breaker_state_payload(cb: pybreaker.CircuitBreaker) -> dict[str, Any]:
    return {
        "name": cb.name,
        "state": cb.current_state,
        "fail_counter": cb.fail_counter,
        "fail_max": cb.fail_max,
        "reset_timeout": cb.reset_timeout,
        "success_threshold": getattr(cb, "success_threshold", 1),
    }


def get_all_breakers_status() -> dict[str, dict[str, Any]]:
    return {name: breaker_state_payload(cb) for name, cb in BREAKERS.items()}


def execute_with_breaker(
    breaker_name: str,
    func: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Any:
    breaker = get_breaker(breaker_name)
    return breaker.call(func, *args, **kwargs)