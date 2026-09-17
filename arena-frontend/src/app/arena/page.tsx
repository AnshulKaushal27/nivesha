"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type HistoryMap, type LeaderboardEntry, type ModelResult, type PortfolioDetail, type PortfolioListItem, type SimData } from "@/lib/api";
import { fmtDate, fmtINR, fmtPct, modelMeta, RISK_TONE } from "@/lib/signals";
import { Button, EmptyState, LoadMore, PageHeader, Pill, Section, StatTile, Tabs } from "@/components/ui";
import { AllocationDonut, LeaderBars } from "@/components/charts";
import { useScreen } from "@/lib/screen";

type Tab = "today" | "leaderboard" | "history" | "portfolios" | "shortlist";
const PAGE = 20;
const TAB_LABEL: Record<Tab, string> = { today: "Today's picks", leaderboard: "Leaderboard", history: "Race", portfolios: "All portfolios", shortlist: "Shortlist" };

export default function ArenaPage() {
  const [tab, setTab] = useState<Tab>("today");
  const [sim, setSim] = useState<SimData | null>(null);
  const [board, setBoard] = useState<LeaderboardEntry[]>([]);
  const [hist, setHist] = useState<HistoryMap>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  function load() {
    setLoading(true);
    Promise.all([api.simToday(), api.leaderboard(), api.history()])
      .then(([s, b, h]) => { setSim(s); setBoard(b); setHist(h); setError(null); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  async function run(kind: "simulate" | "value") {
    setBusy(kind); setNotice(null);
    try {
      const r = kind === "simulate" ? await api.runSimulation() : await api.updateValuations();
      setNotice(r.message); load();
    } catch (e) { setNotice((e as Error).message); } finally { setBusy(null); }
  }

  const models = sim?.model_results ?? [];

  useScreen(!loading && sim ? {
    page: "arena", route: "/arena", title: `AI Arena — ${TAB_LABEL[tab]}`, asOf: sim.date,
    summary: `AI Arena, tab "${TAB_LABEL[tab]}", latest round ${sim.date}. ` + (models.length
      ? `Managers: ${models.map((m) => `${modelMeta(m.model).label} ${m.current_return == null ? "(not valued)" : fmtPct(m.current_return, 2)}, ${m.risk_level ?? "?"} risk, ${m.portfolio.length} stocks`).join("; ")}.`
      : "No round has been run yet."),
    data: {
      managers: models.map((m) => ({ manager: modelMeta(m.model).label, key: m.model, return_pct: m.current_return, value: m.portfolio_value, risk: m.risk_level, strategy: m.strategy_summary,
        holdings: m.portfolio.map((h) => ({ symbol: h.ticker.replace(".NS", ""), weight_pct: h.allocation_percent, confidence: h.confidence, why: h.reasoning })) })),
      leaderboard: board.map((b) => ({ manager: modelMeta(b.model).label, avg_return_pct: b.average_return_percent, win_rate: b.win_rate, rounds: b.total_portfolios })),
      shortlist_top10: (sim.market_candidates ?? []).slice(0, 10).map((c) => ({ symbol: c.ticker.replace(".NS", ""), topsis: c.topsis_score, one_month_pct: c.one_month_return, rsi: c.rsi, sector: c.sector })),
    },
  } : null, [loading, sim, board, tab]);

  if (error) return <EmptyState icon="⚠" title="Could not reach the Arena" body={error} />;
  const leader = [...board].sort((a, b) => b.average_return_percent - a.average_return_percent)[0];

  return (
    <div style={{ display: "grid", gap: 22 }}>
      <PageHeader
        eyebrow="AI Arena · four AI managers, one market"
        title="Which AI picks stocks best?"
        blurb="Every trading morning four AI models get the same TOPSIS shortlist and ₹1,00,000 of paper money. Each builds a portfolio in its own style. We track who is ahead."
        aside={sim?.date ? <>Latest round <b style={{ color: "var(--text)" }}>{fmtDate(sim.date)}</b></> : null}
      />

      {/* Admin strip */}
      <section className="glass fade-up-1" style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 16 }}>
        <span className="eyebrow">Controls</span>
        <Button onClick={() => run("simulate")} disabled={busy !== null}>{busy === "simulate" ? "Running the AIs…" : "▶ Run today's round"}</Button>
        <Button onClick={() => run("value")} disabled={busy !== null} variant="ghost">{busy === "value" ? "Updating…" : "↻ Update values"}</Button>
        {notice && <span style={{ fontSize: 12.5, color: "var(--text-muted)" }}>{notice}</span>}
      </section>

      {/* Summary tiles */}
      {!loading && models.length > 0 && (
        <section className="fade-up-2" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
          <StatTile label="Leading overall" value={leader ? modelMeta(leader.model).short : "—"} sub={leader ? `${fmtPct(leader.average_return_percent, 2)} average return` : ""} tone="strong" />
          <StatTile label="Best today" value={(() => { const b = [...models].sort((a, c) => (c.current_return ?? -1e9) - (a.current_return ?? -1e9))[0]; return b ? modelMeta(b.model).short : "—"; })()} sub={(() => { const b = [...models].sort((a, c) => (c.current_return ?? -1e9) - (a.current_return ?? -1e9))[0]; return b?.current_return != null ? fmtPct(b.current_return, 2) : "not valued yet"; })()} tone="good" />
          <StatTile label="Rounds played" value={board.reduce((m, b) => Math.max(m, b.total_portfolios), 0)} sub="trading days with portfolios" />
          <StatTile label="Shortlist size" value={sim?.market_candidates.length ?? 0} sub="TOPSIS-ranked candidates today" tone="neutral" />
        </section>
      )}

      <Tabs<Tab> ariaLabel="Arena views" value={tab} onChange={setTab} tabs={[
        { id: "today", label: "Today's picks", icon: "⬡" },
        { id: "leaderboard", label: "Leaderboard", icon: "♛" },
        { id: "history", label: "Race", icon: "↗" },
        { id: "portfolios", label: "All portfolios", icon: "▤" },
        { id: "shortlist", label: "Shortlist", icon: "☰", count: sim?.market_candidates.length },
      ]} />

      {loading && <div className="skeleton" style={{ height: 320 }} />}

      {!loading && models.length === 0 && tab !== "shortlist" && (
        <EmptyState icon="⬡" title="No round yet" body="Press “Run today's round” to have the four AIs build their portfolios from today's shortlist." />
      )}

      {!loading && tab === "today" && models.length > 0 && <TodayView models={models} />}
      {!loading && tab === "leaderboard" && board.length > 0 && <LeaderboardView board={board} />}
      {!loading && tab === "history" && Object.keys(hist).length > 0 && <RaceView hist={hist} />}
      {!loading && tab === "portfolios" && <PortfoliosView />}
      {!loading && tab === "shortlist" && <ShortlistView sim={sim} />}
    </div>
  );
}

/* ── Today ─────────────────────────────────────────────────────────── */
function TodayView({ models }: { models: ModelResult[] }) {
  const [open, setOpen] = useState<string | null>(models[0]?.model ?? null);
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: 14 }}>
        {models.map((m) => {
          const meta = modelMeta(m.model);
          const active = open === m.model;
          const ret = m.current_return;
          return (
            <button key={m.model} onClick={() => setOpen(m.model)} className="card" aria-pressed={active} style={{
              textAlign: "left", padding: 18, borderColor: active ? meta.color : "var(--border)", borderWidth: active ? 2 : 1,
              position: "relative", overflow: "hidden",
            }}>
              <div aria-hidden style={{ position: "absolute", right: -20, top: -20, width: 90, height: 90, borderRadius: "50%", background: meta.color, opacity: 0.12 }} />
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span aria-hidden style={{ width: 34, height: 34, borderRadius: 11, display: "grid", placeItems: "center", background: meta.color, color: "#fff", fontWeight: 800 }}>{meta.icon}</span>
                <div>
                  <div style={{ fontWeight: 800 }}>{meta.label}</div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{meta.style}</div>
                </div>
              </div>
              <div className="tnum" style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 28, marginTop: 12, color: ret == null ? "var(--text-dim)" : ret >= 0 ? "var(--strong-ink)" : "var(--weak-ink)" }}>
                {ret == null ? "—" : fmtPct(ret, 2)}
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6, fontSize: 12.5, color: "var(--text-2)" }}>
                <span className="tnum">{fmtINR(m.portfolio_value ?? m.starting_capital, 0)}</span>
                {m.risk_level && <Pill tone={RISK_TONE[m.risk_level] ?? "neutral"}>{m.risk_level}</Pill>}
                <span style={{ color: "var(--text-muted)" }}>{m.portfolio.length} stocks</span>
              </div>
            </button>
          );
        })}
      </div>

      {models.filter((m) => m.model === open).map((m) => {
        const meta = modelMeta(m.model);
        return (
          <Section key={m.model} title={`${meta.label} — today's portfolio`} sub={m.strategy_summary ?? ""}>
            <div style={{ marginBottom: 16, padding: 14, borderRadius: 14, background: "var(--card2)" }}>
              <div className="eyebrow" style={{ marginBottom: 8 }}>How the money is split</div>
              <AllocationDonut holdings={m.portfolio} color={meta.color} cash={(m.remaining_cash / m.starting_capital) * 100} />
            </div>
            <div style={{ display: "grid", gap: 10 }}>
              {[...m.portfolio].sort((a, b) => b.allocation_percent - a.allocation_percent).map((h) => (
                <div key={h.ticker} style={{ display: "grid", gridTemplateColumns: "140px 1fr 90px 80px", alignItems: "center", gap: 12, padding: "10px 12px", borderRadius: 12, background: "var(--card2)" }}>
                  <div>
                    <Link href={`/rank/${h.ticker.replace(".NS", "")}`} style={{ fontWeight: 800 }}>{h.ticker.replace(".NS", "")}</Link>
                    <div style={{ fontSize: 11.5, color: "var(--text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{h.sector}</div>
                  </div>
                  <div>
                    <div style={{ height: 10, background: "var(--card)", borderRadius: 999, overflow: "hidden" }}>
                      <div style={{ width: `${h.allocation_percent}%`, height: "100%", background: meta.color, borderRadius: 999 }} />
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-2)", marginTop: 6, lineHeight: 1.45 }}>{h.reasoning}</div>
                  </div>
                  <div className="tnum" style={{ textAlign: "right", fontWeight: 800 }}>{h.allocation_percent.toFixed(0)}%</div>
                  <div style={{ textAlign: "right" }}><Pill tone={h.confidence >= 80 ? "strong" : h.confidence >= 65 ? "good" : "neutral"}>{h.confidence}% sure</Pill></div>
                </div>
              ))}
            </div>
          </Section>
        );
      })}
    </div>
  );
}

