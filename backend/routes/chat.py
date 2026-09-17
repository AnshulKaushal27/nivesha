"""Chat assistant API: streaming SSE, thread history, forget."""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import settings
from llm import chat as chat_graph
from llm.gateway import llm_available

router = APIRouter(prefix="/chat", tags=["chat"])

_THREAD_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_hits: dict[str, deque] = defaultdict(deque)


def _rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "anon"
    now = time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= settings.CHAT_RATE_LIMIT_PER_MIN:
        raise HTTPException(429, "Too many messages. Please wait a minute.")
    q.append(now)


class ChatIn(BaseModel):
    thread_id: str = Field(min_length=8, max_length=64)
    message: str = Field(min_length=1, max_length=4000)
    screen: dict | None = None
    stream: bool = True


def _check_thread(thread_id: str) -> None:
    if not _THREAD_RE.match(thread_id):
        raise HTTPException(400, "Invalid thread id")


@router.post("")
async def chat(body: ChatIn, request: Request):
    _check_thread(body.thread_id)
    if not llm_available():
        raise HTTPException(503, "Chat is unavailable: no LLM API key configured.")
    _rate_limit(request)

    if not body.stream:
        final = None
        async for frame in chat_graph.stream_chat(body.thread_id, body.message, body.screen):
            if frame["type"] in ("done", "error"):
                final = frame
        return final

    async def gen():
        async for frame in chat_graph.stream_chat(body.thread_id, body.message, body.screen):
            yield f"data: {json.dumps(frame, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/{thread_id}/history")
async def get_history(thread_id: str):
    _check_thread(thread_id)
    h = await chat_graph.history(thread_id)
    return {"thread_id": thread_id, **h}


@router.delete("/{thread_id}")
async def delete_thread(thread_id: str):
    _check_thread(thread_id)
    return {"thread_id": thread_id, "forgotten": await chat_graph.forget(thread_id)}
