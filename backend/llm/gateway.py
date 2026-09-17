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
from typing import Any, Type

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from config import settings

PROJECT_TAG = "ai-arena"


def llm_available() -> bool:
    return bool(settings.AICREDITS_API_KEY and settings.AICREDITS_API_KEY != "replace-me")


def tracing_enabled() -> bool:
    return os.getenv("LANGSMITH_TRACING", "").lower() in {"1", "true", "yes"}


def chat(
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    **kwargs: Any,
) -> ChatOpenAI:
    """A plain chat model bound to the gateway."""
    return ChatOpenAI(
        model=model or settings.LLM_MODEL,
        api_key=settings.AICREDITS_API_KEY or "missing",
        base_url=settings.AICREDITS_BASE_URL,
        temperature=settings.LLM_TEMPERATURE if temperature is None else temperature,
        max_tokens=max_tokens,
        timeout=60,
        max_retries=2,
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
    method = method or settings.LLM_STRUCTURED_METHOD
    llm = chat(model=model, **kwargs)
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
