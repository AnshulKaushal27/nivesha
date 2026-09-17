"use client";

import Link from "next/link";
import { Fragment, useEffect, useMemo, useState } from "react";
import { api, type Band, type Movers, type RankRow, type SectorRow } from "@/lib/api";
import { BAND, fmtDate, fmtINR, fmtPct } from "@/lib/signals";
import { RankRing } from "@/components/RankRing";
import { FactorBars } from "@/components/FactorBars";
import { LoadMore, PageHeader, Section } from "@/components/ui";
import { BandDonut, FactorStrip, MoversChart, SectorBars } from "@/components/charts";
import { useScreen } from "@/lib/screen";

const BANDS: Band[] = ["Strong", "Good", "Neutral", "Weak"];
const PAGE = 20;

export default function RankPage() {
  const [items, setItems] = useState<RankRow[]>([]);
  const [universe, setUniverse] = useState(0);
  const [date, setDate] = useState<string | null>(null);
  const [compareDate, setCompareDate] = useState<string | null>(null);
  const [movers, setMovers] = useState<Movers | null>(null);
  const [sectors, setSectors] = useState<SectorRow[]>([]);
  const [sector, setSector] = useState("");
  const [band, setBand] = useState<Band | "">("");
  const [q, setQ] = useState("");
  const [shown, setShown] = useState(PAGE);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { setShown(PAGE); }, [sector, band, q]);

  useEffect(() => {
    setLoading(true);
    Promise.all([api.rank({ limit: 600 }), api.rankSectors(), api.rankMovers(20, 6)])
      .then(([r, s, m]) => { setItems(r.items); setUniverse(r.universe ?? r.items.length); setDate(r.date); setCompareDate(r.compare_date ?? null); setSectors(s.sectors); setMovers(m); setError(null); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => items.filter((i) =>
    (!sector || i.sector === sector) && (!band || i.band === band) &&
    (!q || i.symbol.toLowerCase().includes(q.toLowerCase()) || (i.sector ?? "").toLowerCase().includes(q.toLowerCase()))
  ), [items, sector, band, q]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    items.forEach((i) => { c[i.band] = (c[i.band] ?? 0) + 1; });
    return c;
  }, [items]);

  const top = filtered.slice(0, 3);

  useScreen(loading ? null : {
    page: "rank", route: "/", title: "Strength Score — NIFTY 500", asOf: date,
    summary: `Strength Score list as of ${date}. ${items.length} stocks ranked; ${counts.Strong ?? 0} Strong, ${counts.Good ?? 0} Good, ${counts.Neutral ?? 0} Neutral, ${counts.Weak ?? 0} Weak.` +
      (sector || band || q ? ` Filters: ${[sector && `sector=${sector}`, band && `band=${band}`, q && `search="${q}"`].filter(Boolean).join(", ")}. ${filtered.length} match.` : ""),
    data: {
      visible_rows: filtered.slice(0, shown).map((i) => ({ position: i.position, symbol: i.symbol, score: i.score, rank_bucket: i.buy_rank, band: i.band, sector: i.sector, price: i.close,
        rank_change_1m: i.rank_change_20d, price_change_1m_pct: i.price_change_20d_pct, model_odds_pct: i.prob_up == null ? null : Math.round(i.prob_up * 100), factor_contributions: i.contributions })),
      showing: Math.min(shown, filtered.length), of: filtered.length,
      biggest_movers_1m: movers ? { risers: movers.risers.map((m) => `${m.symbol} ${m.from_rank}→${m.to_rank}`), fallers: movers.fallers.map((m) => `${m.symbol} ${m.from_rank}→${m.to_rank}`) } : null,
    },
  }, [loading, date, items.length, sector, band, q, shown, filtered.length, movers]);

  if (error) return <ErrorState message={error} />;

  return (
    <div style={{ display: "grid", gap: 24 }}>
      <PageHeader
        eyebrow="Strength Rank · NIFTY 500 · updated nightly"
        title="Which stocks are strongest today?"
        blurb="Every NIFTY 500 stock gets a Strength Score from 1 to 100 based on its trend, momentum, calmness and liquidity. Higher is stronger. It describes today, it does not predict, and it is not advice."
        aside={loading ? <span className="skeleton" style={{ display: "inline-block", width: 140, height: 16 }} /> : <>As of <b style={{ color: "var(--text)" }}>{fmtDate(date)}</b> · {items.length} stocks ranked</>}
      />

      {/* Band summary — colour + word + count */}
      <section className="fade-up-1" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
        {BANDS.map((b) => {
          const s = BAND[b];
          const active = band === b;
          return (
            <button key={b} onClick={() => setBand(active ? "" : b)} aria-pressed={active} className="card" style={{
              textAlign: "left", padding: "16px 18px", borderColor: active ? s.fill : "var(--border)",
              background: active ? s.soft : "var(--card)", transition: "all 0.15s",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span className="chip-dot" style={{ background: s.fill, width: 10, height: 10 }} aria-hidden />
                <span style={{ fontWeight: 800, color: s.ink }}>{s.word}</span>
              </div>
              <div className="tnum" style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 28, marginTop: 6 }}>
                {loading ? "…" : counts[b] ?? 0}
              </div>
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>{s.blurb}</div>
            </button>
          );
        })}
      </section>

      {/* Picture of the market */}
      {!loading && items.length > 0 && (
        <section className="fade-up-2" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 14 }}>
          <Section title="How the market splits" sub="Share of ranked stocks in each band today">
            <BandDonut counts={counts} total={items.length} />
          </Section>
          <Section title="Biggest moves this month" sub={compareDate ? `Change in Strength Score since ${fmtDate(compareDate)}` : "Change in Strength Score over 20 trading days"}>
            {movers && (movers.risers.length || movers.fallers.length)
              ? <MoversChart risers={movers.risers} fallers={movers.fallers} />
              : <div style={{ color: "var(--text-muted)", fontSize: 13 }}>Needs a month of rank history.</div>}
          </Section>
          <Section title="Strongest sectors" sub="Average Strength Score, top sectors">
            <SectorBars rows={sectors.map((s) => ({ sector: s.sector, count: s.count, avg_rank: s.avg_rank }))} max={8} height={220} />
          </Section>
        </section>
      )}

      {/* Top three spotlight */}
      {!loading && top.length > 0 && (
        <section className="fade-up-2" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 14 }}>
          {top.map((i, n) => (
            <Link key={i.ticker} href={`/rank/${i.symbol}`} className="card" style={{ padding: 18, display: "grid", gap: 14, position: "relative", overflow: "hidden" }}>
              <div aria-hidden style={{ position: "absolute", right: -30, top: -30, width: 140, height: 140, borderRadius: "50%", background: BAND[i.band].soft, opacity: 0.8 }} />
              <div style={{ display: "flex", gap: 14, alignItems: "center", position: "relative" }}>
                <RankRing rank={i.score ?? i.buy_rank} band={i.band} size={84} />
                <div style={{ minWidth: 0 }}>
                  <div className="eyebrow">#{sector || band || q ? n + 1 : i.position ?? n + 1} {sector ? `in ${sector}` : `of ${universe}`}</div>
                  <div style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 22, letterSpacing: "-0.01em", marginTop: 2 }}>{i.symbol}</div>
                  <div style={{ fontSize: 12.5, color: "var(--text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{i.sector} · {fmtINR(i.close)}</div>
                </div>
              </div>
              <FactorBars contributions={i.contributions} compact />
            </Link>
          ))}
        </section>
      )}

      {/* Filters */}
      <section className="fade-up-3" style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search a stock or sector…" aria-label="Search"
               style={{ flex: "1 1 220px", maxWidth: 320, padding: "10px 14px", borderRadius: 999, border: "1px solid var(--border)", background: "var(--card)", outline: "none" }} />
        <select value={sector} onChange={(e) => setSector(e.target.value)} aria-label="Sector"
                style={{ padding: "10px 14px", borderRadius: 999, border: "1px solid var(--border)", background: "var(--card)" }}>
          <option value="">All sectors</option>
          {sectors.map((s) => <option key={s.sector} value={s.sector}>{s.sector} ({s.count})</option>)}
        </select>
        {(band || sector || q) && (
          <button onClick={() => { setBand(""); setSector(""); setQ(""); }} style={{ fontSize: 13, fontWeight: 700, color: "var(--accent-ink)", padding: "8px 12px", borderRadius: 999, background: "var(--accent-soft)" }}>
            Clear filters
          </button>
        )}
        <span style={{ marginLeft: "auto", fontSize: 13, color: "var(--text-muted)" }}>{filtered.length} shown</span>
      </section>

      {/* Table */}
      <section className="card fade-up-4" style={{ overflow: "hidden" }}>
        <div style={{ padding: "12px 16px", fontSize: 12.5, color: "var(--text-2)", background: "var(--accent-soft)", lineHeight: 1.5 }}>
          <b style={{ color: "var(--accent-ink)" }}>How to read the score.</b> Strength Score is a percentile of the {universe || "~470"} stocks ranked today: <b>100.0 is the single strongest stock</b>, each step down is {universe ? (100 / universe).toFixed(1) : "0.2"} points, and 50.0 is the middle of the pack.
          The bands (Strong, Good, Neutral, Weak) use the whole-number version. Ties are broken by the underlying factor score.
        </div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 860 }}>
            <thead>
              <tr style={{ background: "var(--card2)" }}>
                {[
                  ["#", "left"], ["Stock", "left"], ["Rank", "right"], ["1-month change", "right"], ["Price · 1 month", "right"], ["Model odds", "right"], ["Factors", "left"],
                ].map(([h, align]) => (
                  <th key={h} className="eyebrow" style={{ textAlign: align as "left" | "right", padding: "12px 14px", fontWeight: 800, whiteSpace: "nowrap" }}
                      title={h === "Factors" ? "Seven cells: 12-month momentum, 6-month momentum, trend, calmness, liquidity, volume, overheat. Green helped the rank, rose hurt it. Hover a cell." : h === "Model odds" ? "Odds of beating the market over the next 3 months, from the Predictions model" : undefined}>
                    {h}{h === "Factors" && <span style={{ fontWeight: 500, textTransform: "none", letterSpacing: 0, marginLeft: 6, color: "var(--text-dim)" }}>12m · 6m · trend · calm · liq · vol · heat</span>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && Array.from({ length: 10 }).map((_, i) => (
                <tr key={i}><td colSpan={7} style={{ padding: 10 }}><div className="skeleton" style={{ height: 34 }} /></td></tr>
              ))}
              {!loading && filtered.slice(0, shown).map((i, n, arr) => {
                const s = BAND[i.band];
                const newGroup = n === 0 || arr[n - 1].band !== i.band;
                const groupCount = filtered.filter((x) => x.band === i.band).length;
                const rc = i.rank_change_20d; const pc = i.price_change_20d_pct; const odds = i.prob_up;
                return (
                  <Fragment key={i.ticker}>
                    {newGroup && !band && (
                      <tr>
                        <td colSpan={7} style={{ padding: "8px 14px", background: s.soft, color: s.ink, fontSize: 12, fontWeight: 800, letterSpacing: "0.04em" }}>
                          <span className="chip-dot" style={{ background: s.fill, display: "inline-block", marginRight: 8, verticalAlign: "middle" }} />
                          {s.word.toUpperCase()} · {groupCount} stocks · {s.blurb}
                        </td>
                      </tr>
                    )}
                    <tr style={{ borderTop: "1px solid var(--border)" }}>
                      <td className="tnum" style={{ padding: "11px 14px", color: "var(--text-muted)", fontSize: 12, fontWeight: 700 }}>#{sector || band || q ? n + 1 : i.position ?? n + 1}</td>
                      <td style={{ padding: "11px 14px" }}>
                        <Link href={`/rank/${i.symbol}`} style={{ fontWeight: 800, color: "var(--text)" }}>{i.symbol}</Link>
                        <div style={{ fontSize: 11.5, color: "var(--text-muted)", maxWidth: 220, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{i.sector}</div>
                      </td>
                      <td style={{ padding: "11px 14px", textAlign: "right" }}>
                        <div style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
                          <div aria-hidden style={{ width: 64, height: 8, borderRadius: 999, background: s.soft, overflow: "hidden" }}>
                            <div style={{ width: `${i.score ?? i.buy_rank}%`, height: "100%", background: s.fill, borderRadius: 999 }} />
                          </div>
                          <b className="tnum" style={{ minWidth: 40, textAlign: "right", fontSize: 15 }}>{(i.score ?? i.buy_rank).toFixed(1)}</b>
                        </div>
                      </td>
                      <td className="tnum" style={{ padding: "11px 14px", textAlign: "right", fontWeight: 800, color: rc == null ? "var(--text-dim)" : rc > 0 ? "var(--strong-ink)" : rc < 0 ? "var(--weak-ink)" : "var(--text-muted)" }}>
                        {rc == null ? "—" : rc > 0 ? `▲ ${rc}` : rc < 0 ? `▼ ${-rc}` : "· 0"}
                      </td>
                      <td className="tnum" style={{ padding: "11px 14px", textAlign: "right" }}>
                        <div style={{ color: "var(--text-2)" }}>{fmtINR(i.close)}</div>
                        <div style={{ fontSize: 11.5, fontWeight: 700, color: pc == null ? "var(--text-dim)" : pc >= 0 ? "var(--strong-ink)" : "var(--weak-ink)" }}>{fmtPct(pc)}</div>
                      </td>
                      <td className="tnum" style={{ padding: "11px 14px", textAlign: "right" }}>
                        {odds == null ? <span style={{ color: "var(--text-dim)" }}>—</span> : (
                          <span className="chip" style={{ background: odds >= 0.6 ? "var(--strong-soft)" : odds >= 0.5 ? "var(--good-soft)" : odds >= 0.4 ? "var(--neutral-soft)" : "var(--weak-soft)",
                                                          color: odds >= 0.6 ? "var(--strong-ink)" : odds >= 0.5 ? "var(--good-ink)" : odds >= 0.4 ? "var(--neutral-ink)" : "var(--weak-ink)" }}>
                            {Math.round(odds * 100)}%
                          </span>
                        )}
                      </td>
                      <td style={{ padding: "11px 14px" }}><FactorStrip contributions={i.contributions} /></td>
                    </tr>
                  </Fragment>
                );
              })}
              {!loading && filtered.length === 0 && (
                <tr><td colSpan={7} style={{ padding: 40, textAlign: "center", color: "var(--text-muted)" }}>
                  {items.length === 0 ? "No ranks yet. Run the nightly job to load data." : "Nothing matches these filters."}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
        {!loading && <LoadMore shown={Math.min(shown, filtered.length)} total={filtered.length} step={PAGE} onMore={() => setShown((s) => s + PAGE)} />}
      </section>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="card" style={{ padding: 32, textAlign: "center" }}>
      <div style={{ fontSize: 28 }} aria-hidden>⚠</div>
      <div style={{ fontWeight: 800, marginTop: 8 }}>Could not reach the backend</div>
      <div style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 4 }}>{message}</div>
      <div style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 12 }}>Start it with <code>uvicorn main:app --reload</code> in <code>backend/</code>.</div>
    </div>
  );
}
