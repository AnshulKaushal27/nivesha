"""
The single door to every LLM in the project.

Built on LangChain's ChatOpenAI against the OpenAI-compatible gateway, so the
same code can address GPT, Gemini, Mistral, DeepSeek, Groq-hosted models, etc.
by model id. LangGraph graphs call `structured()` and never a provider SDK.

Monitoring: LangSmith tracing is switched on purely by environment variables
(LANGSMITH_TRACING=true, LANGSMITH_API_KEY, LANGSMITH_PROJECT). Every graph
invocation passes a run_name and tags so traces group by feature.
"""

from __future__ import annotations

import os
import warnings
from typing import Any, Type

import httpx
from langchain_openai import ChatOpenAI

# langchain-openai serialises structured-output responses with a `parsed` field pydantic
# did not expect; harmless, but it prints a warning per call.
warnings.filterwarnings("ignore", message="Pydantic serializer warnings", category=UserWarning)
from pydantic import BaseModel

from config import settings

PROJECT_TAG = "nivesha"

# ── Failover between the primary gateway and an optional fallback provider ──
import time as _time

_primary_down_until = 0.0


def fallback_configured() -> bool:
    return bool(settings.LLM_FALLBACK_BASE_URL and settings.LLM_FALLBACK_API_KEY and settings.LLM_FALLBACK_MODEL)


def mark_primary_down() -> None:
    """Called when the primary gateway fails all retries; routes calls to the fallback for a while."""
    global _primary_down_until
    _primary_down_until = _time.monotonic() + settings.LLM_FAILOVER_SECONDS


def mark_primary_up() -> None:
    global _primary_down_until
    _primary_down_until = 0.0


def using_fallback() -> bool:
    return fallback_configured() and _time.monotonic() < _primary_down_until


def provider_status() -> dict:
    return {"primary": settings.AICREDITS_BASE_URL, "fallback_configured": fallback_configured(),
            "on_fallback": using_fallback(), "fallback_model": settings.LLM_FALLBACK_MODEL or None,
            "failover_ends_in_s": max(0, int(_primary_down_until - _time.monotonic())) if using_fallback() else 0}


def llm_available() -> bool:
    return bool(settings.AICREDITS_API_KEY and settings.AICREDITS_API_KEY != "replace-me") or fallback_configured()


def tracing_enabled() -> bool:
    return os.getenv("LANGSMITH_TRACING", "").lower() in {"1", "true", "yes"}


def chat(
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    max_retries: int = 2,
    read_timeout: float = 60.0,
    **kwargs: Any,
) -> ChatOpenAI:
    """A plain chat model bound to the gateway. Connect failures surface in 5 s, not 10 s+.
    Every call is metered (tokens, estimated cost) by ops.llm_usage."""
    from ops.llm_usage import recorder
    callbacks = list(kwargs.pop("callbacks", []) or []) + [recorder]
    if using_fallback():
        # every call goes to the fallback provider with its single model until the failover window ends
        model, api_key, base_url = settings.LLM_FALLBACK_MODEL, settings.LLM_FALLBACK_API_KEY, settings.LLM_FALLBACK_BASE_URL
    else:
        model, api_key, base_url = model or settings.LLM_MODEL, settings.AICREDITS_API_KEY or "missing", settings.AICREDITS_BASE_URL
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=settings.LLM_TEMPERATURE if temperature is None else temperature,
        max_tokens=max_tokens,
        timeout=httpx.Timeout(read_timeout, connect=5.0),
        max_retries=max_retries,
        callbacks=callbacks,
        **kwargs,
    )


def structured(
    schema: Type[BaseModel],
    model: str | None = None,
    method: str | None = None,
    **kwargs: Any,
):
    """
    A runnable that returns an instance of `schema`, never free text.

    method: json_schema (strict, preferred) | function_calling | json_mode.
    Set LLM_STRUCTURED_METHOD=function_calling for a gateway or model that
    lacks strict JSON-schema support.
    """
    method = method or (settings.LLM_FALLBACK_STRUCTURED_METHOD if using_fallback() else settings.LLM_STRUCTURED_METHOD)
    llm = chat(model=model, **kwargs)   # kwargs may carry max_retries / read_timeout
    opts: dict[str, Any] = {"method": method}
    if method == "json_schema":
        opts["strict"] = True
    return llm.with_structured_output(schema, **opts)


def run_config(run_name: str, tags: list[str] | None = None, **metadata: Any) -> dict:
    """Config dict for graph.invoke(...) so LangSmith traces are searchable."""
    return {
        "run_name": run_name,
        "tags": [PROJECT_TAG, *(tags or [])],
        "metadata": metadata,
    }
