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

export interface RankRow extends RankItem {
  position?: number; score?: number | null; rank_change_20d?: number | null; price_change_20d_pct?: number | null; prob_up?: number | null;
}
export interface RankList { date: string | null; count: number; universe?: number; compare_date?: string | null; items: RankRow[] }
export interface Mover {
  ticker: string; symbol: string; sector: string | null; from_rank: number; to_rank: number; change: number;
  band: Band; close: number; price_change_pct: number | null;
}
export interface Movers { date: string | null; compare_date: string | null; days?: number; risers: Mover[]; fallers: Mover[] }

export interface LiveScore {
  run_date: string; matured_on: string; horizon: number; n: number; auc: number | null; accuracy: number;
  top_decile_hit: number; top_decile_excess_pct: number; median_return_pct: number;
}
export interface PredictLive {
  scores: LiveScore[];
  next_maturity: { run_date: string; horizon: number; expected_on: string; pending_batches: number } | null;
  training_history: string[];
  model_card: { algorithm: string; target: string; features: string[]; validation: string; training_stride_days: number;
                retrain_policy: string; last_trained: string | null; history_years: number | null; n_train_rows: number | null };
}

export interface RankDetail extends RankItem {
  position?: number; universe?: number; score?: number | null;
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

/* ── Predictions ─────────────────────────────────────────────────────── */
export interface PredictionItem {
  ticker: string; symbol: string; date: string; horizon: number;
  prob_up: number; pct_rank: number; sector: string | null; close: number | null;
  buy_rank: number | null; features: Record<string, number | null>;
  so_far_pct?: number | null; market_so_far_pct?: number | null; beating_so_far?: boolean | null;
}
export interface PredictionTrack {
  symbol: string; prediction_date: string; horizon_days: number; odds_pct: number; pct_rank: number;
  days_elapsed: number; days_total: number; expected_end: string;
  stock_pct: number | null; market_pct: number | null; beating: boolean | null; verdict: string;
  series: { date: string; stock: number; market: number | null }[];
}
export interface PredictRun {
  as_of: string; horizon_days: number; history_start: string; history_years: number;
  n_rows: number; n_train_rows: number; n_tickers: number;
  folds: { year: number; n_train: number; n_test: number; auc: number; accuracy: number; top_decile_hit: number; top_decile_excess_pct: number }[];
  oos: { auc: number | null; accuracy: number | null; top_decile_hit: number | null; top_decile_excess_pct: number | null; n_oos: number };
  calibration: { bin_lo: number; bin_hi: number; predicted: number; actual: number; n: number }[];
  importance: { feature: string; label: string; importance: number }[];
  profiles: { feature: string; label: string; high_prob: number; low_prob: number; edge: number }[];
  sectors: { sector: string; n: number; avg_prob: number; top_stock: string | null; rel_strength_6m_pct: number | null; rs_rank?: number; top3_continuation_rate: number }[];
  band_base_rates: { band: string; horizon: number; n: number; hit_rate: number; median_return_pct: number; beat_market_rate: number }[];
  market_now: { mkt_mom_pct: number; breadth: number };
}
export interface PredictList { run: PredictRun | null; count: number; as_of_prices?: string | null; market_so_far_pct?: number | null; items: PredictionItem[] }

/* ── Arena (v1 endpoints) ────────────────────────────────────────────── */
export interface Holding {
  ticker: string; quantity: number; entry_price: number; invested_amount: number;
  allocation_percent: number; confidence: number; reasoning: string; sector: string;
}
export interface ModelResult {
  model: string; starting_capital: number; remaining_cash: number; strategy_summary: string | null;
  risk_level: string | null; current_return: number | null; portfolio_value: number | null; portfolio: Holding[];
}
export interface Candidate {
  ticker: string; current_price: number; rsi: number; volatility: number; volume_ratio: number;
  one_month_return: number; sector: string; trend_score: number; topsis_score: number;
}
export interface SimData { date: string | null; market_candidates: Candidate[]; model_results: ModelResult[] }
export interface LeaderboardEntry {
  model: string; average_return_percent: number; best_return_percent: number; worst_return_percent: number;
  days_active: number; win_rate: number; latest_return: number; total_portfolios: number;
}
export type HistoryMap = Record<string, { date: string; return_pct: number; portfolio_value: number }[]>;
export interface PortfolioListItem {
  id: number; model: string; date: string; starting_capital: number; total_invested: number; remaining_cash: number;
  strategy_summary: string | null; risk_level: string | null; holdings_count: number;
}
export interface PortfolioDetail extends Omit<PortfolioListItem, "holdings_count"> {
  holdings: Holding[];
  latest_valuation: { portfolio_value: number; return_pct: number; unrealized_pnl: number } | null;
  valuation_history: { date: string; portfolio_value: number; return_pct: number }[];
}

/* ── System status ───────────────────────────────────────────────────── */
export interface SystemAlert {
  id: number; kind: string; severity: "info" | "warning" | "critical"; message: string; detail: string | null;
  count: number; first_seen: string; last_seen: string; help: string | null;
}
export interface SystemStatus {
  overall: "ok" | "warning" | "critical";
  checked_at: string;
  today: { date: string; trading_day: boolean; holiday: string | null; next_trading_day: string };
  alerts: SystemAlert[];
  jobs: Record<string, { status: string; started_at: string; finished_at: string; rows: number; detail: string }>;
  schedule: { id: string; name: string; next_run: string | null; trigger: string }[];
  data: { latest_bars: string; latest_scores: string; model_trained: string | null; model_oos: Record<string, number | null> | null };
  llm: {
    today: { calls: number; input_tokens: number; output_tokens: number; est_cost_usd: number; errors: number };
    last_30_days: { calls: number; input_tokens: number; output_tokens: number; est_cost_usd: number; errors: number };
    all_time: { calls: number; est_cost_usd: number };
    burn_per_day_usd: number;
    budget: { budget_inr: number; spent_inr: number; spent_usd: number; remaining_inr: number | null; pct_used: number | null; exhausted: boolean; usd_inr: number };
    by_feature_30d: { feature: string; calls: number; est_cost_usd: number }[];
    by_model_30d: { model: string; calls: number; est_cost_usd: number }[];
    daily_30d: { date: string; est_cost_usd: number; calls: number }[];
    projection: { currency: "INR" | "USD"; balance_usd: number; balance_inr: number; as_of: string; spent_since_usd: number; spent_since_inr: number; remaining_usd: number; remaining_inr: number; remaining_pct: number; burn_per_day_usd: number; burn_per_day_inr: number; days_left: number | null; runs_out_on: string | null } | { error: string } | null;
    note: string;
  };
  calendar: { years_covered: number[]; total: number; by_source: Record<string, number>; next: { date: string; name: string }[] };
  channels: { telegram: boolean; webhook: boolean };
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return res.json() as Promise<T>;
}
async function post<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { method: "POST" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  predict: (q: { limit?: number; offset?: number; sector?: string } = {}) => {
    const p = new URLSearchParams();
    Object.entries(q).forEach(([k, v]) => v !== undefined && v !== "" && p.set(k, String(v)));
    return get<PredictList>(`/predict?${p.toString()}`);
  },
  predictLive: () => get<PredictLive>("/predict/live"),
  predictTrack: (ticker: string) => get<PredictionTrack>(`/predict/${encodeURIComponent(ticker)}/track`),
  predictOne: (ticker: string) => get<PredictionItem & { oos: PredictRun["oos"]; history_years: number }>(`/predict/${encodeURIComponent(ticker)}`),

  status: () => get<SystemStatus>("/status"),
  resolveAlert: (id: number) => post<{ ok: boolean }>(`/alerts/${id}/resolve`),
  runChecks: () => post<Record<string, unknown>>("/checks/run"),
  testAlert: () => post<{ ok: boolean; notified: boolean; channels: { telegram: boolean; webhook: boolean } }>("/alerts/test"),

  simToday: () => get<SimData>("/simulation/today"),
  leaderboard: () => get<LeaderboardEntry[]>("/leaderboard"),
  history: () => get<HistoryMap>("/analytics/history"),
  portfolios: (model?: string) => get<PortfolioListItem[]>(`/portfolios${model ? `?model=${model}` : ""}`),
  portfolio: (id: number) => get<PortfolioDetail>(`/portfolios/${id}`),
  runSimulation: () => post<{ message: string }>("/simulate-and-save"),
  updateValuations: () => post<{ message: string; portfolios_updated: number }>("/update-valuations"),
  trainPredictor: () => post<{ message: string; as_of: string }>("/train-predictor"),

  rank: (q: { limit?: number; offset?: number; sector?: string; band?: string; min_rank?: number } = {}) => {
    const p = new URLSearchParams();
    Object.entries(q).forEach(([k, v]) => v !== undefined && v !== "" && p.set(k, String(v)));
    return get<RankList>(`/rank?${p.toString()}`);
  },
  rankSectors: () => get<{ date: string | null; sectors: SectorRow[] }>("/rank/sectors"),
  rankMovers: (days = 20, limit = 6) => get<Movers>(`/rank/movers?days=${days}&limit=${limit}`),
  rankDetail: (ticker: string, history = 60) => get<RankDetail>(`/rank/${encodeURIComponent(ticker)}?history=${history}`),
  rankExplain: (ticker: string) => get<Explanation>(`/rank/${encodeURIComponent(ticker)}/explain`),
  health: () => get<{ status: string; version: string }>("/health"),
};
