"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api, type PredictionItem, type PredictLive, type PredictRun } from "@/lib/api";
import { fmtDate, fmtINR, fmtPct } from "@/lib/signals";
import { Button, EmptyState, LoadMore, PageHeader, Pill, Section, StatTile, Tabs } from "@/components/ui";
import { BaseRateChart, CalibrationChart, FoldsChart, LiveScoreChart, OddsHistogram, ProfileChart, SectorBars } from "@/components/charts";
import { useScreen } from "@/lib/screen";

const PAGE = 20;
type Tab = "odds" | "types" | "sectors" | "history" | "model";
const TAB_LABEL: Record<Tab, string> = { odds: "Best odds now", types: "What type rises", sectors: "Sector outlook", history: "20-year base rates", model: "How it was tested" };

export default function PredictPage() {
  const [run, setRun] = useState<PredictRun | null>(null);
  const [live, setLive] = useState<PredictLive | null>(null);
  const [items, setItems] = useState<PredictionItem[]>([]);
  const [tab, setTab] = useState<Tab>("odds");
  const [shown, setShown] = useState(PAGE);
  const [sector, setSector] = useState("");
  const [loading, setLoading] = useState(true);
  const [training, setTraining] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setLoading(true);
    api.predict({ limit: 600 })
      .then((r) => { setRun(r.run); setItems(r.items); setError(null); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
    api.predictLive().then(setLive).catch(() => setLive(null));
  }
  useEffect(load, []);
  useEffect(() => { setShown(PAGE); }, [sector]);

  const filtered = useMemo(() => items.filter((i) => !sector || i.sector === sector), [items, sector]);
  const sectors = useMemo(() => Array.from(new Set(items.map((i) => i.sector ?? "Unknown"))).sort(), [items]);

  async function train() {
    setTraining(true);
    try { await api.trainPredictor(); load(); } catch (e) { setError((e as Error).message); } finally { setTraining(false); }
  }

  useScreen(run ? {
    page: "predict", route: "/predict", title: `Predictions — ${TAB_LABEL[tab]}`, asOf: run.as_of,
    summary: `Predictions page, tab "${TAB_LABEL[tab]}". Model trained on ${run.history_years} years; out of sample accuracy ${((run.oos.accuracy ?? 0) * 100).toFixed(0)}%, AUC ${(run.oos.auc ?? 0).toFixed(2)}, top-decile beat-market rate ${((run.oos.top_decile_hit ?? 0) * 100).toFixed(0)}%, extra return ${(run.oos.top_decile_excess_pct ?? 0).toFixed(1)}% per quarter.` + (sector ? ` Sector filter: ${sector}.` : ""),
    data: tab === "odds" ? { visible_rows: filtered.slice(0, shown).map((p, n) => ({ n: n + 1, symbol: p.symbol, odds_pct: Math.round(p.prob_up * 100), buy_rank: p.buy_rank, sector: p.sector, price: p.close })) }
      : tab === "types" ? { trait_profiles: run.profiles, importance: run.importance }
      : tab === "sectors" ? { sectors: run.sectors.slice(0, 25) }
      : tab === "history" ? { band_base_rates: run.band_base_rates }
      : { folds: run.folds, calibration: run.calibration, oos: run.oos },
  } : null, [run, tab, sector, shown, filtered.length]);

  if (error) return <EmptyState icon="⚠" title="Could not load predictions" body={error} />;

  const oos = run?.oos;
  const acc = oos?.accuracy ?? null;

  return (
    <div style={{ display: "grid", gap: 22 }}>
      <PageHeader
        eyebrow={`3-Month Odds · ${run ? `learned from ${run.history_years} years of history` : "beat-the-market model"}`}
        title="Which stocks have the best odds of beating the market?"
        blurb={<>
          A model trained on {run ? `${run.history_years} years` : "up to 20 years"} of NIFTY 500 history estimates each stock&apos;s odds of
          beating the market over the next 3 months. It is tested on years it never saw. Odds are not promises.
        </>}
        aside={run ? <>As of <b style={{ color: "var(--text)" }}>{fmtDate(run.as_of)}</b> · {run.n_tickers} stocks</> : null}
      />

      {!loading && !run && (
        <EmptyState icon="◆" title="No model run yet"
          body={<>Load long history first (<code>python -m jobs.nightly --source yahoo --lookback-days 7300 --full --skip-rank</code>), then train.</>}
          action={<Button onClick={train} disabled={training}>{training ? "Training… (1–3 min)" : "Train the model now"}</Button>} />
      )}

      {run && (
        <>
          <div className="glass fade-up-1" style={{ padding: "12px 16px", borderRadius: 14, fontSize: 13, color: "var(--text-2)", lineHeight: 1.55 }}>
            <b style={{ color: "var(--text)" }}>How to read this page.</b> Three-month stock moves are mostly noise, so no honest model gets far above 50% on single calls.
            The useful signal is in the <b>top-odds group</b>: how often it beat the market, and by how much, in years the model never trained on. Those numbers are below, unpolished.
          </div>

          {/* Honesty row: how good is it, out of sample */}
          <section className="fade-up-1" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
            <StatTile label="Right, out of sample" value={acc == null ? "—" : `${(acc * 100).toFixed(0)}%`} sub="of calls in years the model never saw" tone="good" />
            <StatTile label="Top-odds stocks that beat the market" value={oos?.top_decile_hit == null ? "—" : `${(oos.top_decile_hit * 100).toFixed(0)}%`} sub="top 10% by odds, per test year" tone="strong" />
            <StatTile label="Their extra return" value={oos?.top_decile_excess_pct == null ? "—" : fmtPct(oos.top_decile_excess_pct)} sub="vs the median stock, per 3 months" tone="accent" />
            <StatTile label="Ranking power (AUC)" value={oos?.auc == null ? "—" : oos.auc.toFixed(2)} sub="0.50 = coin flip · 1.00 = perfect" />
            <StatTile label="Market now" value={run.market_now.breadth == null ? "—" : `${Math.round(run.market_now.breadth * 100)}%`} sub={`of stocks in uptrend · median 12-mo move ${fmtPct(run.market_now.mkt_mom_pct, 0)}`} tone="neutral" />
          </section>

          <Tabs<Tab> ariaLabel="Prediction views" value={tab} onChange={setTab} tabs={[
            { id: "odds", label: "Best odds now", icon: "◆", count: filtered.length },
            { id: "types", label: "What type rises", icon: "✦" },
            { id: "sectors", label: "Sector outlook", icon: "▦" },
            { id: "history", label: "20-year base rates", icon: "◷" },
            { id: "model", label: "How it was tested", icon: "⚙" },
          ]} />

          {tab === "odds" && (
            <Section title="Stocks with the best odds of beating the market" sub={`Next ${run.horizon_days} trading days · odds from the model · Strength Score shown for comparison`}
              action={
                <select value={sector} onChange={(e) => setSector(e.target.value)} aria-label="Sector" style={{ padding: "8px 12px", borderRadius: 999, border: "1px solid var(--border)", background: "var(--card)" }}>
                  <option value="">All sectors</option>{sectors.map((s) => <option key={s}>{s}</option>)}
                </select>
              }>
              <div style={{ marginBottom: 14 }}>
                <div className="eyebrow" style={{ marginBottom: 6 }}>How the odds are spread across {filtered.length} stocks</div>
                <OddsHistogram probs={filtered.map((p) => p.prob_up)} />
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 720 }}>
                  <thead><tr style={{ background: "var(--card2)" }}>
                    {["#", "Stock", "Sector", "Odds of beating market", "Strength Score", "Price"].map((h, i) => (
                      <th key={h} className="eyebrow" style={{ textAlign: i >= 3 ? "right" : "left", padding: "12px 14px", whiteSpace: "nowrap" }}>{h}</th>
                    ))}
                  </tr></thead>
                  <tbody>
                    {filtered.slice(0, shown).map((p, n) => <OddsRow key={p.ticker} p={p} n={n} />)}
                  </tbody>
                </table>
              </div>
              <LoadMore shown={Math.min(shown, filtered.length)} total={filtered.length} step={PAGE} onMore={() => setShown((s) => s + PAGE)} />
            </Section>
          )}

          {tab === "types" && (
            <div style={{ display: "grid", gap: 20 }}>
              <Section title="Which traits carry the best odds right now" sub="Average model odds for stocks in the top fifth vs the bottom fifth of each trait, today. Bars further right of the dashed 50% line mean better odds.">
                <ProfileChart profiles={run.profiles} />
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12, marginTop: 16 }}>
                  {run.profiles.map((p) => {
                    const up = p.edge >= 0;
                    return (
                      <div key={p.feature} className="card" style={{ padding: 16, background: up ? "var(--strong-soft)" : "var(--weak-soft)", borderColor: "transparent" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                          <div style={{ fontWeight: 800, textTransform: "capitalize" }}>{p.label}</div>
                          <Pill tone={up ? "strong" : "weak"}>{up ? "high is better" : "low is better"}</Pill>
                        </div>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 12 }}>
                          <Odds label="High" v={p.high_prob} strong={p.high_prob >= p.low_prob} />
                          <Odds label="Low" v={p.low_prob} strong={p.low_prob > p.high_prob} />
                        </div>
                        <div style={{ fontSize: 12.5, color: "var(--text-2)", marginTop: 10, lineHeight: 1.5 }}>
                          {up
                            ? <>Stocks with strong <b>{p.label}</b> have <b>{Math.round(p.edge * 100)} points</b> better odds than those with weak {p.label}.</>
                            : <>Stocks with weak <b>{p.label}</b> currently have <b>{Math.round(-p.edge * 100)} points</b> better odds than those with strong {p.label}.</>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Section>
              <Section title="What the model leans on" sub="Permutation importance on the most recent year: how much ranking power is lost when a trait is scrambled">
                <ImportanceBars rows={run.importance} />
              </Section>
            </div>
          )}

          {tab === "sectors" && (
            <Section title="Sector outlook" sub={`Average odds by sector today. Historically, a sector in the top 3 for 6-month strength stayed ahead of the median sector over the next 3 months ${Math.round((run.sectors[0]?.top3_continuation_rate ?? 0) * 100)}% of the time.`}>
              <div style={{ marginBottom: 16 }}>
                <SectorBars rows={run.sectors.map((s) => ({ sector: s.sector, avg_prob: s.avg_prob * 100 }))} valueKey="avg_prob" label="average odds" max={12} formatter={(v) => `${v.toFixed(0)}%`} />
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 640 }}>
                  <thead><tr style={{ background: "var(--card2)" }}>
                    {["Sector", "Stocks", "Average odds", "6-month strength", "Best odds in sector"].map((h, i) => (
                      <th key={h} className="eyebrow" style={{ textAlign: i === 0 || i === 4 ? "left" : "right", padding: "12px 14px", whiteSpace: "nowrap" }}>{h}</th>
                    ))}
                  </tr></thead>
                  <tbody>
                    {run.sectors.map((s) => (
                      <tr key={s.sector} style={{ borderTop: "1px solid var(--border)" }}>
                        <td style={{ padding: "12px 14px", fontWeight: 700 }}>{s.sector}{s.rs_rank && s.rs_rank <= 3 && <Pill tone="strong">top 3 strength</Pill>}</td>
                        <td className="tnum" style={{ padding: "12px 14px", textAlign: "right", color: "var(--text-2)" }}>{s.n}</td>
                        <td style={{ padding: "12px 14px", textAlign: "right" }}><OddsBar v={s.avg_prob} /></td>
                        <td className="tnum" style={{ padding: "12px 14px", textAlign: "right", fontWeight: 700, color: (s.rel_strength_6m_pct ?? 0) >= 0 ? "var(--strong-ink)" : "var(--weak-ink)" }}>{fmtPct(s.rel_strength_6m_pct)}</td>
                        <td style={{ padding: "12px 14px" }}>{s.top_stock && <Link href={`/rank/${s.top_stock.replace(".NS", "")}`} style={{ fontWeight: 800 }}>{s.top_stock.replace(".NS", "")}</Link>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          )}

          {tab === "history" && (
            <Section title={`What happened after each Strength Score band, ${run.history_start.slice(0, 4)}–${run.as_of.slice(0, 4)}`} sub="Every stock-day in the sample, grouped by the band it was in at the time">
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 14 }}>
                {[21, 63, 126].map((h) => (
                  <div key={h} className="card" style={{ padding: 16, background: "var(--card2)", borderColor: "transparent" }}>
                    <div className="eyebrow" style={{ marginBottom: 10 }}>Next {h === 21 ? "1 month" : h === 63 ? "3 months" : "6 months"}</div>
                    <BaseRateChart rows={run.band_base_rates.filter((r) => r.horizon === h)} />
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, marginTop: 8 }}>
                      <thead><tr>{["Band", "Went up", "Beat market", "Median"].map((x, i) => <th key={x} style={{ textAlign: i ? "right" : "left", paddingBottom: 6, fontSize: 11, color: "var(--text-muted)" }}>{x}</th>)}</tr></thead>
                      <tbody>
                        {run.band_base_rates.filter((r) => r.horizon === h).map((r) => (
                          <tr key={r.band}>
                            <td style={{ padding: "5px 0" }}><Pill tone={r.band.toLowerCase() as "strong" | "good" | "neutral" | "weak"}>{r.band}</Pill></td>
                            <td className="tnum" style={{ textAlign: "right", fontWeight: 700 }}>{Math.round(r.hit_rate * 100)}%</td>
                            <td className="tnum" style={{ textAlign: "right", fontWeight: 700, color: r.beat_market_rate >= 0.5 ? "var(--strong-ink)" : "var(--weak-ink)" }}>{Math.round(r.beat_market_rate * 100)}%</td>
                            <td className="tnum" style={{ textAlign: "right", color: "var(--text-2)" }}>{fmtPct(r.median_return_pct)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ))}
              </div>
              <p style={{ fontSize: 12.5, color: "var(--text-muted)", marginTop: 12, lineHeight: 1.5 }}>
                Read it as base rates, not forecasts: they tell you how often a band was followed by a rise in the past, across {run.n_rows.toLocaleString("en-IN")} stock-days.
                One known bias: the history is that of <em>today&apos;s</em> NIFTY 500 members, so companies that failed and left the index are missing, which flatters every band&apos;s absolute returns. The comparison <em>between</em> bands is less affected.
              </p>
            </Section>
          )}

          {tab === "model" && (
            <div style={{ display: "grid", gap: 20 }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 20 }}>
                <Section title="The model" sub="What it is and how it keeps itself current">
                  <dl style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "8px 14px", fontSize: 13 }}>
                    <dt style={{ color: "var(--text-muted)" }}>Algorithm</dt><dd><b>{live?.model_card.algorithm ?? "HistGradientBoostingClassifier (scikit-learn)"}</b></dd>
                    <dt style={{ color: "var(--text-muted)" }}>Predicts</dt><dd>{live?.model_card.target ?? `whether a stock beats the market median over ${run.horizon_days} trading days`}</dd>
                    <dt style={{ color: "var(--text-muted)" }}>Learns from</dt><dd>7 Strength Score factors, the sector, and two market-state readings (median momentum, breadth)</dd>
                    <dt style={{ color: "var(--text-muted)" }}>Trained on</dt><dd>{run.history_years} years · {run.n_train_rows.toLocaleString("en-IN")} weekly samples · {run.n_tickers} stocks</dd>
                    <dt style={{ color: "var(--text-muted)" }}>Tested by</dt><dd>{live?.model_card.validation ?? "walk-forward by calendar year"}</dd>
                    <dt style={{ color: "var(--text-muted)" }}>Keeps current</dt><dd>{live?.model_card.retrain_policy ?? "retrains automatically when its last training is more than 7 days old"}</dd>
                    <dt style={{ color: "var(--text-muted)" }}>Last trained</dt><dd className="tnum">{fmtDate(run.as_of)}{live && live.training_history.length > 1 && <span style={{ color: "var(--text-muted)" }}> · {live.training_history.length} trainings so far</span>}</dd>
                  </dl>
                </Section>
                <Section title="Live scorecard" sub="Once a batch of predictions is 3 months old, it is scored against real prices. This is the test that never runs out.">
                  {live && live.scores.length > 0 ? (
                    <>
                      <LiveScoreChart scores={live.scores} />
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginTop: 10 }}>
                        <StatTile label="Batches scored" value={live.scores.length} />
                        <StatTile label="Top-odds beat market" value={`${Math.round(live.scores.reduce((s, r) => s + r.top_decile_hit, 0) / live.scores.length * 100)}%`} tone="strong" />
                        <StatTile label="Their extra return" value={fmtPct(live.scores.reduce((s, r) => s + r.top_decile_excess_pct, 0) / live.scores.length)} tone="accent" />
                      </div>
                    </>
                  ) : (
                    <div style={{ padding: "18px 16px", borderRadius: 12, background: "var(--card2)", fontSize: 13.5, lineHeight: 1.6 }}>
                      <b>No batch has matured yet.</b> The first predictions were made on {fmtDate(live?.next_maturity?.run_date ?? run.as_of)}; their 3-month window closes around
                      <b> {fmtDate(live?.next_maturity?.expected_on ?? null)}</b>. From then on this card fills in automatically, one batch per training, and the model retrains itself on the new prices every week.
                    </div>
                  )}
                </Section>
              </div>
              <Section title="Walk-forward test, year by year" sub={`Each year was predicted by a model trained only on earlier years, with labels ending ${run.horizon_days} trading days before the year began. Bars are accuracy on every stock; the line is how often the top-odds group beat the market.`}
                action={<Button onClick={train} disabled={training} variant="ghost">{training ? "Retraining…" : "Retrain now"}</Button>}>
                <FoldsChart folds={run.folds} />
                <div style={{ overflowX: "auto", marginTop: 12 }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 560 }}>
                    <thead><tr style={{ background: "var(--card2)" }}>
                      {["Test year", "Accuracy", "AUC", "Top-odds hit rate", "Top-odds extra return", "Stock-days"].map((h, i) => (
                        <th key={h} className="eyebrow" style={{ textAlign: i ? "right" : "left", padding: "10px 14px", whiteSpace: "nowrap" }}>{h}</th>
                      ))}
                    </tr></thead>
                    <tbody>
                      {run.folds.map((f) => (
                        <tr key={f.year} style={{ borderTop: "1px solid var(--border)" }}>
                          <td style={{ padding: "10px 14px", fontWeight: 700 }}>{f.year}</td>
                          <td className="tnum" style={{ padding: "10px 14px", textAlign: "right", color: f.accuracy >= 0.5 ? "var(--strong-ink)" : "var(--weak-ink)", fontWeight: 700 }}>{(f.accuracy * 100).toFixed(1)}%</td>
                          <td className="tnum" style={{ padding: "10px 14px", textAlign: "right" }}>{f.auc.toFixed(3)}</td>
                          <td className="tnum" style={{ padding: "10px 14px", textAlign: "right" }}>{(f.top_decile_hit * 100).toFixed(0)}%</td>
                          <td className="tnum" style={{ padding: "10px 14px", textAlign: "right", color: f.top_decile_excess_pct >= 0 ? "var(--strong-ink)" : "var(--weak-ink)" }}>{fmtPct(f.top_decile_excess_pct)}</td>
                          <td className="tnum" style={{ padding: "10px 14px", textAlign: "right", color: "var(--text-muted)" }}>{f.n_test.toLocaleString("en-IN")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Section>
              <Section title="Are the odds honest?" sub="When the model said X%, how often did it actually happen? The bars should climb from left to right and track the line.">
                <CalibrationChart rows={run.calibration} />
              </Section>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function OddsRow({ p, n }: { p: PredictionItem; n: number }) {
  return (
    <tr style={{ borderTop: "1px solid var(--border)" }}>
      <td className="tnum" style={{ padding: "12px 14px", color: "var(--text-dim)", fontSize: 12 }}>{n + 1}</td>
      <td style={{ padding: "12px 14px" }}><Link href={`/rank/${p.symbol}`} style={{ fontWeight: 800 }}>{p.symbol}</Link></td>
      <td style={{ padding: "12px 14px", color: "var(--text-2)", fontSize: 13, maxWidth: 220, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{p.sector}</td>
      <td style={{ padding: "12px 14px", textAlign: "right" }}><OddsBar v={p.prob_up} /></td>
      <td className="tnum" style={{ padding: "12px 14px", textAlign: "right", fontWeight: 700 }}>{p.buy_rank ?? "—"}</td>
      <td className="tnum" style={{ padding: "12px 14px", textAlign: "right", color: "var(--text-2)" }}>{fmtINR(p.close)}</td>
    </tr>
  );
}

function OddsBar({ v }: { v: number }) {
  const tone = v >= 0.6 ? "strong" : v >= 0.5 ? "good" : v >= 0.4 ? "neutral" : "weak";
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
      <span aria-hidden style={{ width: 90, height: 8, borderRadius: 999, background: `var(--${tone}-soft)`, overflow: "hidden", display: "inline-block" }}>
        <span style={{ display: "block", width: `${v * 100}%`, height: "100%", background: `var(--${tone})`, borderRadius: 999 }} />
      </span>
      <b className="tnum" style={{ minWidth: 40, textAlign: "right", color: `var(--${tone}-ink)` }}>{Math.round(v * 100)}%</b>
    </span>
  );
}

function Odds({ label, v, strong }: { label: string; v: number; strong: boolean }) {
  return (
    <div style={{ padding: "10px 12px", borderRadius: 12, background: "color-mix(in srgb, var(--card) 70%, transparent)" }}>
      <div className="eyebrow" style={{ fontSize: 10 }}>{label}</div>
      <div className="tnum" style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 24, color: strong ? "var(--strong-ink)" : "var(--text-2)" }}>{Math.round(v * 100)}%</div>
    </div>
  );
}

function ImportanceBars({ rows }: { rows: PredictRun["importance"] }) {
  const max = Math.max(0.001, ...rows.map((r) => r.importance));
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {rows.map((r) => (
        <div key={r.feature} style={{ display: "grid", gridTemplateColumns: "200px 1fr 60px", alignItems: "center", gap: 10 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-2)", textTransform: "capitalize" }}>{r.label}</div>
          <div style={{ height: 12, background: "var(--card2)", borderRadius: 999, overflow: "hidden" }}>
            <div style={{ width: `${Math.max(0, r.importance) / max * 100}%`, height: "100%", background: "var(--accent)", borderRadius: 999 }} />
          </div>
          <div className="tnum" style={{ fontSize: 12.5, textAlign: "right", color: "var(--text-muted)" }}>{r.importance.toFixed(3)}</div>
        </div>
      ))}
    </div>
  );
}
