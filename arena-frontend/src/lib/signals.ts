/** Everything that maps a signal to a colour + a word. Colour never travels alone. */

import type { Band, FactorKey } from "./api";

export interface BandStyle { fill: string; soft: string; ink: string; word: string; blurb: string }

export const BAND: Record<Band, BandStyle> = {
  Strong:  { fill: "var(--strong)",  soft: "var(--strong-soft)",  ink: "var(--strong-ink)",  word: "Strong",  blurb: "Top of the pack on trend, momentum and calm." },
  Good:    { fill: "var(--good)",    soft: "var(--good-soft)",    ink: "var(--good-ink)",    word: "Good",    blurb: "Better than most, with a soft spot or two." },
  Neutral: { fill: "var(--neutral)", soft: "var(--neutral-soft)", ink: "var(--neutral-ink)", word: "Neutral", blurb: "Middle of the pack. Nothing stands out yet." },
  Weak:    { fill: "var(--weak)",    soft: "var(--weak-soft)",    ink: "var(--weak-ink)",    word: "Weak",    blurb: "Behind most stocks on the factors we track." },
  Wait:    { fill: "var(--wait)",    soft: "var(--wait-soft)",    ink: "var(--wait-ink)",    word: "Wait",    blurb: "Market weather is stormy. Ranks are on hold." },
  Watch:   { fill: "var(--wait)",    soft: "var(--wait-soft)",    ink: "var(--wait-ink)",    word: "Watch",   blurb: "Top ranked, but the weather says be patient." },
};

export function bandOf(rank: number, regime: string | null = null): Band {
  if (regime === "Stormy") return rank >= 90 ? "Watch" : "Wait";
  const [s, g, n] = regime === "Cloudy" ? [85, 70, 50] : [80, 60, 40];
  return rank >= s ? "Strong" : rank >= g ? "Good" : rank >= n ? "Neutral" : "Weak";
}

export const FACTOR_LABEL: Record<FactorKey, { name: string; plain: string }> = {
  mom_12_1:  { name: "12-month momentum", plain: "How far the price has climbed over the past year, ignoring the last month." },
  mom_6_1:   { name: "6-month momentum",  plain: "The same idea over six months." },
  trend:     { name: "Trend quality",     plain: "How steadily it has stayed above its 50-day average price." },
  low_vol:   { name: "Calmness",          plain: "Smaller day-to-day swings score higher." },
  liquidity: { name: "Liquidity",         plain: "How much money changes hands each day. Easier to buy and sell." },
  vol_conf:  { name: "Volume confirmation", plain: "Are more people trading it than usual?" },
  overheat:  { name: "Overheat penalty",  plain: "A sharp recent spike or a very high RSI costs points." },
};

export const FACTOR_ORDER: FactorKey[] = ["mom_12_1", "mom_6_1", "trend", "low_vol", "liquidity", "vol_conf", "overheat"];

/* AI Arena personas / models — fixed colour order, never cycled */
export const MODEL: Record<string, { label: string; short: string; color: string; icon: string; style: string }> = {
  gpt:      { label: "GPT-4o mini",      short: "GPT",      color: "var(--series-1)", icon: "⬡", style: "Quant & risk-adjusted" },
  gemini:   { label: "Gemini 2.5 Flash", short: "Gemini",   color: "var(--series-2)", icon: "◈", style: "Aggressive growth" },
  mistral:  { label: "Mistral Voxtral",  short: "Mistral",  color: "var(--series-3)", icon: "▲", style: "Conservative value" },
  deepseek: { label: "DeepSeek V3.2",    short: "DeepSeek", color: "var(--series-7)", icon: "◎", style: "Pure TOPSIS" },
};
export const modelMeta = (m: string) => MODEL[m] ?? { label: m, short: m, color: "var(--series-8)", icon: "●", style: "" };

export const RISK_TONE: Record<string, "good" | "neutral" | "weak"> = { conservative: "good", moderate: "neutral", aggressive: "weak" };

export const fmtINR = (n: number | null | undefined, d = 2) =>
  n == null ? "—" : `₹${n.toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d })}`;

export const fmtPct = (x: number | null | undefined, d = 1) =>
  x == null ? "—" : `${x >= 0 ? "+" : ""}${x.toFixed(d)}%`;

export const logToPct = (x: number | null | undefined) => (x == null ? null : (Math.exp(x) - 1) * 100);

export const fmtDate = (iso: string | null | undefined) =>
  iso ? new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "—";
