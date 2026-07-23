import asyncio
import logging
import os
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional

import logfire
from langchain_openai import ChatOpenAI
from src.app.core.config import settings

logger = logging.getLogger("LLMCircuitBreaker")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip('"')


class CircuitState(Enum):
    CLOSED = "CLOSED"  # Normal operation: Primary model (OpenAI) is active
    OPEN = "OPEN"  # Failover active: Bypasses primary and calls fallback (Groq) directly
    HALF_OPEN = (
        "HALF_OPEN"  # Recovery testing: Sends 1 probe call to primary to test recovery
    )


class LLMCircuitBreaker:
    """
    High-availability LLM Circuit Breaker pattern for enterprise resilience.
    Guarantees 0-downtime failover from primary LLM (OpenAI) to secondary LLM (Groq)
    when API limits, 5xx server errors, or timeouts occur.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
        provider_name: str = "OpenAI",
        fallback_name: str = "Groq",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.provider_name = provider_name
        self.fallback_name = fallback_name

        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.last_state_change: float = time.time()
        self.last_failure_time: float = 0.0

        # Fallback Model initialized using OpenAI-compatible Groq API endpoint
        self._fallback_llm: Optional[ChatOpenAI] = None

    def get_fallback_llm(self) -> ChatOpenAI:
        if self._fallback_llm is None and GROQ_API_KEY:
            try:
                self._fallback_llm = ChatOpenAI(
                    model="llama-3.3-70b-versatile",
                    openai_api_base="https://api.groq.com/openai/v1",
                    openai_api_key=GROQ_API_KEY,
                    temperature=0.2,
                )
            except Exception as e:
                logger.error(f"Failed to initialize Groq fallback LLM: {e}")
        return self._fallback_llm

    def _log_state_change(self, new_state: CircuitState, reason: str):
        self.state = new_state
        self.last_state_change = time.time()
        msg = f"[CIRCUIT BREAKER {new_state.value}] {reason}"
        print(f"\033[93m{msg}\033[0m")
        logger.warning(msg)
        try:
            logfire.warn(
                "CIRCUIT BREAKER STATE CHANGE: state={new_state} provider={provider} reason={reason}",
                new_state=new_state.value,
                provider=self.provider_name,
                reason=reason,
            )
        except Exception:
            pass

    async def execute(
        self,
        primary_fn: Callable[[], Any],
        fallback_fn: Callable[[], Any],
        context_name: str = "LLM Call",
    ) -> Any:
        now = time.time()

        # ─── 1. STATE == OPEN: Check Cooldown Window ──────────────────────────
        if self.state == CircuitState.OPEN:
            elapsed = now - self.last_state_change
            if elapsed < self.recovery_timeout:
                msg = f"Skipping {self.provider_name} (Circuit OPEN, {self.recovery_timeout - elapsed:.1f}s cooldown remaining) -> Running {self.fallback_name} Fallback for {context_name}"
                logger.info(msg)
                print(f"\033[94m[CIRCUIT BREAKER FAILOVER] {msg}\033[0m")
                return await self._run_fallback(fallback_fn, context_name)
            else:
                self._log_state_change(
                    CircuitState.HALF_OPEN,
                    f"Cooldown window ({self.recovery_timeout}s) expired. Testing {self.provider_name} recovery...",
                )

        # ─── 2. STATE == CLOSED or HALF_OPEN: Execute Primary ─────────────────
        try:
            # Execute primary function with timeout limit (10s) to prevent hanging
            result = await asyncio.wait_for(primary_fn(), timeout=10.0)

            # On Success: Reset failure count and close circuit if half-open
            if self.state == CircuitState.HALF_OPEN:
                self.failure_count = 0
                self._log_state_change(
                    CircuitState.CLOSED,
                    f"Probe call to {self.provider_name} SUCCEEDED! Resetting circuit to CLOSED.",
                )
            elif self.failure_count > 0:
                self.failure_count = 0

            return result

        except Exception as primary_error:
            self.failure_count += 1
            self.last_failure_time = time.time()
            err_msg = str(primary_error) or type(primary_error).__name__

            logger.error(
                f"Primary {self.provider_name} failed ({self.failure_count}/{self.failure_threshold}) during {context_name}: {err_msg}"
            )

            # Check if threshold reached or if we were in HALF_OPEN testing mode
            if (
                self.failure_count >= self.failure_threshold
                or self.state == CircuitState.HALF_OPEN
            ):
                self._log_state_change(
                    CircuitState.OPEN,
                    f"Threshold reached ({self.failure_count} failures). Tripping circuit to OPEN for {self.recovery_timeout}s! Routing 100% traffic to {self.fallback_name}.",
                )

            # Instantly execute fallback model without failing the request
            return await self._run_fallback(fallback_fn, context_name, primary_error)

    async def _run_fallback(
        self,
        fallback_fn: Callable[[], Any],
        context_name: str,
        primary_error: Optional[Exception] = None,
    ) -> Any:
        try:
            logger.info(
                f"Executing {self.fallback_name} fallback for {context_name}..."
            )
            result = await fallback_fn()
            try:
                logfire.info(
                    "CIRCUIT BREAKER FALLBACK SUCCESS: context={context} fallback={fallback}",
                    context=context_name,
                    fallback=self.fallback_name,
                )
            except Exception:
                pass
            return result
        except Exception as fallback_error:
            logger.critical(
                f"Both Primary ({self.provider_name}) AND Fallback ({self.fallback_name}) failed for {context_name}! Primary Error: {primary_error}, Fallback Error: {fallback_error}"
            )
            raise fallback_error


# Singleton instance for LLM calls across agent graphs
llm_circuit_breaker = LLMCircuitBreaker()
