/** Typed client for the FastAPI backend. All fetches go through here. */

export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Band = "Strong" | "Good" | "Neutral" | "Weak" | "Wait" | "Watch";

export type FactorKey =
  | "mom_12_1" | "mom_6_1" | "trend" | "low_vol" | "liquidity" | "vol_conf" | "overheat";

export interface RankItem {
  ticker: string;
  symbol: string;
  date: string;
  buy_rank: number;
  band: Band;
  regime: string | null;
  sector: string | null;
  close: number;
  topsis: number;
  eligible: boolean;
  contributions: Record<FactorKey, number | null>;
}

export interface RankList { date: string | null; count: number; items: RankItem[] }

export interface RankDetail extends RankItem {
  z: Record<FactorKey, number | null>;
  raw: Record<string, number | null>;
  history: { date: string; buy_rank: number; close: number }[];
}

export interface Explanation {
  ticker: string; date: string; buy_rank: number; band: Band;
  bullets: string[]; watch_out: string;
  model: string; attempts: number; audit_dropped: number; cached: boolean;
}

export interface SectorRow { sector: string; count: number; avg_rank: number }

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  rank: (q: { limit?: number; offset?: number; sector?: string; band?: string; min_rank?: number } = {}) => {
    const p = new URLSearchParams();
    Object.entries(q).forEach(([k, v]) => v !== undefined && v !== "" && p.set(k, String(v)));
    return get<RankList>(`/rank?${p.toString()}`);
  },
  rankSectors: () => get<{ date: string | null; sectors: SectorRow[] }>("/rank/sectors"),
  rankDetail: (ticker: string, history = 60) => get<RankDetail>(`/rank/${encodeURIComponent(ticker)}?history=${history}`),
  rankExplain: (ticker: string) => get<Explanation>(`/rank/${encodeURIComponent(ticker)}/explain`),
  health: () => get<{ status: string; version: string }>("/health"),
};
