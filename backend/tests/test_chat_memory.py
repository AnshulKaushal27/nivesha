"""Compression and resilience logic of the chat graph, without any model calls."""

from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage

import llm.chat as chat
from llm.chat import _cut_index, _is_transient, _trim, compress


def _thread(n_turns: int, with_tools: bool = False):
    msgs = []
    for i in range(n_turns):
        msgs.append(HumanMessage(content=f"question {i}", id=f"h{i}"))
        if with_tools and i % 2 == 0:
            msgs.append(AIMessage(content="", tool_calls=[{"name": "list_ranks", "args": {}, "id": f"c{i}"}], id=f"a{i}c"))
            msgs.append(ToolMessage(content="{...}", tool_call_id=f"c{i}", name="list_ranks", id=f"t{i}"))
        msgs.append(AIMessage(content=f"answer {i}", id=f"a{i}"))
    return msgs


def test_cut_index_starts_kept_part_at_a_human_turn():
    msgs = _thread(10, with_tools=True)
    cut = _cut_index(msgs, keep=5)
    assert isinstance(msgs[cut], HumanMessage)
    assert all(not isinstance(m, ToolMessage) for m in msgs[cut:cut + 1])


def test_trim_never_starts_with_tool_result_and_skips_transient():
    msgs = _thread(6, with_tools=True)
    msgs.append(AIMessage(content="gateway down", additional_kwargs={"transient": True, "declined": True}, id="x"))
    tail = _trim(msgs, 5)
    assert isinstance(tail[0], HumanMessage)
    assert all(not m.additional_kwargs.get("transient") for m in tail)


def test_compress_is_a_noop_for_short_threads(monkeypatch):
    monkeypatch.setattr(chat.settings, "CHAT_COMPRESS_AFTER", 18)
    monkeypatch.setattr(chat.settings, "CHAT_COMPRESS_CHARS", 20_000)
    assert compress({"messages": _thread(3)}) == {}


def test_compress_summarises_and_removes_old_messages(monkeypatch):
    monkeypatch.setattr(chat.settings, "CHAT_COMPRESS_AFTER", 8)
    monkeypatch.setattr(chat.settings, "CHAT_KEEP_RECENT", 4)
    captured = {}

    class FakeLLM:
        def with_config(self, **_):
            return self
        def invoke(self, messages):
            captured["prompt"] = messages[1][1]
            return SimpleNamespace(content="The user asked about questions 0 to 2; Voxa answered each.")

    monkeypatch.setattr(chat, "chat_model", lambda **_: FakeLLM())
    msgs = _thread(6)                       # 12 messages
    out = compress({"messages": msgs, "summary": "Earlier: nothing."})
    assert out["summary"].startswith("The user asked")
    removed = [m for m in out["messages"] if isinstance(m, RemoveMessage)]
    assert len(removed) == len(msgs) - 4
    assert "Existing note:\nEarlier: nothing." in captured["prompt"]
    assert "question 0" in captured["prompt"] and "question 5" not in captured["prompt"]


def test_compress_keeps_history_when_summariser_fails(monkeypatch):
    monkeypatch.setattr(chat.settings, "CHAT_COMPRESS_AFTER", 4)
    monkeypatch.setattr(chat.settings, "CHAT_KEEP_RECENT", 2)

    class Boom:
        def with_config(self, **_):
            return self
        def invoke(self, _):
            raise ValueError("bad gateway")

    monkeypatch.setattr(chat, "chat_model", lambda **_: Boom())
    assert compress({"messages": _thread(5)}) == {}


def test_transient_detection_walks_the_cause_chain():
    try:
        try:
            raise ConnectionError("reset")
        except ConnectionError as inner:
            raise RuntimeError("wrapped") from inner
    except RuntimeError as exc:
        assert _is_transient(exc)
    assert not _is_transient(ValueError("schema"))
