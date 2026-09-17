"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { API } from "@/lib/api";
import { getScreen, subscribeScreen, SUGGESTIONS } from "@/lib/screen";

interface Msg { role: "user" | "assistant"; content: string; declined?: boolean; tools?: string[]; pending?: boolean }
interface Frame { type: "status" | "delta" | "done" | "error"; text?: string; label?: string; stage?: string; message?: string; declined?: boolean; tools_used?: string[]; compressed?: boolean }

const THREAD_KEY = "arena-chat-thread";
const newId = () => (typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `t${Date.now()}${Math.random().toString(36).slice(2, 10)}`);

export function ChatDock() {
  const [open, setOpen] = useState(false);
  const [thread, setThread] = useState<string>("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [page, setPage] = useState(getScreen().page);
  const [summary, setSummary] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // thread id persists per browser
  useEffect(() => {
    let id = "";
    try { id = localStorage.getItem(THREAD_KEY) ?? ""; } catch { /* ignore */ }
    if (!id) { id = newId(); try { localStorage.setItem(THREAD_KEY, id); } catch { /* ignore */ } }
    setThread(id);
  }, []);

  useEffect(() => subscribeScreen(() => setPage(getScreen().page)), []);

  // load history when opened
  useEffect(() => {
    if (!open || !thread || msgs.length) return;
    fetch(`${API}/chat/${thread}/history`).then((r) => r.ok ? r.json() : null).then((d) => {
      if (d?.messages) setMsgs(d.messages as Msg[]);
      if (d?.summary) setSummary(d.summary as string);
    }).catch(() => { /* offline */ });
  }, [open, thread]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" }); }, [msgs, status]);

  const send = useCallback(async (text: string) => {
    const q = text.trim();
    if (!q || busy || !thread) return;
    setInput("");
    setBusy(true);
    setStatus("Checking your question");
    setMsgs((m) => [...m, { role: "user", content: q }, { role: "assistant", content: "", pending: true }]);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" }, signal: ctrl.signal,
        body: JSON.stringify({ thread_id: thread, message: q, screen: getScreen(), stream: true }),
      });
      if (!res.ok || !res.body) {
        const detail = await res.text().catch(() => "");
        if (res.status === 503) setUnavailable("Chat needs an LLM API key on the server.");
        throw new Error(detail || `${res.status}`);
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      let acc = "";
      const tools: string[] = [];
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          const f = JSON.parse(line.slice(6)) as Frame;
          if (f.type === "status") { setStatus(f.label ?? null); if (f.stage === "tool" && f.label) tools.push(f.label); }
          else if (f.type === "delta") { acc += f.text ?? ""; setStatus(null); setMsgs((m) => replaceLast(m, { role: "assistant", content: acc, pending: true, tools })); }
          else if (f.type === "done") {
            setMsgs((m) => replaceLast(m, { role: "assistant", content: f.message || acc, declined: f.declined, tools }));
            if (f.compressed && !summary) setSummary("Earlier turns have been condensed into a short memory note so long chats stay fast.");
          }
          else if (f.type === "error") { setMsgs((m) => replaceLast(m, { role: "assistant", content: f.message ?? "Something went wrong.", declined: true })); }
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setMsgs((m) => replaceLast(m, { role: "assistant", content: "I couldn't reach the assistant. Is the backend running?", declined: true }));
      }
    } finally {
      setBusy(false); setStatus(null); abortRef.current = null;
    }
  }, [busy, thread]);

  function reset() {
    abortRef.current?.abort();
    if (thread) fetch(`${API}/chat/${thread}`, { method: "DELETE" }).catch(() => { /* ignore */ });
    const id = newId();
    try { localStorage.setItem(THREAD_KEY, id); } catch { /* ignore */ }
    setThread(id); setMsgs([]); setSummary(null); setStatus(null); setBusy(false);
  }

  const suggestions = SUGGESTIONS[page] ?? SUGGESTIONS.unknown;

  return (
    <>
      {/* Launcher */}
      <button onClick={() => setOpen((o) => !o)} aria-label={open ? "Close Voxa" : "Open Voxa"} aria-expanded={open} className="glass" style={{
        position: "fixed", right: 22, bottom: 22, zIndex: 60, height: 52, padding: "0 18px 0 14px", borderRadius: 999,
        display: "flex", alignItems: "center", gap: 10, fontWeight: 800, fontSize: 14, color: "var(--accent-ink)", boxShadow: "var(--shadow-lg)",
      }}>
        <span aria-hidden style={{ width: 28, height: 28, borderRadius: 9, display: "grid", placeItems: "center", background: "linear-gradient(135deg, var(--accent), var(--good))", color: "#fff", fontSize: 14 }}>✦</span>
        {open ? "Close" : "Ask Voxa"}
      </button>

      {/* Panel */}
      {open && (
        <aside role="dialog" aria-label="Voxa assistant" className="glass fade-up" style={{
          position: "fixed", right: 22, bottom: 86, zIndex: 60, width: "min(420px, calc(100vw - 32px))", height: "min(680px, calc(100vh - 120px))",
          borderRadius: 22, display: "grid", gridTemplateRows: "auto 1fr auto", overflow: "hidden", boxShadow: "var(--shadow-lg)",
        }}>
          <header style={{ display: "flex", alignItems: "center", gap: 10, padding: "14px 16px", borderBottom: "1px solid var(--border)" }}>
            <span aria-hidden style={{ width: 30, height: 30, borderRadius: 10, display: "grid", placeItems: "center", background: "linear-gradient(135deg, var(--accent), var(--good))", color: "#fff" }}>✦</span>
            <div style={{ lineHeight: 1.15 }}>
              <div style={{ fontWeight: 800 }}>Voxa</div>
              <div style={{ fontSize: 11.5, color: "var(--text-muted)" }}>Sees this screen · remembers this chat · can search the web</div>
            </div>
            <button onClick={reset} style={{ marginLeft: "auto", fontSize: 12, fontWeight: 700, color: "var(--accent-ink)", padding: "6px 10px", borderRadius: 999, background: "var(--accent-soft)" }}>New chat</button>
          </header>

          <div ref={listRef} style={{ overflowY: "auto", padding: 16, display: "grid", gap: 12, alignContent: "start" }}>
            {unavailable && <Bubble role="assistant" declined>{unavailable}</Bubble>}
            {summary && (
              <details style={{ fontSize: 12, color: "var(--text-muted)", padding: "8px 10px", borderRadius: 10, background: "var(--card2)" }}>
                <summary style={{ cursor: "pointer", fontWeight: 700 }}>Earlier conversation condensed into memory</summary>
                <div style={{ marginTop: 6, lineHeight: 1.5, color: "var(--text-2)" }}>{summary}</div>
              </details>
            )}
            {msgs.length === 0 && !unavailable && (
              <div style={{ display: "grid", gap: 8 }}>
                <div style={{ fontSize: 13, color: "var(--text-2)", lineHeight: 1.5 }}>
                  Ask about anything you can see, a stock, or the markets. I ground answers in the app&apos;s data and cite the web when I use it.
                </div>
                {suggestions.map((s) => (
                  <button key={s} onClick={() => send(s)} style={{ textAlign: "left", padding: "10px 12px", borderRadius: 12, background: "var(--card)", border: "1px solid var(--border)", fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
                    {s}
                  </button>
                ))}
              </div>
            )}
            {msgs.map((m, i) => (
              <Bubble key={i} role={m.role} declined={m.declined} tools={m.tools} pending={m.pending && !m.content} streaming={m.pending && !!m.content}>
                {m.role === "assistant"
                  ? <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: (p) => <a {...p} target="_blank" rel="noreferrer" style={{ color: "var(--accent-ink)", textDecoration: "underline" }} /> }}>{m.content}</ReactMarkdown>
                  : m.content}
              </Bubble>
            ))}
            {status && <div style={{ fontSize: 12, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 8 }}><Dots /> {status}…</div>}
          </div>

          <form onSubmit={(e) => { e.preventDefault(); send(input); }} style={{ display: "flex", gap: 8, padding: 12, borderTop: "1px solid var(--border)" }}>
            <input value={input} onChange={(e) => setInput(e.target.value)} placeholder={`Ask about this ${page === "unknown" ? "app" : page} screen…`} aria-label="Message" disabled={busy || !!unavailable}
                   style={{ flex: 1, padding: "11px 14px", borderRadius: 999, border: "1px solid var(--border)", background: "var(--card)", outline: "none", fontSize: 13.5 }} />
            <button type="submit" disabled={busy || !input.trim()} aria-label="Send" style={{ width: 42, height: 42, borderRadius: 999, background: "var(--accent)", color: "#fff", fontWeight: 800, opacity: busy || !input.trim() ? 0.5 : 1 }}>↑</button>
          </form>
        </aside>
      )}
    </>
  );
}

