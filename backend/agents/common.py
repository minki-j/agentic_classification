import os
from typing import Optional
from langgraph.types import RetryPolicy
from langgraph.checkpoint.memory import MemorySaver


# ===========================================
#            LangGraph Configuration
# ===========================================
def get_checkpointer() -> Optional[MemorySaver]:
    """
    Returns a MemorySaver checkpointer if not running in LangGraph Studio.

    LangGraph Studio doesn't support checkpointers, so we disable it when
    the LANGGRAPH_STUDIO environment variable is set to 'true'.

    Can be configured via:
    1. Environment variable: LANGGRAPH_STUDIO=true
    2. Settings configuration in app.core.config

    Returns:
        MemorySaver instance if not in LangGraph Studio, None otherwise
    """
    # Check environment variable first (takes precedence)
    if os.getenv("LANGGRAPH_STUDIO", "false").lower() == "true":
        return None

    # Try to use app settings if available (for when running as API)
    try:
        from app.core.config import settings

        if settings.LANGGRAPH_STUDIO:
            return None
    except ImportError:
        # If app module is not available (e.g., running agent standalone),
        # just use environment variable
        pass

    return MemorySaver()


# ===========================================
#                 Retry Policy
# ===========================================
def retry_on(exc: Exception) -> bool:
    print(f"[Retry policy captured an exception]\n{exc}\n")
    import httpx
    import requests

    if isinstance(exc, ConnectionError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return 500 <= exc.response.status_code < 600
    if isinstance(exc, requests.HTTPError):
        return 500 <= exc.response.status_code < 600 if exc.response else True
    if isinstance(
        exc,
        (
            ValueError,
            TypeError,
            ArithmeticError,
            ImportError,
            LookupError,
            NameError,
            SyntaxError,
            RuntimeError,
            ReferenceError,
            StopIteration,
            StopAsyncIteration,
            OSError,
        ),
    ):
        return False
    return True


# Retry Policy
retry_policy = RetryPolicy(
    initial_interval=0.5,
    backoff_factor=2.0,
    max_interval=128.0,
    max_attempts=3,
    jitter=True,
    retry_on=retry_on,
)
