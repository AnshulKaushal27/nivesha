"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Explanation, type RankDetail } from "@/lib/api";
import { BAND, FACTOR_LABEL, FACTOR_ORDER, fmtDate, fmtINR, fmtPct, logToPct } from "@/lib/signals";
import { BandChip, RankRing } from "@/components/RankRing";
import { FactorBars } from "@/components/FactorBars";
import { RankSparkline } from "@/components/Sparkline";
import { PriceChart } from "@/components/charts";
import { useScreen } from "@/lib/screen";

export default function StockRankPage({ params }: { params: { symbol: string } }) {
  const symbol = decodeURIComponent(params.symbol).toUpperCase();
  const [d, setD] = useState<RankDetail | null>(null);
  const [ex, setEx] = useState<Explanation | null>(null);
  const [exLoading, setExLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.rankDetail(symbol, 120).then(setD).catch((e: Error) => setError(e.message));
  }, [symbol]);

  useScreen(d ? {
    page: "stock", route: `/rank/${symbol}`, title: `${d.symbol} — Buy Rank ${(d.score ?? d.buy_rank).toFixed(1)} (${d.band})`, asOf: d.date,
    summary: `Stock page for ${d.symbol} (${d.sector}). Buy Rank ${(d.score ?? d.buy_rank).toFixed(1)}/100 (position #${d.position} of ${d.universe}), band ${d.band}, price ₹${d.close}, as of ${d.date}.` +
      (ex ? ` AI explanation shown: ${ex.bullets.join(" ")} Watch out: ${ex.watch_out}` : " AI explanation not requested yet."),
    data: {
      buy_rank: d.buy_rank, band: d.band, sector: d.sector, price: d.close, eligible: d.eligible,
      factor_z_scores: d.z, factor_contributions: d.contributions, raw_factor_values: d.raw,
      rank_history_last_10: d.history.slice(-10),
    },
  } : null, [d, ex, symbol]);

  function loadExplanation() {
    setExLoading(true);
    api.rankExplain(symbol).then(setEx).catch((e: Error) => setError(e.message)).finally(() => setExLoading(false));
  }

  if (error) return <div className="card" style={{ padding: 28 }}><b>Something went wrong.</b> <span style={{ color: "var(--text-muted)" }}>{error}</span></div>;
  if (!d) return <div style={{ display: "grid", gap: 16 }}><div className="skeleton" style={{ height: 140 }} /><div className="skeleton" style={{ height: 260 }} /></div>;

  const s = BAND[d.band];
  const raw = d.raw ?? {};
  const facts: { label: string; value: string }[] = [
    { label: "12-month move (skipping last month)", value: fmtPct(logToPct(raw.mom_12_1)) },
    { label: "6-month move (skipping last month)", value: fmtPct(logToPct(raw.mom_6_1)) },
    { label: "Days above 50-day average (last 60)", value: raw.trend_frac == null ? "—" : `${Math.round(raw.trend_frac * 100)}%` },
    { label: "Yearly volatility", value: raw.neg_vol_60 == null ? "—" : `${(-raw.neg_vol_60 * 100).toFixed(1)}%` },
    { label: "Traded per day", value: raw.log_turnover_20 == null ? "—" : `₹${(Math.exp(raw.log_turnover_20) / 1e7).toFixed(1)} cr` },
    { label: "Volume vs usual", value: raw.vol_conf == null ? "—" : `${raw.vol_conf.toFixed(2)}×` },
    { label: "5-day move", value: fmtPct(logToPct(raw.ret_5d)) },
    { label: "RSI (14)", value: raw.rsi14 == null ? "—" : raw.rsi14.toFixed(0) },
  ];

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <Link href="/" style={{ fontSize: 13, fontWeight: 700, color: "var(--text-muted)" }}>← All ranks</Link>

      {/* Header card */}
      <section className="card fade-up" style={{ padding: 24, display: "flex", flexWrap: "wrap", gap: 24, alignItems: "center", position: "relative", overflow: "hidden" }}>
        <div aria-hidden style={{ position: "absolute", left: -60, top: -80, width: 260, height: 260, borderRadius: "50%", background: s.soft, filter: "blur(30px)", opacity: 0.9 }} />
        <RankRing rank={d.score ?? d.buy_rank} band={d.band} size={132} stroke={12} />
        <div style={{ position: "relative", flex: "1 1 260px" }}>
          <div className="eyebrow">{d.sector} · as of {fmtDate(d.date)}</div>
          <h1 style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 38, letterSpacing: "-0.02em", marginTop: 4 }}>{d.symbol}</h1>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center", marginTop: 8 }}>
            <BandChip band={d.band} />
            {d.position && <span className="chip" style={{ background: "var(--accent-soft)", color: "var(--accent-ink)" }}>#{d.position} of {d.universe}</span>}
            <span className="tnum" style={{ fontWeight: 700, color: "var(--text-2)" }}>{fmtINR(d.close)}</span>
            {!d.eligible && <span className="chip" style={{ background: "var(--warn-soft)", color: "var(--neutral-ink)" }}>Not eligible — low liquidity or history</span>}
          </div>
          <p style={{ color: "var(--text-2)", marginTop: 12, maxWidth: 560, lineHeight: 1.55 }}>
            <b style={{ color: s.ink }}>{s.word}.</b> {s.blurb} Scores <b>{(d.score ?? d.buy_rank).toFixed(1)}</b> out of 100 on the factors below{d.position ? <>, position <b>#{d.position}</b> of {d.universe}</> : null}.
          </p>
        </div>
      </section>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 20 }}>
        {/* Why this rank */}
        <section className="card fade-up-1" style={{ padding: 22, display: "grid", gap: 14, alignContent: "start" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
            <h2 style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 18 }}>Why this rank?</h2>
            {!ex && (
              <button onClick={loadExplanation} disabled={exLoading} style={{
                padding: "8px 14px", borderRadius: 999, fontWeight: 800, fontSize: 13,
                background: "var(--accent-soft)", color: "var(--accent-ink)", opacity: exLoading ? 0.6 : 1,
              }}>
                {exLoading ? "Thinking…" : "Explain in plain words ✦"}
              </button>
            )}
          </div>
          {ex ? (
            <div style={{ display: "grid", gap: 10 }}>
              {ex.bullets.map((b, i) => (
                <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start", lineHeight: 1.5 }}>
                  <span aria-hidden style={{ width: 22, height: 22, borderRadius: 7, flex: "0 0 auto", display: "grid", placeItems: "center", background: s.soft, color: s.ink, fontWeight: 800, fontSize: 12 }}>{i + 1}</span>
                  <span>{b}</span>
                </div>
              ))}
              <div style={{ marginTop: 4, padding: "10px 12px", borderRadius: 10, background: "var(--warn-soft)", color: "var(--neutral-ink)", fontSize: 13.5, lineHeight: 1.5 }}>
                <b>Watch out:</b> {ex.watch_out}
              </div>
              <div style={{ fontSize: 11.5, color: "var(--text-dim)" }}>
                {ex.model === "template" ? "Generated from the factor table (no AI model configured)." : `AI-written from the factor table · numbers audited${ex.audit_dropped ? ` · ${ex.audit_dropped} unverifiable line removed` : ""}`}
              </div>
            </div>
          ) : (
            <p style={{ color: "var(--text-muted)", fontSize: 13.5, lineHeight: 1.55 }}>
              Three short sentences on what pushed this stock up or down the list, written only from the numbers on this page.
            </p>
          )}
          <div>
            <div className="eyebrow" style={{ marginBottom: 10 }}>What helped and what hurt</div>
            <FactorBars contributions={d.contributions} />
          </div>
        </section>

        {/* History + facts */}
        <div style={{ display: "grid", gap: 20, alignContent: "start" }}>
          <section className="card fade-up-2" style={{ padding: 22 }}>
            <h2 style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 18, marginBottom: 4 }}>Price, last {d.history.length} trading days</h2>
            <div style={{ fontSize: 12.5, color: "var(--text-muted)", marginBottom: 8 }}>Closing price with its 20-day average. A price above the average means the recent trend is up.</div>
            <PriceChart history={d.history} color={s.fill} />
            <h2 style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 18, marginTop: 18, marginBottom: 4 }}>Rank over time</h2>
            <div style={{ fontSize: 12.5, color: "var(--text-muted)", marginBottom: 8 }}>Buy Rank, 1–100, same period</div>
            <RankSparkline data={d.history} color={s.fill} height={140} />
          </section>
          <section className="card fade-up-3" style={{ padding: 22 }}>
            <h2 style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 18, marginBottom: 12 }}>The numbers behind it</h2>
            <dl style={{ display: "grid", gridTemplateColumns: "1fr auto", rowGap: 10, columnGap: 16, fontSize: 13.5 }}>
              {facts.map((f) => (
                <FactRow key={f.label} label={f.label} value={f.value} />
              ))}
            </dl>
          </section>
        </div>
      </div>

      {/* Glossary */}
      <section className="card fade-up-4" style={{ padding: 22 }}>
        <h2 style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 18, marginBottom: 12 }}>What the factors mean</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 12 }}>
          {FACTOR_ORDER.map((k) => (
            <div key={k} style={{ padding: "12px 14px", borderRadius: 12, background: "var(--card2)" }}>
              <div style={{ fontWeight: 800, fontSize: 13.5 }}>{FACTOR_LABEL[k].name}</div>
              <div style={{ fontSize: 12.5, color: "var(--text-2)", marginTop: 4, lineHeight: 1.5 }}>{FACTOR_LABEL[k].plain}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function FactRow({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt style={{ color: "var(--text-2)" }}>{label}</dt>
      <dd className="tnum" style={{ fontWeight: 800, textAlign: "right" }}>{value}</dd>
    </>
  );
}
