"use client";

import { useEffect, useState } from "react";
import { api, type SystemStatus } from "@/lib/api";
import { fmtDate } from "@/lib/signals";
import { Button, EmptyState, PageHeader, Pill, Section, StatTile } from "@/components/ui";
import { useScreen } from "@/lib/screen";

const SEV_TONE = { critical: "weak", warning: "neutral", info: "good" } as const;

export default function StatusPage() {
  const [s, setS] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  function load() { api.status().then((d) => { setS(d); setError(null); }).catch((e: Error) => setError(e.message)); }
  useEffect(() => { load(); const t = setInterval(load, 60_000); return () => clearInterval(t); }, []);

  useScreen(s ? {
    page: "status", route: "/status", title: "System status", asOf: s.checked_at,
    summary: `System status page. Overall ${s.overall}. ${s.alerts.length} open alerts: ${s.alerts.map((a) => `${a.kind} (${a.severity})`).join(", ") || "none"}. ` +
      `Latest bars ${s.data.latest_bars}, scores ${s.data.latest_scores}, model trained ${s.data.model_trained}. LLM spend today $${s.llm.today.est_cost_usd}, 30 days $${s.llm.last_30_days.est_cost_usd}.` +
      (s.llm.projection && !("error" in s.llm.projection) ? ` Credits: $${s.llm.projection.remaining_usd} left (${s.llm.projection.remaining_pct}%), runs out around ${s.llm.projection.runs_out_on}.` : " Credit balance not configured."),
    data: { alerts: s.alerts, jobs: s.jobs, schedule: s.schedule, llm: { today: s.llm.today, last_30_days: s.llm.last_30_days, projection: s.llm.projection } },
  } : null, [s]);

  async function act(kind: "checks" | "test") {
    setBusy(kind); setNote(null);
    try {
      if (kind === "checks") { await api.runChecks(); setNote("All checks ran. Refreshed below."); }
      else { const r = await api.testAlert(); setNote(r.notified ? "Test alert delivered to your channel(s)." : "Alert recorded, but no push channel is configured (Telegram / webhook)."); }
      load();
    } catch (e) { setNote((e as Error).message); } finally { setBusy(null); }
  }

  if (error) return <EmptyState icon="⚠" title="Could not load status" body={error} />;
  if (!s) return <div className="skeleton" style={{ height: 300 }} />;

  const p = s.llm.projection && !("error" in s.llm.projection) ? s.llm.projection : null;
  const tone = s.overall === "ok" ? "strong" : s.overall === "warning" ? "neutral" : "weak";

  return (
    <div style={{ display: "grid", gap: 22 }}>
      <PageHeader eyebrow="System status · checked every minute" title={s.overall === "ok" ? "Everything is running" : s.overall === "warning" ? "Running, with warnings" : "Something needs you"}
        blurb="Scheduled jobs, open alerts, data freshness, AI spend and the trading calendar. Alerts also go to Telegram or a webhook when configured."
        aside={<>{fmtDate(s.today.date)} · {s.today.trading_day ? "trading day" : `market closed${s.today.holiday ? ` (${s.today.holiday})` : ""}`} · next trading day {fmtDate(s.today.next_trading_day)}</>} />

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
        <StatTile label="Overall" value={s.overall.toUpperCase()} tone={tone} sub={`${s.alerts.length} open alert${s.alerts.length === 1 ? "" : "s"}`} />
        <StatTile label="Latest prices" value={fmtDate(s.data.latest_bars)} sub={`scores ${fmtDate(s.data.latest_scores)}`} />
        <StatTile label="AI spend today" value={`$${s.llm.today.est_cost_usd.toFixed(3)}`} sub={`${s.llm.today.calls} calls · 30d $${s.llm.last_30_days.est_cost_usd.toFixed(2)}`} tone="accent" />
        <StatTile label="Credits left" value={p ? `$${p.remaining_usd.toFixed(2)}` : "not set"} sub={p ? (p.runs_out_on ? `≈ ${p.days_left} days · out around ${fmtDate(p.runs_out_on)}` : "no spend yet") : "set LLM_CREDITS_USD in .env"}
                  tone={p ? (p.remaining_pct < 20 ? "weak" : p.remaining_pct < 50 ? "neutral" : "strong") : undefined} />
        <StatTile label="Push channels" value={s.channels.telegram || s.channels.webhook ? "on" : "off"} sub={[s.channels.telegram && "Telegram", s.channels.webhook && "webhook"].filter(Boolean).join(" · ") || "log + this page only"} />
      </section>

      <section className="glass" style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center", padding: "10px 14px", borderRadius: 16 }}>
        <span className="eyebrow">Actions</span>
        <Button onClick={() => act("checks")} disabled={busy !== null}>{busy === "checks" ? "Running…" : "Run all checks now"}</Button>
        <Button onClick={() => act("test")} disabled={busy !== null} variant="ghost">{busy === "test" ? "Sending…" : "Send a test alert"}</Button>
        {note && <span style={{ fontSize: 12.5, color: "var(--text-muted)" }}>{note}</span>}
      </section>

      <Section title="Open alerts" sub={s.alerts.length ? "Newest first. Resolve one once you have acted on it; the checks re-raise it if the problem persists." : "Nothing needs attention."}>
        {s.alerts.length === 0 ? <div style={{ color: "var(--strong-ink)", fontWeight: 700 }}>✓ No open alerts</div> : (
          <div style={{ display: "grid", gap: 10 }}>
            {s.alerts.map((a) => (
              <div key={a.id} className="card" style={{ padding: 14, background: `var(--${SEV_TONE[a.severity]}-soft)`, borderColor: "transparent", display: "grid", gap: 6 }}>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
                  <Pill tone={SEV_TONE[a.severity]}>{a.severity}</Pill>
                  <b style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>{a.kind}</b>
                  <span style={{ fontSize: 12, color: "var(--text-muted)" }}>seen {a.count}× · last {a.last_seen.replace("T", " ").slice(0, 16)} UTC</span>
                  <button onClick={() => api.resolveAlert(a.id).then(load)} style={{ marginLeft: "auto", fontSize: 12, fontWeight: 700, color: "var(--accent-ink)", padding: "5px 10px", borderRadius: 999, background: "var(--card)" }}>Mark resolved</button>
                </div>
                <div style={{ fontSize: 13.5, lineHeight: 1.5 }}>{a.message}</div>
                {a.detail && <details style={{ fontSize: 12, color: "var(--text-muted)" }}><summary style={{ cursor: "pointer" }}>Technical detail</summary><pre style={{ whiteSpace: "pre-wrap", fontFamily: "var(--font-mono)", marginTop: 6 }}>{a.detail}</pre></details>}
              </div>
            ))}
          </div>
        )}
      </Section>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 20 }}>
        <Section title="Scheduled jobs" sub="Every job, its next run (IST), and how its last run ended">
          <div style={{ display: "grid", gap: 8 }}>
            {s.schedule.map((j) => {
              const last = Object.entries(s.jobs).find(([k]) => j.id.startsWith(k) || k.startsWith(j.id.replace("_job", "")))?.[1];
              return (
                <div key={j.id} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8, padding: "10px 12px", borderRadius: 12, background: "var(--card2)", fontSize: 13 }}>
                  <div><b>{j.name}</b><div style={{ fontSize: 11.5, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>{j.trigger.replace("cron[", "").replace("]", "")}</div></div>
                  <div style={{ textAlign: "right" }}>
                    <div className="tnum" style={{ fontSize: 12 }}>{j.next_run ? new Date(j.next_run).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—"}</div>
                    {last && <Pill tone={last.status === "ok" ? "strong" : last.status === "failed" ? "weak" : "neutral"}>{last.status}</Pill>}
                  </div>
                </div>
              );
            })}
          </div>
          <div style={{ marginTop: 12, fontSize: 12.5, color: "var(--text-muted)", lineHeight: 1.5 }}>
            Jobs run on every trading day, indefinitely, while the backend process is up. Weekends and the holidays below are skipped automatically.
          </div>
        </Section>

        <Section title="Last job outcomes" sub="From the job log, newest run per job">
          <div style={{ display: "grid", gap: 6 }}>
            {Object.entries(s.jobs).sort(([, a], [, b]) => b.started_at.localeCompare(a.started_at)).map(([k, v]) => (
              <div key={k} style={{ display: "grid", gridTemplateColumns: "150px auto 1fr", gap: 10, alignItems: "center", fontSize: 12.5, padding: "6px 0", borderBottom: "1px solid var(--border)" }}>
                <b style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{k}</b>
                <Pill tone={v.status === "ok" ? "strong" : v.status === "failed" ? "weak" : "neutral"}>{v.status}</Pill>
                <span style={{ color: "var(--text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{v.started_at.replace("T", " ").slice(0, 16)} · {v.rows} rows {v.detail && `· ${v.detail}`}</span>
              </div>
            ))}
            {Object.keys(s.jobs).length === 0 && <div style={{ color: "var(--text-muted)", fontSize: 13 }}>No job has run yet.</div>}
          </div>
        </Section>

        <Section title="AI spend, last 30 days" sub={s.llm.note}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <div>
              <div className="eyebrow" style={{ marginBottom: 6 }}>By feature</div>
              {s.llm.by_feature_30d.map((f) => <Row key={f.feature} k={f.feature} v={`$${f.est_cost_usd.toFixed(3)} · ${f.calls}`} />)}
              {s.llm.by_feature_30d.length === 0 && <div style={{ fontSize: 12.5, color: "var(--text-muted)" }}>No calls metered yet.</div>}
            </div>
            <div>
              <div className="eyebrow" style={{ marginBottom: 6 }}>By model</div>
              {s.llm.by_model_30d.map((m) => <Row key={m.model} k={m.model.replace("openai/", "")} v={`$${m.est_cost_usd.toFixed(3)} · ${m.calls}`} />)}
            </div>
          </div>
          {p && (
            <div style={{ marginTop: 14, padding: 12, borderRadius: 12, background: p.remaining_pct < 20 ? "var(--weak-soft)" : "var(--card2)", fontSize: 13, lineHeight: 1.55 }}>
              Balance <b>${p.balance_usd.toFixed(2)}</b> on {fmtDate(p.as_of)} · spent since ≈ <b>${p.spent_since_usd.toFixed(3)}</b> · burning ≈ <b>${p.burn_per_day_usd.toFixed(3)}/day</b>
              {p.runs_out_on && <> · runs out around <b>{fmtDate(p.runs_out_on)}</b></>}. You get a warning at {`<`}20% or {`<`}14 days, and a critical alert the moment the gateway refuses a call for credits.
            </div>
          )}
          {!p && <div style={{ marginTop: 14, fontSize: 12.5, color: "var(--text-muted)" }}>Add <code>LLM_CREDITS_USD</code> and <code>LLM_CREDITS_AS_OF</code> to <code>backend/.env</code> to see a run-out date here.</div>}
        </Section>

        <Section title="Trading calendar" sub={`${s.calendar.total} holidays known for ${s.calendar.years_covered.join(", ")} · sources: ${Object.entries(s.calendar.by_source).map(([k, v]) => `${k} ${v}`).join(", ") || "static"}`}>
          <div className="eyebrow" style={{ marginBottom: 6 }}>Next market holidays</div>
          {s.calendar.next.map((h) => <Row key={h.date} k={fmtDate(h.date)} v={h.name} />)}
          <div style={{ marginTop: 10, fontSize: 12.5, color: "var(--text-muted)", lineHeight: 1.5 }}>NSE&apos;s list is re-fetched on the 1st of each month; fixed national holidays cover any year not yet published.</div>
        </Section>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return <div style={{ display: "flex", justifyContent: "space-between", gap: 10, fontSize: 12.5, padding: "4px 0", borderBottom: "1px solid var(--border)" }}><span style={{ color: "var(--text-2)" }}>{k}</span><b className="tnum">{v}</b></div>;
}