/* ── Leaderboard ───────────────────────────────────────────────────── */
function LeaderboardView({ board }: { board: LeaderboardEntry[] }) {
  return (
    <Section title="Leaderboard" sub="Ranked by average daily return across every round played">
      <div style={{ marginBottom: 14 }}>
        <LeaderBars rows={board.map((b) => ({ name: modelMeta(b.model).label, value: b.average_return_percent, color: modelMeta(b.model).color }))} />
      </div>
      <div style={{ display: "grid", gap: 10 }}>
        {board.map((b, i) => {
          const meta = modelMeta(b.model);
          return (
            <div key={b.model} className="card" style={{ display: "grid", gridTemplateColumns: "44px 1fr repeat(4, minmax(90px, auto))", alignItems: "center", gap: 14, padding: "14px 16px", background: i === 0 ? "var(--strong-soft)" : "var(--card)", borderColor: "transparent" }}>
              <div className="tnum" style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 22, color: i === 0 ? "var(--strong-ink)" : "var(--text-dim)" }}>{i + 1}</div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span aria-hidden style={{ width: 30, height: 30, borderRadius: 9, display: "grid", placeItems: "center", background: meta.color, color: "#fff", fontWeight: 800, fontSize: 13 }}>{meta.icon}</span>
                <div><div style={{ fontWeight: 800 }}>{meta.label}</div><div style={{ fontSize: 12, color: "var(--text-muted)" }}>{b.days_active} days valued · {b.total_portfolios} rounds</div></div>
              </div>
              <Stat l="Average" v={fmtPct(b.average_return_percent, 2)} tone={b.average_return_percent >= 0} />
              <Stat l="Win rate" v={`${b.win_rate.toFixed(0)}%`} tone={b.win_rate >= 50} />
              <Stat l="Best day" v={fmtPct(b.best_return_percent, 2)} tone />
              <Stat l="Worst day" v={fmtPct(b.worst_return_percent, 2)} tone={false} />
            </div>
          );
        })}
      </div>
    </Section>
  );
}
function Stat({ l, v, tone }: { l: string; v: string; tone: boolean }) {
  return <div style={{ textAlign: "right" }}><div className="eyebrow" style={{ fontSize: 10 }}>{l}</div><div className="tnum" style={{ fontWeight: 800, color: tone ? "var(--strong-ink)" : "var(--weak-ink)" }}>{v}</div></div>;
}

