"use client";

/**
 * Chart kit. Rules applied throughout (see dataviz skill):
 * one hue for magnitude, fixed categorical order for identity, status colours
 * only where they carry meaning, a legend for ≥2 series, tooltips everywhere,
 * thin marks, recessive grid, text in ink tokens never in series colour.
 */

import {
  Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart, Pie, PieChart,
  ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { Band } from "@/lib/api";
import { BAND, fmtDate, fmtPct } from "@/lib/signals";

const TIP = { borderRadius: 12, border: "1px solid var(--border)", background: "var(--card)", boxShadow: "var(--shadow-lg)", fontSize: 12, color: "var(--text)" };
const AXIS = { fontSize: 11, fill: "var(--text-muted)" };
const pct0 = (v: number) => `${Math.round(v * 100)}%`;

function Box({ h, children }: { h: number; children: React.ReactElement }) {
  return <div style={{ width: "100%", height: h }}><ResponsiveContainer>{children}</ResponsiveContainer></div>;
}

/* ── Band donut: how today's universe splits ────────────────────────── */
export function BandDonut({ counts, total }: { counts: Record<string, number>; total: number }) {
  const bands: Band[] = ["Strong", "Good", "Neutral", "Weak"];
  const data = bands.map((b) => ({ name: b, value: counts[b] ?? 0 }));
  return (
    <div style={{ display: "grid", gridTemplateColumns: "150px 1fr", gap: 12, alignItems: "center" }}>
      <div style={{ position: "relative", width: 150, height: 150 }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie data={data} dataKey="value" innerRadius={48} outerRadius={70} paddingAngle={2} stroke="var(--card)" strokeWidth={2} isAnimationActive={false}>
              {data.map((d) => <Cell key={d.name} fill={BAND[d.name as Band].fill} />)}
            </Pie>
            <Tooltip contentStyle={TIP} formatter={(v: number, n: string) => [`${v} stocks`, n]} />
          </PieChart>
        </ResponsiveContainer>
        <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", pointerEvents: "none", textAlign: "center" }}>
          <div><div className="tnum" style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 22 }}>{total}</div><div style={{ fontSize: 10.5, color: "var(--text-muted)" }}>ranked</div></div>
        </div>
      </div>
      <div style={{ display: "grid", gap: 6 }}>
        {data.map((d) => (
          <div key={d.name} style={{ display: "grid", gridTemplateColumns: "10px 1fr auto", alignItems: "center", gap: 8, fontSize: 12.5 }}>
            <span className="chip-dot" style={{ background: BAND[d.name as Band].fill, width: 10, height: 10 }} />
            <span style={{ color: "var(--text-2)" }}>{d.name}</span>
            <b className="tnum">{d.value} <span style={{ color: "var(--text-muted)", fontWeight: 500 }}>· {total ? Math.round(d.value / total * 100) : 0}%</span></b>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Sector bars: average rank per sector (magnitude → one hue) ─────── */
export function SectorBars({ rows, valueKey = "avg_rank", label = "avg rank", max = 12, height, formatter }: {
  rows: { sector: string; [k: string]: number | string }[]; valueKey?: string; label?: string; max?: number; height?: number; formatter?: (v: number) => string;
}) {
  const data = rows.slice(0, max).map((r) => ({ ...r, sector: String(r.sector).length > 22 ? String(r.sector).slice(0, 21) + "…" : r.sector }));
  const fmt = formatter ?? ((v: number) => v.toFixed(1));
  return (
    <Box h={height ?? Math.max(160, data.length * 26 + 30)}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 40, bottom: 0, left: 8 }} barCategoryGap={6}>
        <CartesianGrid horizontal={false} stroke="var(--grid)" />
        <XAxis type="number" tick={AXIS} axisLine={false} tickLine={false} tickFormatter={fmt} />
        <YAxis type="category" dataKey="sector" width={150} tick={{ ...AXIS, fill: "var(--text-2)" }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={TIP} cursor={{ fill: "var(--card2)" }} formatter={(v: number) => [fmt(v), label]} />
        <Bar dataKey={valueKey} fill="var(--good)" radius={[0, 4, 4, 0]} isAnimationActive={false} label={{ position: "right", fontSize: 11, fill: "var(--text-2)", formatter: (v: number) => fmt(v) }} />
      </BarChart>
    </Box>
  );
}

/* ── Histogram of scores, bucketed by 10, coloured by band meaning ─── */
export function RankHistogram({ ranks, regime = null }: { ranks: number[]; regime?: string | null }) {
  const buckets = Array.from({ length: 10 }, (_, i) => ({ lo: i * 10 + 1, hi: i * 10 + 10, n: 0 }));
  ranks.forEach((r) => { const i = Math.min(9, Math.max(0, Math.ceil(r / 10) - 1)); buckets[i].n++; });
  const data = buckets.map((b) => ({ name: `${b.lo}–${b.hi}`, n: b.n, band: bandForRank(b.hi, regime) }));
  return (
    <Box h={170}>
      <BarChart data={data} margin={{ top: 14, right: 8, bottom: 0, left: -20 }}>
        <CartesianGrid vertical={false} stroke="var(--grid)" />
        <XAxis dataKey="name" tick={AXIS} axisLine={{ stroke: "var(--axis)" }} tickLine={false} interval={0} />
        <YAxis tick={AXIS} axisLine={false} tickLine={false} allowDecimals={false} />
        <Tooltip contentStyle={TIP} cursor={{ fill: "var(--card2)" }} formatter={(v: number, _n, p) => [`${v} stocks`, `Rank ${p.payload.name} · ${p.payload.band}`]} />
        <Bar dataKey="n" radius={[4, 4, 0, 0]} isAnimationActive={false} label={{ position: "top", fontSize: 10.5, fill: "var(--text-muted)" }}>
          {data.map((d) => <Cell key={d.name} fill={BAND[d.band].fill} />)}
        </Bar>
      </BarChart>
    </Box>
  );
}
function bandForRank(r: number, regime: string | null): Band {
  const [s, g, n] = regime === "Cloudy" ? [85, 70, 50] : [80, 60, 40];
  return r >= s ? "Strong" : r >= g ? "Good" : r >= n ? "Neutral" : "Weak";
}

/* ── Odds histogram (5-point buckets) ───────────────────────────────── */
export function OddsHistogram({ probs }: { probs: number[] }) {
  const lo = 20, hi = 80;
  const buckets = Array.from({ length: (hi - lo) / 5 }, (_, i) => ({ from: lo + i * 5, n: 0 }));
  probs.forEach((p) => { const v = Math.round(p * 100); const i = Math.min(buckets.length - 1, Math.max(0, Math.floor((v - lo) / 5))); buckets[i].n++; });
  const data = buckets.map((b) => ({ name: `${b.from}%`, n: b.n, tone: b.from >= 60 ? "strong" : b.from >= 50 ? "good" : b.from >= 40 ? "neutral" : "weak" }));
  return (
    <Box h={170}>
      <BarChart data={data} margin={{ top: 14, right: 8, bottom: 0, left: -20 }}>
        <CartesianGrid vertical={false} stroke="var(--grid)" />
        <XAxis dataKey="name" tick={AXIS} axisLine={{ stroke: "var(--axis)" }} tickLine={false} />
        <YAxis tick={AXIS} axisLine={false} tickLine={false} allowDecimals={false} />
        <ReferenceLine x="50%" stroke="var(--axis)" strokeDasharray="4 4" label={{ value: "coin flip", position: "top", fontSize: 10, fill: "var(--text-muted)" }} />
        <Tooltip contentStyle={TIP} cursor={{ fill: "var(--card2)" }} formatter={(v: number, _n, p) => [`${v} stocks`, `odds ${p.payload.name}–${parseInt(p.payload.name) + 5}%`]} />
        <Bar dataKey="n" radius={[4, 4, 0, 0]} isAnimationActive={false}>
          {data.map((d) => <Cell key={d.name} fill={`var(--${d.tone})`} />)}
        </Bar>
      </BarChart>
    </Box>
  );
}

/* ── Calibration: said vs happened ─────────────────────────────────── */
export function CalibrationChart({ rows }: { rows: { bin_lo: number; bin_hi: number; predicted: number; actual: number; n: number }[] }) {
  const data = rows.map((r) => ({ name: `${Math.round(r.bin_lo * 100)}–${Math.round(r.bin_hi * 100)}%`, said: r.predicted, happened: r.actual, n: r.n }));
  return (
    <Box h={220}>
      <ComposedChart data={data} margin={{ top: 10, right: 12, bottom: 0, left: -16 }}>
        <CartesianGrid vertical={false} stroke="var(--grid)" />
        <XAxis dataKey="name" tick={AXIS} axisLine={{ stroke: "var(--axis)" }} tickLine={false} />
        <YAxis domain={[0, 1]} tickFormatter={pct0} tick={AXIS} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={TIP} cursor={{ fill: "var(--card2)" }} formatter={(v: number, n: string) => [pct0(v), n === "said" ? "Model said" : "Actually beat market"]} />
        <Legend formatter={(v: string) => <span style={{ color: "var(--text-2)", fontSize: 12 }}>{v === "said" ? "Model said" : "Actually happened"}</span>} />
        <Bar dataKey="happened" fill="var(--series-1)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
        <Line dataKey="said" stroke="var(--series-2)" strokeWidth={2} dot={{ r: 4, strokeWidth: 2, stroke: "var(--card)" }} isAnimationActive={false} />
      </ComposedChart>
    </Box>
  );
}

/* ── Walk-forward folds: accuracy per test year vs 50% ──────────────── */
export function FoldsChart({ folds }: { folds: { year: number; accuracy: number; top_decile_hit: number; top_decile_excess_pct: number }[] }) {
  return (
    <Box h={230}>
      <ComposedChart data={folds} margin={{ top: 10, right: 12, bottom: 0, left: -16 }}>
        <CartesianGrid vertical={false} stroke="var(--grid)" />
        <XAxis dataKey="year" tick={AXIS} axisLine={{ stroke: "var(--axis)" }} tickLine={false} />
        <YAxis domain={[0.4, 0.65]} tickFormatter={pct0} tick={AXIS} axisLine={false} tickLine={false} />
        <ReferenceLine y={0.5} stroke="var(--axis)" strokeDasharray="4 4" label={{ value: "coin flip", position: "insideTopLeft", fontSize: 10, fill: "var(--text-muted)" }} />
        <Tooltip contentStyle={TIP} cursor={{ fill: "var(--card2)" }} formatter={(v: number, n: string) => [pct0(v), n === "accuracy" ? "Accuracy" : "Top-odds beat market"]} />
        <Legend formatter={(v: string) => <span style={{ color: "var(--text-2)", fontSize: 12 }}>{v === "accuracy" ? "Accuracy, all stocks" : "Top-odds group beat market"}</span>} />
        <Bar dataKey="accuracy" radius={[4, 4, 0, 0]} isAnimationActive={false}>
          {folds.map((f) => <Cell key={f.year} fill={f.accuracy >= 0.5 ? "var(--series-1)" : "var(--weak)"} />)}
        </Bar>
        <Line dataKey="top_decile_hit" stroke="var(--series-3)" strokeWidth={2} dot={{ r: 3, strokeWidth: 2, stroke: "var(--card)" }} isAnimationActive={false} />
      </ComposedChart>
    </Box>
  );
}

/* ── Trait profiles: high vs low quintile odds ──────────────────────── */
export function ProfileChart({ profiles }: { profiles: { label: string; high_prob: number; low_prob: number }[] }) {
  const data = profiles.map((p) => ({ name: p.label.length > 26 ? p.label.slice(0, 25) + "…" : p.label, High: p.high_prob, Low: p.low_prob }));
  return (
    <Box h={Math.max(200, data.length * 40 + 40)}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 40, bottom: 0, left: 8 }} barCategoryGap={10} barGap={2}>
        <CartesianGrid horizontal={false} stroke="var(--grid)" />
        <XAxis type="number" domain={[0.3, 0.7]} tickFormatter={pct0} tick={AXIS} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="name" width={170} tick={{ ...AXIS, fill: "var(--text-2)" }} axisLine={false} tickLine={false} />
        <ReferenceLine x={0.5} stroke="var(--axis)" strokeDasharray="4 4" />
        <Tooltip contentStyle={TIP} cursor={{ fill: "var(--card2)" }} formatter={(v: number, n: string) => [pct0(v), `${n} on this trait`]} />
        <Legend formatter={(v: string) => <span style={{ color: "var(--text-2)", fontSize: 12 }}>{v === "High" ? "Stocks high on the trait" : "Stocks low on the trait"}</span>} />
        <Bar dataKey="High" fill="var(--series-1)" radius={[0, 4, 4, 0]} isAnimationActive={false} label={{ position: "right", fontSize: 10.5, fill: "var(--text-2)", formatter: pct0 }} />
        <Bar dataKey="Low" fill="var(--series-2)" radius={[0, 4, 4, 0]} isAnimationActive={false} label={{ position: "right", fontSize: 10.5, fill: "var(--text-2)", formatter: pct0 }} />
      </BarChart>
    </Box>
  );
}

/* ── Band base rates: grouped bars per band ─────────────────────────── */
export function BaseRateChart({ rows }: { rows: { band: string; hit_rate: number; beat_market_rate: number }[] }) {
  return (
    <Box h={200}>
      <BarChart data={rows} margin={{ top: 14, right: 8, bottom: 0, left: -16 }} barCategoryGap={18} barGap={3}>
        <CartesianGrid vertical={false} stroke="var(--grid)" />
        <XAxis dataKey="band" tick={AXIS} axisLine={{ stroke: "var(--axis)" }} tickLine={false} />
        <YAxis domain={[0, 1]} tickFormatter={pct0} tick={AXIS} axisLine={false} tickLine={false} />
        <ReferenceLine y={0.5} stroke="var(--axis)" strokeDasharray="4 4" />
        <Tooltip contentStyle={TIP} cursor={{ fill: "var(--card2)" }} formatter={(v: number, n: string) => [pct0(v), n === "hit_rate" ? "Went up" : "Beat the market"]} />
        <Legend formatter={(v: string) => <span style={{ color: "var(--text-2)", fontSize: 12 }}>{v === "hit_rate" ? "Went up" : "Beat the market"}</span>} />
        <Bar dataKey="hit_rate" fill="var(--series-1)" radius={[4, 4, 0, 0]} isAnimationActive={false} label={{ position: "top", fontSize: 10.5, fill: "var(--text-muted)", formatter: pct0 }} />
        <Bar dataKey="beat_market_rate" fill="var(--series-3)" radius={[4, 4, 0, 0]} isAnimationActive={false} label={{ position: "top", fontSize: 10.5, fill: "var(--text-muted)", formatter: pct0 }} />
      </BarChart>
    </Box>
  );
}

/* ── Live scorecard: matured batches ────────────────────────────────── */
export function LiveScoreChart({ scores }: { scores: { run_date: string; top_decile_hit: number; top_decile_excess_pct: number }[] }) {
  return (
    <Box h={200}>
      <ComposedChart data={scores} margin={{ top: 10, right: 12, bottom: 0, left: -16 }}>
        <CartesianGrid vertical={false} stroke="var(--grid)" />
        <XAxis dataKey="run_date" tickFormatter={(d: string) => fmtDate(d).slice(0, 6)} tick={AXIS} axisLine={{ stroke: "var(--axis)" }} tickLine={false} />
        <YAxis domain={[0, 1]} tickFormatter={pct0} tick={AXIS} axisLine={false} tickLine={false} />
        <ReferenceLine y={0.5} stroke="var(--axis)" strokeDasharray="4 4" />
        <Tooltip contentStyle={TIP} cursor={{ fill: "var(--card2)" }} labelFormatter={(d) => `Predicted on ${fmtDate(String(d))}`}
                 formatter={(v: number, n: string) => [n === "top_decile_hit" ? pct0(v) : fmtPct(v), n === "top_decile_hit" ? "Top-odds beat market" : "Their extra return"]} />
        <Bar dataKey="top_decile_hit" fill="var(--series-1)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
      </ComposedChart>
    </Box>
  );
}

/* ── Price with 20-day average (two series → legend) ────────────────── */
export function PriceChart({ history, color = "var(--series-1)" }: { history: { date: string; close: number }[]; color?: string }) {
  const data = history.map((h, i) => {
    const w = history.slice(Math.max(0, i - 19), i + 1);
    return { ...h, avg20: i >= 19 ? w.reduce((s, x) => s + x.close, 0) / w.length : null };
  });
  return (
    <Box h={180}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
        <CartesianGrid vertical={false} stroke="var(--grid)" />
        <XAxis dataKey="date" tickFormatter={(d: string) => fmtDate(d).slice(0, 6)} tick={AXIS} axisLine={{ stroke: "var(--axis)" }} tickLine={false} minTickGap={36} />
        <YAxis domain={["auto", "auto"]} tick={AXIS} axisLine={false} tickLine={false} tickFormatter={(v: number) => `₹${v >= 1000 ? (v / 1000).toFixed(1) + "k" : v.toFixed(0)}`} />
        <Tooltip contentStyle={TIP} cursor={{ stroke: "var(--axis)", strokeDasharray: "3 3" }} labelFormatter={(d) => fmtDate(String(d))}
                 formatter={(v: number, n: string) => [`₹${v.toFixed(2)}`, n === "close" ? "Close" : "20-day average"]} />
        <Legend formatter={(v: string) => <span style={{ color: "var(--text-2)", fontSize: 12 }}>{v === "close" ? "Closing price" : "20-day average"}</span>} />
        <Line dataKey="close" stroke={color} strokeWidth={2} dot={false} activeDot={{ r: 5, stroke: "var(--card)", strokeWidth: 2 }} isAnimationActive={false} />
        <Line dataKey="avg20" stroke="var(--text-muted)" strokeWidth={1.5} strokeDasharray="5 4" dot={false} connectNulls isAnimationActive={false} />
      </LineChart>
    </Box>
  );
}

/* ── Allocation donut for one Arena manager ─────────────────────────── */
export function AllocationDonut({ holdings, color, cash }: { holdings: { ticker: string; allocation_percent: number }[]; color: string; cash?: number }) {
  const sorted = [...holdings].sort((a, b) => b.allocation_percent - a.allocation_percent);
  const data = sorted.map((h, i) => ({ name: h.ticker.replace(".NS", ""), value: h.allocation_percent, opacity: 1 - i * (0.65 / Math.max(1, sorted.length)) }));
  if (cash && cash > 0.5) data.push({ name: "Cash", value: cash, opacity: 0.25 });
  return (
    <div style={{ display: "grid", gridTemplateColumns: "150px 1fr", gap: 12, alignItems: "center" }}>
      <div style={{ width: 150, height: 150 }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie data={data} dataKey="value" innerRadius={46} outerRadius={70} paddingAngle={2} stroke="var(--card)" strokeWidth={2} isAnimationActive={false}>
              {data.map((d) => <Cell key={d.name} fill={d.name === "Cash" ? "var(--text-dim)" : color} fillOpacity={d.opacity} />)}
            </Pie>
            <Tooltip contentStyle={TIP} formatter={(v: number, n: string) => [`${v.toFixed(0)}%`, n]} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div style={{ display: "grid", gap: 5 }}>
        {data.map((d) => (
          <div key={d.name} style={{ display: "grid", gridTemplateColumns: "10px 1fr auto", alignItems: "center", gap: 8, fontSize: 12.5 }}>
            <span className="chip-dot" style={{ background: d.name === "Cash" ? "var(--text-dim)" : color, opacity: d.opacity, width: 10, height: 10 }} />
            <span style={{ color: "var(--text-2)" }}>{d.name}</span>
            <b className="tnum">{d.value.toFixed(0)}%</b>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Leaderboard bars (identity = manager colour, labelled) ─────────── */
export function LeaderBars({ rows }: { rows: { name: string; value: number; color: string }[] }) {
  return (
    <Box h={Math.max(120, rows.length * 34 + 20)}>
      <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 56, bottom: 0, left: 8 }} barCategoryGap={8}>
        <CartesianGrid horizontal={false} stroke="var(--grid)" />
        <XAxis type="number" tickFormatter={(v: number) => `${v}%`} tick={AXIS} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="name" width={120} tick={{ ...AXIS, fill: "var(--text-2)" }} axisLine={false} tickLine={false} />
        <ReferenceLine x={0} stroke="var(--axis)" />
        <Tooltip contentStyle={TIP} cursor={{ fill: "var(--card2)" }} formatter={(v: number) => [fmtPct(v, 2), "Average return"]} />
        <Bar dataKey="value" radius={[0, 4, 4, 0]} isAnimationActive={false} label={{ position: "right", fontSize: 11, fill: "var(--text-2)", formatter: (v: number) => fmtPct(v, 2) }}>
          {rows.map((r) => <Cell key={r.name} fill={r.color} />)}
        </Bar>
      </BarChart>
    </Box>
  );
}
