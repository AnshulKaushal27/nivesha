"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api, type Band, type RankItem, type SectorRow } from "@/lib/api";
import { BAND, fmtDate, fmtINR } from "@/lib/signals";
import { BandChip, RankRing } from "@/components/RankRing";
import { FactorBars } from "@/components/FactorBars";

const BANDS: Band[] = ["Strong", "Good", "Neutral", "Weak"];

export default function RankPage() {
  const [items, setItems] = useState<RankItem[]>([]);
  const [date, setDate] = useState<string | null>(null);
  const [sectors, setSectors] = useState<SectorRow[]>([]);
  const [sector, setSector] = useState("");
  const [band, setBand] = useState<Band | "">("");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([api.rank({ limit: 600 }), api.rankSectors()])
      .then(([r, s]) => { setItems(r.items); setDate(r.date); setSectors(s.sectors); setError(null); })
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

  if (error) return <ErrorState message={error} />;

  return (
    <div style={{ display: "grid", gap: 24 }}>
      {/* Hero */}
      <section className="fade-up" style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 16 }}>
        <div>
          <div className="eyebrow">Buy Rank · NIFTY 500</div>
          <h1 style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 34, letterSpacing: "-0.02em", marginTop: 6 }}>
            Which stocks look strongest today?
          </h1>
          <p style={{ color: "var(--text-2)", marginTop: 8, maxWidth: 640, lineHeight: 1.55 }}>
            Every stock gets a score from 1 to 100 based on trend, momentum, calmness and liquidity.
            Higher is stronger. It is a ranking, not advice.
          </p>
        </div>
        <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
          {loading ? <span className="skeleton" style={{ display: "inline-block", width: 140, height: 16 }} /> : <>As of <b style={{ color: "var(--text)" }}>{fmtDate(date)}</b> · {items.length} stocks ranked</>}
        </div>
      </section>

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

      {/* Top three spotlight */}
      {!loading && top.length > 0 && (
        <section className="fade-up-2" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 14 }}>
          {top.map((i, n) => (
            <Link key={i.ticker} href={`/rank/${i.symbol}`} className="card" style={{ padding: 18, display: "grid", gap: 14, position: "relative", overflow: "hidden" }}>
              <div aria-hidden style={{ position: "absolute", right: -30, top: -30, width: 140, height: 140, borderRadius: "50%", background: BAND[i.band].soft, opacity: 0.8 }} />
              <div style={{ display: "flex", gap: 14, alignItems: "center", position: "relative" }}>
                <RankRing rank={i.buy_rank} band={i.band} size={84} />
                <div style={{ minWidth: 0 }}>
                  <div className="eyebrow">#{n + 1} {sector ? `in ${sector}` : "overall"}</div>
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
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 820 }}>
            <thead>
              <tr style={{ background: "var(--card2)" }}>
                {["#", "Stock", "Sector", "Rank", "Band", "Price", "What drives it"].map((h, i) => (
                  <th key={h} className="eyebrow" style={{ textAlign: i >= 3 && i <= 5 ? "right" : "left", padding: "12px 14px", fontWeight: 800, whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && Array.from({ length: 10 }).map((_, i) => (
                <tr key={i}><td colSpan={7} style={{ padding: 10 }}><div className="skeleton" style={{ height: 34 }} /></td></tr>
              ))}
              {!loading && filtered.map((i, n) => {
                const s = BAND[i.band];
                const drivers = Object.entries(i.contributions ?? {}).filter(([, v]) => v != null).sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0));
                const best = drivers[0]?.[0]; const worst = drivers[drivers.length - 1]?.[0];
                return (
                  <tr key={i.ticker} style={{ borderTop: "1px solid var(--border)" }}>
                    <td className="tnum" style={{ padding: "12px 14px", color: "var(--text-dim)", fontSize: 12 }}>{n + 1}</td>
                    <td style={{ padding: "12px 14px" }}>
                      <Link href={`/rank/${i.symbol}`} style={{ fontWeight: 800, color: "var(--text)" }}>{i.symbol}</Link>
                    </td>
                    <td style={{ padding: "12px 14px", color: "var(--text-2)", fontSize: 13, maxWidth: 200, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{i.sector}</td>
                    <td style={{ padding: "12px 14px", textAlign: "right" }}>
                      <div style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
                        <div aria-hidden style={{ width: 72, height: 8, borderRadius: 999, background: s.soft, overflow: "hidden" }}>
                          <div style={{ width: `${i.buy_rank}%`, height: "100%", background: s.fill, borderRadius: 999 }} />
                        </div>
                        <b className="tnum" style={{ minWidth: 28, textAlign: "right" }}>{i.buy_rank}</b>
                      </div>
                    </td>
                    <td style={{ padding: "12px 14px", textAlign: "right" }}><BandChip band={i.band} size="sm" /></td>
                    <td className="tnum" style={{ padding: "12px 14px", textAlign: "right", color: "var(--text-2)" }}>{fmtINR(i.close)}</td>
                    <td style={{ padding: "10px 14px", fontSize: 12 }}>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                        {best && <span className="chip" style={{ background: "var(--strong-soft)", color: "var(--strong-ink)", whiteSpace: "nowrap" }}>▲ {label(best)}</span>}
                        {worst && worst !== best && <span className="chip" style={{ background: "var(--weak-soft)", color: "var(--weak-ink)", whiteSpace: "nowrap" }}>▼ {label(worst)}</span>}
                      </div>
                    </td>
                  </tr>
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
      </section>
    </div>
  );
}

function label(k: string) {
  return ({ mom_12_1: "12-mo momentum", mom_6_1: "6-mo momentum", trend: "trend", low_vol: "calmness",
            liquidity: "liquidity", vol_conf: "volume", overheat: "overheat" } as Record<string, string>)[k] ?? k;
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