/* ── Race chart ────────────────────────────────────────────────────── */
function RaceView({ hist }: { hist: HistoryMap }) {
  const models = Object.keys(hist);
  const data = useMemo(() => {
    const byDate: Record<string, Record<string, number>> = {};
    models.forEach((m) => hist[m].forEach((r) => { (byDate[r.date] ??= {})[m] = r.return_pct; }));
    return Object.entries(byDate).sort(([a], [b]) => a.localeCompare(b)).map(([date, v]) => ({ date, ...v }));
  }, [hist, models]);
  return (
    <Section title="The race" sub="Daily return of each AI's portfolio, %. One line per manager.">
      <div style={{ width: "100%", height: 340 }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 10, right: 20, bottom: 0, left: -10 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis dataKey="date" tickFormatter={(d: string) => fmtDate(d).slice(0, 6)} tick={{ fontSize: 11, fill: "var(--text-muted)" }} axisLine={{ stroke: "var(--axis)" }} tickLine={false} minTickGap={30} />
            <YAxis tickFormatter={(v: number) => `${v}%`} tick={{ fontSize: 11, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid var(--border)", background: "var(--card)", boxShadow: "var(--shadow-lg)", fontSize: 12 }}
                     formatter={(v: number, name: string) => [fmtPct(v, 2), modelMeta(name).label]} labelFormatter={(d) => fmtDate(String(d))} />
            <Legend formatter={(name: string) => <span style={{ color: "var(--text-2)", fontSize: 12 }}>{modelMeta(name).label}</span>} />
            {models.map((m) => <Line key={m} type="monotone" dataKey={m} stroke={modelMeta(m).color} strokeWidth={2} dot={false} activeDot={{ r: 5, stroke: "var(--card)", strokeWidth: 2 }} connectNulls isAnimationActive={false} />)}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Section>
  );
}

/* ── Portfolios ────────────────────────────────────────────────────── */
function PortfoliosView() {
  const [list, setList] = useState<PortfolioListItem[]>([]);
  const [detail, setDetail] = useState<PortfolioDetail | null>(null);
  const [filter, setFilter] = useState("");
  const [shown, setShown] = useState(PAGE);
  useEffect(() => { api.portfolios().then(setList).catch(() => setList([])); }, []);
  const rows = list.filter((p) => !filter || p.model === filter);
  useEffect(() => { setShown(PAGE); }, [filter]);
  return (
    <div style={{ display: "grid", gridTemplateColumns: detail ? "minmax(320px, 1fr) minmax(320px, 1.2fr)" : "1fr", gap: 20 }}>
      <Section title="All portfolios" sub={`${rows.length} rounds`} action={
        <select value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Model" style={{ padding: "8px 12px", borderRadius: 999, border: "1px solid var(--border)", background: "var(--card)" }}>
          <option value="">All managers</option>
          {["gpt", "gemini", "mistral", "deepseek"].map((m) => <option key={m} value={m}>{modelMeta(m).label}</option>)}
        </select>}>
        <div style={{ display: "grid", gap: 8 }}>
          {rows.slice(0, shown).map((p) => {
            const meta = modelMeta(p.model);
            return (
              <button key={p.id} onClick={() => api.portfolio(p.id).then(setDetail)} style={{ display: "grid", gridTemplateColumns: "34px 1fr auto", gap: 12, alignItems: "center", textAlign: "left", padding: "10px 12px", borderRadius: 12, background: detail?.id === p.id ? "var(--accent-soft)" : "var(--card2)" }}>
                <span aria-hidden style={{ width: 30, height: 30, borderRadius: 9, display: "grid", placeItems: "center", background: meta.color, color: "#fff", fontWeight: 800, fontSize: 13 }}>{meta.icon}</span>
                <div><div style={{ fontWeight: 800 }}>{meta.label} <span style={{ color: "var(--text-muted)", fontWeight: 500 }}>· {fmtDate(p.date)}</span></div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 420 }}>{p.strategy_summary}</div></div>
                <div style={{ textAlign: "right", fontSize: 12.5 }}><div className="tnum" style={{ fontWeight: 700 }}>{p.holdings_count} stocks</div>{p.risk_level && <Pill tone={RISK_TONE[p.risk_level] ?? "neutral"}>{p.risk_level}</Pill>}</div>
              </button>
            );
          })}
          {rows.length === 0 && <div style={{ color: "var(--text-muted)", fontSize: 13 }}>No portfolios yet.</div>}
        </div>
        <LoadMore shown={Math.min(shown, rows.length)} total={rows.length} step={PAGE} onMore={() => setShown((s) => s + PAGE)} />
      </Section>
      {detail && (
        <Section title={`${modelMeta(detail.model).label} · ${fmtDate(detail.date)}`} sub={detail.strategy_summary ?? ""} action={<Button variant="ghost" onClick={() => setDetail(null)}>Close</Button>}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 14 }}>
            <StatTile label="Value" value={fmtINR(detail.latest_valuation?.portfolio_value ?? detail.starting_capital, 0)} />
            <StatTile label="Return" value={fmtPct(detail.latest_valuation?.return_pct ?? null, 2)} tone={(detail.latest_valuation?.return_pct ?? 0) >= 0 ? "strong" : "weak"} />
            <StatTile label="Cash" value={fmtINR(detail.remaining_cash, 0)} />
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {detail.holdings.map((h) => (
              <div key={h.ticker} style={{ display: "grid", gridTemplateColumns: "120px 1fr 70px", gap: 10, alignItems: "center", padding: "8px 10px", borderRadius: 10, background: "var(--card2)", fontSize: 13 }}>
                <b>{h.ticker.replace(".NS", "")}</b>
                <span style={{ color: "var(--text-2)", fontSize: 12 }}>{h.reasoning}</span>
                <b className="tnum" style={{ textAlign: "right" }}>{h.allocation_percent.toFixed(0)}%</b>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

/* ── Shortlist ─────────────────────────────────────────────────────── */
function ShortlistView({ sim }: { sim: SimData | null }) {
  const [shown, setShown] = useState(PAGE);
  const rows = sim?.market_candidates ?? [];
  if (rows.length === 0) return <EmptyState icon="☰" title="No shortlist yet" body="The shortlist is built when a round runs." />;
  return (
    <Section title="Today's TOPSIS shortlist" sub="The candidates every AI manager was shown, best score first">
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 720 }}>
          <thead><tr style={{ background: "var(--card2)" }}>
            {["#", "Stock", "Sector", "TOPSIS", "1-month", "RSI", "Volatility", "Volume"].map((h, i) => <th key={h} className="eyebrow" style={{ textAlign: i >= 3 ? "right" : "left", padding: "12px 14px", whiteSpace: "nowrap" }}>{h}</th>)}
          </tr></thead>
          <tbody>
            {rows.slice(0, shown).map((c, i) => (
              <tr key={c.ticker} style={{ borderTop: "1px solid var(--border)" }}>
                <td className="tnum" style={{ padding: "11px 14px", color: "var(--text-dim)", fontSize: 12 }}>{i + 1}</td>
                <td style={{ padding: "11px 14px" }}><Link href={`/rank/${c.ticker.replace(".NS", "")}`} style={{ fontWeight: 800 }}>{c.ticker.replace(".NS", "")}</Link></td>
                <td style={{ padding: "11px 14px", color: "var(--text-2)", fontSize: 13 }}>{c.sector}</td>
                <td className="tnum" style={{ padding: "11px 14px", textAlign: "right", fontWeight: 800 }}>{c.topsis_score.toFixed(3)}</td>
                <td className="tnum" style={{ padding: "11px 14px", textAlign: "right", color: c.one_month_return >= 0 ? "var(--strong-ink)" : "var(--weak-ink)", fontWeight: 700 }}>{fmtPct(c.one_month_return)}</td>
                <td className="tnum" style={{ padding: "11px 14px", textAlign: "right" }}>{c.rsi.toFixed(0)}</td>
                <td className="tnum" style={{ padding: "11px 14px", textAlign: "right", color: "var(--text-2)" }}>{c.volatility.toFixed(0)}%</td>
                <td className="tnum" style={{ padding: "11px 14px", textAlign: "right", color: "var(--text-2)" }}>{c.volume_ratio.toFixed(2)}×</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <LoadMore shown={Math.min(shown, rows.length)} total={rows.length} step={PAGE} onMore={() => setShown((s) => s + PAGE)} />
    </Section>
  );
}