function replaceLast(list: Msg[], m: Msg): Msg[] {
  const out = list.slice();
  out[out.length - 1] = m;
  return out;
}

function Bubble({ role, declined, tools, pending, streaming, children }: { role: "user" | "assistant"; declined?: boolean; tools?: string[]; pending?: boolean; streaming?: boolean; children: React.ReactNode }) {
  const user = role === "user";
  return (
    <div style={{ display: "grid", gap: 4, justifyItems: user ? "end" : "start" }}>
      {!user && tools && tools.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {Array.from(new Set(tools)).map((t) => <span key={t} className="chip" style={{ background: "var(--good-soft)", color: "var(--good-ink)", fontSize: 10.5 }}>{t}</span>)}
        </div>
      )}
      <div className="chat-md" style={{
        maxWidth: "88%", padding: "10px 13px", borderRadius: user ? "16px 16px 4px 16px" : "16px 16px 16px 4px", fontSize: 13.5, lineHeight: 1.55,
        background: user ? "var(--accent)" : declined ? "var(--warn-soft)" : "var(--card)",
        color: user ? "#fff" : declined ? "var(--neutral-ink)" : "var(--text)",
        border: user ? "none" : "1px solid var(--border)", whiteSpace: user ? "pre-wrap" : "normal",
      }}>
        {pending ? <Dots /> : children}
        {streaming && <span className="caret" aria-hidden />}
      </div>
    </div>
  );
}

function Dots() {
  return <span aria-label="Working" style={{ display: "inline-flex", gap: 3 }}>{[0, 1, 2].map((i) => <span key={i} style={{ width: 6, height: 6, borderRadius: 3, background: "var(--text-dim)", animation: `pulse-dot 1.2s ${i * 0.15}s infinite` }} />)}</span>;
}
