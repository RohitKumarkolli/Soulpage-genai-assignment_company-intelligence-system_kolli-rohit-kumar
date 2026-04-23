"""
tools/base.py
──────────────────────────────────────────────────────────────
Shared utilities for all tools in the system.

Contains:
  • ToolResult        — standardized return envelope
  • safe_tool_call()  — decorator that catches exceptions so
                        a failing tool never crashes the graph
  • retry_request()   — HTTP GET with exponential back-off
──────────────────────────────────────────────────────────────
"""

import time
import functools
from typing import Any, Callable
from dataclasses import dataclass, field, asdict

import requests

from config.settings import settings
from config.logger import logger


# ── Standardized Return Envelope ─────────────────────────────
@dataclass
class ToolResult:
    """
    Every tool in the system returns a ToolResult.
    This gives agents a consistent structure to reason about:
      • Did the tool succeed?
      • What data did it return?
      • If it failed, why?

    The agent's prompt will mention: "If success is False,
    explain the error in your output."
    """
    success: bool
    data: dict = field(default_factory=dict)
    error: str = ""
    source: str = ""          # "live_api" | "mock" | "cache"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def failure(cls, error: str, source: str = "") -> "ToolResult":
        """Convenience constructor for failure cases."""
        return cls(success=False, error=error, source=source)


# ── Safe Tool Call Decorator ──────────────────────────────────
def safe_tool_call(func: Callable) -> Callable:
    """
    Wraps any tool function so that uncaught exceptions are
    caught and returned as a ToolResult.failure() instead of
    crashing the LangGraph node.

    Usage:
        @safe_tool_call
        def my_tool(company: str) -> dict:
            ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> dict:
        try:
            result = func(*args, **kwargs)
            # Functions may return ToolResult or plain dict — normalize
            if isinstance(result, ToolResult):
                return result.to_dict()
            return result
        except Exception as e:
            logger.error(f"Tool '{func.__name__}' failed: {e}")
            return ToolResult.failure(
                error=f"{type(e).__name__}: {str(e)}",
                source="error"
            ).to_dict()
    return wrapper


# ── HTTP Request with Retry ───────────────────────────────────
def retry_request(
    url: str,
    params: dict = None,
    max_retries: int = None,
    timeout: int = None,
) -> requests.Response:
    """
    Makes a GET request with exponential back-off on failure.

    Args:
        url:         Full URL to request
        params:      Query string parameters
        max_retries: Override settings.max_retries
        timeout:     Override settings.request_timeout

    Returns:
        requests.Response on success

    Raises:
        requests.RequestException after all retries exhausted
    """
    max_retries = max_retries or settings.max_retries
    timeout = timeout or settings.request_timeout

    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(f"HTTP GET {url} (attempt {attempt}/{max_retries})")
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()   # Raises on 4xx / 5xx
            return response

        except requests.RequestException as e:
            if attempt == max_retries:
                logger.error(f"All {max_retries} attempts failed for {url}: {e}")
                raise
            # Exponential back-off: 1s, 2s, 4s ...
            wait = 2 ** (attempt - 1)
            logger.warning(f"Request failed (attempt {attempt}), retrying in {wait}s...")
            time.sleep(wait)