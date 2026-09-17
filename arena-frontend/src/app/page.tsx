"use client";

import { useState, useEffect, useCallback } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, RadarChart, Radar, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, Cell, Legend, AreaChart, Area, ScatterChart, Scatter,
} from "recharts";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Holding {
  ticker: string;
  quantity: number;
  entry_price: number;
  invested_amount: number;
  allocation_percent: number;
  confidence: number;
  reasoning: string;
  sector: string;
}

interface ModelResult {
  model: string;
  starting_capital: number;
  remaining_cash: number;
  strategy_summary: string;
  risk_level: string;
  current_return: number | null;
  portfolio_value: number | null;
  portfolio: Holding[];
}

interface Candidate {
  ticker: string;
  current_price: number;
  rsi: number;
  volatility: number;
  volume_ratio: number;
  one_month_return: number;
  sector: string;
  trend_score: number;
  topsis_score: number;
}

interface SimData {
  date: string | null;
  market_candidates: Candidate[];
  model_results: ModelResult[];
}

interface LeaderboardEntry {
  model: string;
  average_return_percent: number;
  best_return_percent: number;
  worst_return_percent: number;
  days_active: number;
  win_rate: number;
  latest_return: number;
  total_portfolios: number;
}

interface HistoryMap {
  [model: string]: { date: string; return_pct: number; portfolio_value: number }[];
}

type Page = "dashboard" | "leaderboard" | "market" | "portfolios" | "history";

// ─── Constants ────────────────────────────────────────────────────────────────

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const MODEL_COLORS: Record<string, string> = {
  gpt:      "#00e5a0",
  gemini:   "#0077ff",
  mistral:  "#ff6b35",
  deepseek: "#ffd166",
};

const MODEL_LABELS: Record<string, string> = {
  gpt:      "GPT-4o mini",
  gemini:   "Gemini 2.5 Flash",
  mistral:  "Mistral Voxtral",
  deepseek: "DeepSeek V4",
};

const MODEL_ICONS: Record<string, string> = {
  gpt:      "⬡",
  gemini:   "◈",
  mistral:  "▲",
  deepseek: "◎",
};

const RISK_COLOR: Record<string, string> = {
  conservative: "#0077ff",
  moderate:     "#ffd166",
  aggressive:   "#ff6b35",
};

// ─── NSE Market Status Helper ──────────────────────────────────────────────────

interface NSEStatus {
  isOpen: boolean;
  timeUntilOpen: string;
  timeUntilClose: string;
  status: "open" | "closed" | "pre-market" | "post-market";
  currentTime: string;
}

function getNSEStatus(): NSEStatus {
  const now = new Date();
  
  // Convert to IST (UTC+5:30)
  const istTime = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }));
  const day = istTime.getDay();
  const hours = istTime.getHours();
  const minutes = istTime.getMinutes();
  const totalMinutes = hours * 60 + minutes;
  
  // NSE trading hours: 9:15 AM (555 min) to 3:30 PM (930 min), Mon-Fri
  const MARKET_OPEN = 9 * 60 + 15;      // 555 minutes
  const MARKET_CLOSE = 15 * 60 + 30;    // 930 minutes
  const PRE_MARKET = 9 * 60;            // 540 minutes (9:00 AM)

  const timeString = istTime.toLocaleTimeString('en-IN', { 
    hour: '2-digit', 
    minute: '2-digit', 
    second: '2-digit',
    hour12: true 
  });

  let status: NSEStatus["status"] = "closed";
  let isOpen = false;
  let timeUntilOpen = "";
  let timeUntilClose = "";

  // Check if it's a weekend
  if (day === 0 || day === 6) {
    // Weekend
    const daysUntilMonday = day === 0 ? 1 : 2;
    timeUntilOpen = `${daysUntilMonday} day${daysUntilMonday > 1 ? 's' : ''} until open`;
    status = "closed";
  } else {
    // Weekday
    if (totalMinutes < PRE_MARKET) {
      // Before 9:00 AM
      const minsUntil = PRE_MARKET - totalMinutes;
      const hrs = Math.floor(minsUntil / 60);
      const mins = minsUntil % 60;
      timeUntilOpen = `${hrs}h ${mins}m until pre-market`;
      status = "closed";
    } else if (totalMinutes < MARKET_OPEN) {
      // 9:00 AM to 9:15 AM (pre-market)
      const minsUntil = MARKET_OPEN - totalMinutes;
      timeUntilOpen = `${minsUntil}m until open`;
      status = "pre-market";
    } else if (totalMinutes < MARKET_CLOSE) {
      // Market is open
      const minsUntilClose = MARKET_CLOSE - totalMinutes;
      const hrs = Math.floor(minsUntilClose / 60);
      const mins = minsUntilClose % 60;
      timeUntilClose = `${hrs}h ${mins}m until close`;
      isOpen = true;
      status = "open";
    } else {
      // After 3:30 PM
      const nextOpenTime = 24 * 60 + 9 * 60 + 15 - totalMinutes; // minutes until next day 9:15 AM
      const hrs = Math.floor(nextOpenTime / 60);
      const mins = nextOpenTime % 60;
      timeUntilOpen = `Tomorrow ${hrs % 24}h ${mins}m`;
      status = "post-market";
    }
  }

  return {
    isOpen,
    status,
    timeUntilOpen,
    timeUntilClose,
    currentTime: timeString,
  };
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmt(n: number | null | undefined, decimals = 2): string {
  if (n == null) return "—";
  return n.toFixed(decimals);
}

function fmtINR(n: number | null | undefined): string {
  if (n == null) return "—";
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function pct(n: number | null | undefined): string {
  if (n == null) return "—";
  const sign = n >= 0 ? "+" : "";
  return sign + n.toFixed(3) + "%";
}

function returnColor(n: number | null | undefined): string {
  if (n == null) return "var(--text-muted)";
  return n >= 0 ? "var(--green)" : "var(--red)";
}

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// ─── UI Atoms ─────────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <div style={{
      width: 28, height: 28, borderRadius: "50%",
      border: "2px solid var(--border-hi)",
      borderTopColor: "var(--accent)",
      animation: "spin 0.8s linear infinite",
    }} />
  );
}

function Tag({ children, color }: { children: React.ReactNode; color?: string }) {
  return (
    <span style={{
      fontSize: 10, fontFamily: "var(--font-mono)",
      letterSpacing: "0.08em", textTransform: "uppercase",
      padding: "2px 7px", borderRadius: 3,
      border: `1px solid ${color ?? "var(--border-hi)"}`,
      color: color ?? "var(--text-muted)",
    }}>
      {children}
    </span>
  );
}

function StatBox({
  label, value, color, sub,
}: {
  label: string; value: string; color?: string; sub?: string;
}) {
  return (
    <div style={{
      background: "var(--card)", border: "1px solid var(--border)",
      borderRadius: 8, padding: "14px 18px", minWidth: 130,
    }}>
      <div style={{ fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 20, fontFamily: "var(--font-display)", fontWeight: 700, color: color ?? "var(--text)" }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 style={{
      fontFamily: "var(--font-display)", fontSize: 13, fontWeight: 600,
      letterSpacing: "0.12em", textTransform: "uppercase",
      color: "var(--text-muted)", marginBottom: 14,
      display: "flex", alignItems: "center", gap: 8,
    }}>
      <span style={{ width: 18, height: 1, background: "var(--accent)", display: "inline-block" }} />
      {children}
    </h2>
  );
}

// ─── NSE Market Status Component ───────────────────────────────────────────────

function NSEMarketClock() {
  const [status, setStatus] = useState<NSEStatus>(() => getNSEStatus());

  useEffect(() => {
    const timer = setInterval(() => {
      setStatus(getNSEStatus());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const statusColors: Record<NSEStatus["status"], string> = {
    open: "var(--green)",
    closed: "var(--red)",
    "pre-market": "var(--gold)",
    "post-market": "var(--text-muted)",
  };

  const statusLabels: Record<NSEStatus["status"], string> = {
    open: "MARKET OPEN",
    closed: "MARKET CLOSED",
    "pre-market": "PRE-MARKET",
    "post-market": "AFTER HOURS",
  };

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12,
      background: "rgba(0,0,0,0.2)", borderRadius: 8,
      padding: "8px 14px",
    }}>
      {/* Clock */}
      <div style={{
        fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 600,
        color: "var(--text)", letterSpacing: "0.02em",
      }}>
        {status.currentTime}
      </div>

      {/* Status indicator */}
      <div style={{
        display: "flex", alignItems: "center", gap: 6,
        fontSize: 11, fontWeight: 600, letterSpacing: "0.08em",
        color: statusColors[status.status],
      }}>
        <span style={{
          width: 8, height: 8, borderRadius: "50%",
          background: statusColors[status.status],
          animation: status.isOpen ? "pulse-dot 2s ease infinite" : "none",
        }} />
        {statusLabels[status.status]}
      </div>

      {/* Time until open/close */}
      {status.timeUntilClose && (
        <div style={{
          fontSize: 11, color: "var(--text-muted)",
          fontFamily: "var(--font-mono)",
        }}>
          Closes in {status.timeUntilClose}
        </div>
      )}
      {status.timeUntilOpen && (status.status === "closed" || status.status === "post-market") && (
        <div style={{
          fontSize: 11, color: "var(--text-muted)",
          fontFamily: "var(--font-mono)",
        }}>
          {status.timeUntilOpen}
        </div>
      )}
    </div>
  );
}

// ─── Navbar ───────────────────────────────────────────────────────────────────

function Navbar({
  page, setPage, isDark, onToggle, simDate,
}: {
  page: Page;
  setPage: (p: Page) => void;
  isDark: boolean;
  onToggle: () => void;
  simDate: string | null;
}) {
  const navItems: { id: Page; label: string }[] = [
    { id: "dashboard",   label: "Dashboard" },
    { id: "leaderboard", label: "Leaderboard" },
    { id: "market",      label: "Market Intel" },
    { id: "portfolios",  label: "Portfolios" },
    { id: "history",     label: "History" },
  ];

  return (
    <nav style={{
      position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
      height: 56,
      background: isDark ? "rgba(7,9,13,0.92)" : "rgba(240,242,245,0.92)",
      backdropFilter: "blur(16px)",
      borderBottom: "1px solid var(--border)",
      display: "flex", alignItems: "center",
      padding: "0 24px", gap: 0,
    }}>
      {/* Logo */}
      <div style={{
        fontFamily: "var(--font-display)", fontWeight: 800,
        fontSize: 15, letterSpacing: "0.04em",
        color: "var(--accent)", marginRight: 32, whiteSpace: "nowrap",
      }}>
        AI ARENA
      </div>

      {/* Nav links */}
      <div style={{ display: "flex", gap: 2, flex: 1 }}>
        {navItems.map((item) => (
          <button key={item.id} onClick={() => setPage(item.id)} style={{
            fontFamily: "var(--font-display)", fontSize: 12, fontWeight: 600,
            letterSpacing: "0.08em", textTransform: "uppercase",
            padding: "6px 14px", borderRadius: 5, border: "none", cursor: "pointer",
            transition: "all 0.15s",
            background: page === item.id ? "var(--accent)" : "transparent",
            color: page === item.id ? "#000" : "var(--text-muted)",
          }}>
            {item.label}
          </button>
        ))}
      </div>

      {/* Right side */}
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        {/* NSE Market Clock */}
        <NSEMarketClock />

        {simDate && (
          <span style={{ fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
            {simDate}
          </span>
        )}

        {/* Dark/Light toggle */}
        <button onClick={onToggle} style={{
          width: 36, height: 36, borderRadius: 8,
          border: "1px solid var(--border-hi)",
          background: "var(--card)",
          color: "var(--text)", cursor: "pointer",
          fontSize: 16, display: "flex", alignItems: "center", justifyContent: "center",
          transition: "all 0.15s",
        }}>
          {isDark ? "☀" : "☽"}
        </button>
      </div>
    </nav>
  );
}

// ─── Model Card ───────────────────────────────────────────────────────────────

function ModelCard({
  result, isSelected, onClick,
}: {
  result: ModelResult;
  isSelected: boolean;
  onClick: () => void;
}) {
  const color = MODEL_COLORS[result.model] ?? "#888";
  const ret   = result.current_return;
  const val   = result.portfolio_value;

  return (
    <div onClick={onClick} style={{
      background: "var(--card)", border: `1px solid ${isSelected ? color : "var(--border)"}`,
      borderRadius: 10, padding: "18px 20px", cursor: "pointer",
      transition: "all 0.2s",
      boxShadow: isSelected ? `0 0 20px ${color}22` : "none",
      position: "relative", overflow: "hidden",
    }}>
      {/* Accent bar */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: 2,
        background: color, opacity: isSelected ? 1 : 0.3,
      }} />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
        <div>
          <div style={{
            fontFamily: "var(--font-display)", fontSize: 14, fontWeight: 700,
            color, marginBottom: 3, letterSpacing: "0.02em",
          }}>
            {MODEL_ICONS[result.model]} {MODEL_LABELS[result.model] ?? result.model}
          </div>
          <Tag color={RISK_COLOR[result.risk_level] ?? "var(--text-muted)"}>
            {result.risk_level}
          </Tag>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{
            fontFamily: "var(--font-display)", fontSize: 22, fontWeight: 800,
            color: returnColor(ret), lineHeight: 1,
          }}>
            {pct(ret)}
          </div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
            {fmtINR(val)}
          </div>
        </div>
      </div>

      <div style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.6, marginBottom: 12 }}>
        {result.strategy_summary}
      </div>

      {/* Mini allocation bar */}
      <div style={{ display: "flex", gap: 2, height: 4, borderRadius: 2, overflow: "hidden" }}>
        {result.portfolio.map((h) => (
          <div key={h.ticker} style={{
            flex: h.allocation_percent, background: color, opacity: 0.6 + (h.confidence / 100) * 0.4,
          }} title={`${h.ticker}: ${h.allocation_percent}%`} />
        ))}
      </div>

      <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
        {result.portfolio.map((h) => (
          <span key={h.ticker} style={{
            fontSize: 10, fontFamily: "var(--font-mono)",
            color: "var(--text-muted)", background: "var(--card2)",
            padding: "2px 6px", borderRadius: 3,
          }}>
            {h.ticker.replace(".NS", "")}
          </span>
        ))}
      </div>
    </div>
  );
}

// ─── Holdings Table ───────────────────────────────────────────────────────────

function HoldingsTable({ holdings, modelColor }: { holdings: Holding[]; modelColor: string }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border)" }}>
            {["Ticker", "Sector", "Alloc %", "Qty", "Entry ₹", "Invested", "Conf"].map((h) => (
              <th key={h} style={{
                textAlign: "left", padding: "6px 10px",
                fontFamily: "var(--font-mono)", fontSize: 10,
                letterSpacing: "0.08em", textTransform: "uppercase",
                color: "var(--text-dim)", fontWeight: 500,
              }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {holdings.map((h, i) => (
            <tr key={i} style={{
              borderBottom: "1px solid var(--border)",
              transition: "background 0.1s",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--card2)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <td style={{ padding: "8px 10px" }}>
                <span style={{ color: modelColor, fontWeight: 600, fontFamily: "var(--font-display)" }}>
                  {h.ticker.replace(".NS", "")}
                </span>
              </td>
              <td style={{ padding: "8px 10px", color: "var(--text-muted)" }}>
                <Tag>{h.sector}</Tag>
              </td>
              <td style={{ padding: "8px 10px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <div style={{
                    width: 40, height: 4, borderRadius: 2, background: "var(--border)",
                    position: "relative", overflow: "hidden",
                  }}>
                    <div style={{
                      position: "absolute", left: 0, top: 0, bottom: 0,
                      width: `${Math.min(h.allocation_percent, 100)}%`,
                      background: modelColor,
                    }} />
                  </div>
                  <span>{fmt(h.allocation_percent, 1)}%</span>
                </div>
              </td>
              <td style={{ padding: "8px 10px", color: "var(--text-muted)" }}>{fmt(h.quantity, 2)}</td>
              <td style={{ padding: "8px 10px" }}>{fmtINR(h.entry_price)}</td>
              <td style={{ padding: "8px 10px" }}>{fmtINR(h.invested_amount)}</td>
              <td style={{ padding: "8px 10px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <div style={{
                    width: 24, height: 24, borderRadius: "50%",
                    background: `conic-gradient(${modelColor} ${h.confidence * 3.6}deg, var(--border) 0deg)`,
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    <div style={{
                      width: 16, height: 16, borderRadius: "50%",
                      background: "var(--card)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 8, fontWeight: 700,
                    }}>
                      {h.confidence}
                    </div>
                  </div>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Reasoning */}
      <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 8 }}>
        {holdings.map((h, i) => (
          <div key={i} style={{
            background: "var(--card2)", borderRadius: 6, padding: "10px 12px",
            fontSize: 11, color: "var(--text-muted)", lineHeight: 1.6,
          }}>
            <span style={{ color: modelColor, fontWeight: 600, marginRight: 8 }}>
              {h.ticker.replace(".NS", "")}
            </span>
            {h.reasoning}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Dashboard Page (ENHANCED) ────────────────────────────────────────────────

function DashboardPage({ sim, loading }: { sim: SimData | null; loading: boolean }) {
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    if (sim?.model_results.length && !selected) {
      setSelected(sim.model_results[0].model);
    }
  }, [sim, selected]);

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", paddingTop: 80 }}>
        <Spinner />
      </div>
    );
  }

  if (!sim || !sim.model_results.length) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        {/* Empty State with Suggestions */}
        <div style={{
          background: "linear-gradient(135deg, var(--card) 0%, var(--card2) 100%)",
          border: "1px solid var(--border)",
          borderRadius: 12, padding: "40px 32px", textAlign: "center",
        }}>
          <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.6 }}>📊</div>
          <div style={{ fontFamily: "var(--font-display)", fontSize: 18, fontWeight: 700, marginBottom: 8 }}>
            No Portfolio Data Yet
          </div>
          <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 20, lineHeight: 1.6 }}>
            Run a simulation to generate AI-powered NIFTY200 portfolios from our 4 models
          </div>
          <div style={{
            background: "var(--card)", borderRadius: 8, padding: "16px 20px",
            textAlign: "left", fontSize: 12, color: "var(--text-muted)", lineHeight: 1.8,
          }}>
            <div style={{ fontWeight: 600, color: "var(--text)", marginBottom: 10 }}>Expected Dashboard Content:</div>
            <ul style={{ paddingLeft: 20, gap: 4, display: "flex", flexDirection: "column" }}>
              <li>✓ <strong>Portfolio Performance</strong> — Current return % and portfolio value for each AI model</li>
              <li>✓ <strong>Risk Metrics</strong> — Volatility, Sharpe ratio, max drawdown analysis</li>
              <li>✓ <strong>Sector Allocation</strong> — Pie/radar chart showing sector diversification</li>
              <li>✓ <strong>Top Holdings</strong> — Key positions with allocation % and confidence scores</li>
              <li>✓ <strong>Model Comparison</strong> — Side-by-side performance of GPT, Gemini, Mistral, DeepSeek</li>
              <li>✓ <strong>Investment Thesis</strong> — AI-generated reasoning for each pick</li>
            </ul>
          </div>
        </div>


      </div>
    );
  }

  const activeResult = sim.model_results.find((r) => r.model === selected) ?? sim.model_results[0];
  const modelColor   = MODEL_COLORS[activeResult.model] ?? "#888";

  // Sector distribution for radar
  const sectorTotals: Record<string, number> = {};
  for (const h of activeResult.portfolio) {
    sectorTotals[h.sector] = (sectorTotals[h.sector] ?? 0) + h.allocation_percent;
  }
  const radarData = Object.entries(sectorTotals).map(([sector, alloc]) => ({
    subject: sector.replace(" ", "\n"), A: alloc,
  }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Model Cards */}
      <div className="fade-up">
        <SectionTitle>Today&apos;s Portfolios</SectionTitle>
        <div style={{
          display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: 12,
        }}>
          {sim.model_results.map((r) => (
            <ModelCard key={r.model} result={r} isSelected={selected === r.model} onClick={() => setSelected(r.model)} />
          ))}
        </div>
      </div>

      {/* Selected Model Details */}
      {activeResult && (
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 24 }}>
          {/* Holdings & Strategy */}
          <div className="fade-up-1">
            <SectionTitle>Portfolio Details — {MODEL_LABELS[activeResult.model] ?? activeResult.model}</SectionTitle>
            <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 10, padding: "20px" }}>
              <HoldingsTable holdings={activeResult.portfolio} modelColor={modelColor} />
            </div>
          </div>

          {/* Right: Stats & Sector Allocation */}
          <div className="fade-up-2" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {/* Key Stats */}
<div>
  <SectionTitle>Key Metrics</SectionTitle>

  <div style={{
      display:"flex",
      flexDirection:"column",
      gap:10
  }}>

    <StatBox
      label="Portfolio Value"
      value={fmtINR(activeResult.portfolio_value)}
      color="var(--text)"
    />

    <StatBox
      label="Return %"
      value={pct(activeResult.current_return)}
      color={returnColor(activeResult.current_return)}
    />

    <StatBox
      label="Unrealized P&L"
      value={fmtINR(
        (activeResult.portfolio_value ?? 0) -
        activeResult.starting_capital
      )}
      color={
        (activeResult.current_return ?? 0) >= 0
          ? "var(--green)"
          : "var(--red)"
      }
    />

    <StatBox
      label="Cash Remaining"
      value={fmtINR(activeResult.remaining_cash)}
      color="var(--text-muted)"
    />

    <StatBox
      label="Holdings"
      value={String(activeResult.portfolio.length)}
      color="var(--gold)"
    />

  </div>
</div>

            {/* Sector Allocation */}
            {radarData.length > 0 && (
              <div>
                <SectionTitle>Sector Mix</SectionTitle>
                <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 10, padding: "16px" }}>
                  <ResponsiveContainer width="100%" height={200}>
                    <RadarChart data={radarData}>
                      <PolarGrid stroke="var(--border)" />
                      <PolarAngleAxis dataKey="subject" tick={{ fontSize: 9, fill: "var(--text-dim)" }} />
                      <PolarRadiusAxis tick={{ fontSize: 9, fill: "var(--text-dim)" }} />
                      <Radar name="Allocation %" dataKey="A" stroke={modelColor} fill={modelColor} fillOpacity={0.4} />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Leaderboard Page ─────────────────────────────────────────────────────────

function LeaderboardPage() {
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<LeaderboardEntry[]>("/leaderboard")
      .then(setLeaderboard)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ display: "flex", justifyContent: "center", paddingTop: 60 }}><Spinner /></div>;

  if (leaderboard.length === 0) {
    return (
      <div style={{ color: "var(--text-muted)", padding: 40, textAlign: "center" }}>
        No leaderboard data yet. Run simulations to build rankings.
      </div>
    );
  }

  const sorted = [...leaderboard].sort((a, b) => b.average_return_percent - a.average_return_percent);

  return (
    <div className="fade-up" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <SectionTitle>AI Model Leaderboard</SectionTitle>

      {sorted.map((entry, rank) => {
        const color = MODEL_COLORS[entry.model] ?? "#888";
        const isTop = rank === 0;

        return (
          <div key={entry.model} style={{
            background: "var(--card)",
            border: `1px solid ${isTop ? color : "var(--border)"}`,
            borderRadius: 10, padding: "16px 20px",
            display: "grid",
            gridTemplateColumns: "40px 200px 1fr 1fr 1fr 1fr 1fr 1fr",
            alignItems: "center", gap: 16,
            boxShadow: isTop ? `0 0 24px ${color}18` : "none",
            transition: "all 0.2s",
          }}>
            {/* Rank */}
            <div style={{
              fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 800,
              color: isTop ? color : "var(--text-dim)",
            }}>
              {rank === 0 ? "🥇" : rank === 1 ? "🥈" : rank === 2 ? "🥉" : `#${rank + 1}`}
            </div>

            {/* Model */}
            <div>
              <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, color, fontSize: 13 }}>
                {MODEL_ICONS[entry.model]} {MODEL_LABELS[entry.model] ?? entry.model}
              </div>
              <div style={{ fontSize: 10, color: "var(--text-dim)", marginTop: 2 }}>
                {entry.total_portfolios} days total
              </div>
            </div>

            {/* Stats */}
            {[
              { label: "Avg Return",  value: pct(entry.average_return_percent),  color: returnColor(entry.average_return_percent) },
              { label: "Best Day",    value: pct(entry.best_return_percent),      color: "var(--green)" },
              { label: "Worst Day",   value: pct(entry.worst_return_percent),     color: "var(--red)" },
              { label: "Latest",      value: pct(entry.latest_return),            color: returnColor(entry.latest_return) },
              { label: "Win Rate",    value: fmt(entry.win_rate, 1) + "%",        color: "var(--gold)" },
              { label: "Days Active", value: String(entry.days_active),           color: "var(--text)" },
            ].map(({ label, value, color: c }) => (
              <div key={label}>
                <div style={{ fontSize: 10, color: "var(--text-dim)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
                  {label}
                </div>
                <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 15, color: c }}>
                  {value}
                </div>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

// ─── Market Intel Page (ENHANCED) ─────────────────────────────────────────────

function MarketPage({ sim, loading }: { sim: SimData | null; loading: boolean }) {
  const [sort, setSort] = useState<keyof Candidate>("topsis_score");
  const [asc, setAsc]   = useState(false);

  if (loading) return <div style={{ display: "flex", justifyContent: "center", paddingTop: 60 }}><Spinner /></div>;

  const candidates = [...(sim?.market_candidates ?? [])].sort((a, b) => {
    const av = a[sort] as number;
    const bv = b[sort] as number;
    return asc ? av - bv : bv - av;
  });

  function handleSort(col: keyof Candidate) {
    if (sort === col) setAsc((p) => !p);
    else { setSort(col); setAsc(false); }
  }

  const cols: { key: keyof Candidate; label: string }[] = [
    { key: "ticker",          label: "Ticker" },
    { key: "sector",          label: "Sector" },
    { key: "current_price",   label: "Price ₹" },
    { key: "topsis_score",    label: "TOPSIS" },
    { key: "rsi",             label: "RSI" },
    { key: "one_month_return",label: "1M Ret%" },
    { key: "volume_ratio",    label: "Vol Ratio" },
    { key: "volatility",      label: "Volatility" },
    { key: "trend_score",     label: "Trend" },
  ];

  if (candidates.length === 0) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        {/* Empty State */}
        <div style={{
          background: "linear-gradient(135deg, var(--card) 0%, var(--card2) 100%)",
          border: "1px solid var(--border)",
          borderRadius: 12, padding: "40px 32px", textAlign: "center",
        }}>
          <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.6 }}>📈</div>
          <div style={{ fontFamily: "var(--font-display)", fontSize: 18, fontWeight: 700, marginBottom: 8 }}>
            No Market Data Available
          </div>
          <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 20, lineHeight: 1.6 }}>
            Run a simulation to analyze NIFTY200 candidates using TOPSIS methodology
          </div>
          <div style={{
            background: "var(--card)", borderRadius: 8, padding: "16px 20px",
            textAlign: "left", fontSize: 12, color: "var(--text-muted)", lineHeight: 1.8,
          }}>
            <div style={{ fontWeight: 600, color: "var(--text)", marginBottom: 10 }}>Expected Market Intel Content:</div>
            <ul style={{ paddingLeft: 20, gap: 4, display: "flex", flexDirection: "column" }}>
              <li>✓ <strong>TOPSIS Scoring</strong> — Multi-criteria decision analysis for stock ranking</li>
              <li>✓ <strong>Technical Indicators</strong> — RSI, volatility, trend scores, volume analysis</li>
              <li>✓ <strong>Price Data</strong> — Current NSE prices for all NIFTY200 constituents</li>
              <li>✓ <strong>Momentum Metrics</strong> — 1-month returns, volume ratio (vs 20-day avg)</li>
              <li>✓ <strong>Sector Filtering</strong> — Sortable by sector to identify opportunities</li>
              <li>✓ <strong>Real-time Sorting</strong> — Click column headers to sort by any metric</li>
            </ul>
          </div>
        </div>

        {/* Analysis Guide */}
        <div style={{
          background: "var(--card)", border: "1px solid var(--border)",
          borderRadius: 10, padding: "24px 28px",
        }}>
          <SectionTitle>How to Read the Metrics</SectionTitle>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div style={{ background: "var(--card2)", borderRadius: 8, padding: "16px", border: "1px solid var(--border)" }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: "var(--accent)" }}>TOPSIS Score (0-1)</div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.6 }}>
                Higher scores indicate better overall stock quality. Top-ranked candidates typically have scores &gt; 0.7
              </div>
            </div>
            <div style={{ background: "var(--card2)", borderRadius: 8, padding: "16px", border: "1px solid var(--border)" }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: "var(--accent2)" }}>RSI (0-100)</div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.6 }}>
                &lt;30 = Oversold (potential buy), &gt;70 = Overbought (potential sell). 30-70 = neutral zone
              </div>
            </div>
            <div style={{ background: "var(--card2)", borderRadius: 8, padding: "16px", border: "1px solid var(--border)" }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: "var(--accent3)" }}>Volatility (%)</div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.6 }}>
                High volatility (&gt;40%) = riskier, potentially higher returns. Lower volatility = more stable stocks
              </div>
            </div>
            <div style={{ background: "var(--card2)", borderRadius: 8, padding: "16px", border: "1px solid var(--border)" }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: "var(--gold)" }}>Vol Ratio (&times;)</div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.6 }}>
                &gt;1.5x = High volume relative to 20-day average. Indicates institutional interest
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fade-up">
      <SectionTitle>TOPSIS Market Intelligence — {sim?.date ?? "—"}</SectionTitle>

      <div style={{ overflowX: "auto", background: "var(--card)", borderRadius: 10, border: "1px solid var(--border)" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {cols.map(({ key, label }) => (
                <th key={key} onClick={() => handleSort(key)} style={{
                  textAlign: "left", padding: "10px 14px", cursor: "pointer",
                  fontFamily: "var(--font-mono)", fontSize: 10,
                  letterSpacing: "0.08em", textTransform: "uppercase",
                  color: sort === key ? "var(--accent)" : "var(--text-dim)",
                  fontWeight: 500, userSelect: "none", whiteSpace: "nowrap",
                }}>
                  {label} {sort === key ? (asc ? "↑" : "↓") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {candidates.map((c, i) => (
              <tr key={c.ticker} style={{
                borderBottom: "1px solid var(--border)",
                background: i === 0 ? "var(--glow)" : "transparent",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--card2)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = i === 0 ? "var(--glow)" : "transparent")}
              >
                <td style={{ padding: "8px 14px", fontFamily: "var(--font-display)", fontWeight: 700, color: "var(--accent)" }}>
                  {c.ticker.replace(".NS", "")}
                </td>
                <td style={{ padding: "8px 14px" }}><Tag>{c.sector}</Tag></td>
                <td style={{ padding: "8px 14px" }}>{fmtINR(c.current_price)}</td>
                <td style={{ padding: "8px 14px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <div style={{
                      width: 50, height: 4, borderRadius: 2, background: "var(--border)",
                      position: "relative", overflow: "hidden",
                    }}>
                      <div style={{
                        position: "absolute", inset: 0,
                        width: `${c.topsis_score * 100}%`,
                        background: "var(--accent)",
                      }} />
                    </div>
                    <span style={{ color: "var(--accent)", fontWeight: 600 }}>{fmt(c.topsis_score, 4)}</span>
                  </div>
                </td>
                <td style={{ padding: "8px 14px", color: c.rsi > 70 ? "var(--red)" : c.rsi < 30 ? "var(--green)" : "var(--text)" }}>
                  {fmt(c.rsi, 1)}
                </td>
                <td style={{ padding: "8px 14px", color: returnColor(c.one_month_return), fontWeight: 600 }}>
                  {pct(c.one_month_return)}
                </td>
                <td style={{ padding: "8px 14px", color: c.volume_ratio > 1.5 ? "var(--gold)" : "var(--text-muted)" }}>
                  {fmt(c.volume_ratio, 2)}x
                </td>
                <td style={{ padding: "8px 14px", color: c.volatility > 40 ? "var(--red)" : "var(--text-muted)" }}>
                  {fmt(c.volatility, 1)}%
                </td>
                <td style={{ padding: "8px 14px", color: "var(--text-muted)" }}>{fmt(c.trend_score, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Portfolios Page (excerpt) ────────────────────────────────────────────────

interface PortfolioListItem {
  id: number;
  model: string;
  date: string;
  starting_capital: number;
  total_invested: number;
  remaining_cash: number;
  strategy_summary: string;
  risk_level: string;
  holdings_count: number;
}

interface PortfolioDetail extends PortfolioListItem {
  holdings: Holding[];
  latest_valuation: {
    portfolio_value: number;
    return_pct: number;
    unrealized_pnl: number;
  } | null;
  valuation_history: { date: string; portfolio_value: number; return_pct: number }[];
}

function PortfoliosPage() {
  const [list, setList]     = useState<PortfolioListItem[]>([]);
  const [detail, setDetail] = useState<PortfolioDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    const q = filter !== "all" ? `?model=${filter}` : "";
    setLoading(true);
    apiFetch<PortfolioListItem[]>(`/portfolios${q}`)
      .then(setList)
      .finally(() => setLoading(false));
  }, [filter]);

  function openDetail(id: number) {
    setDetailLoading(true);
    apiFetch<PortfolioDetail>(`/portfolios/${id}`)
      .then(setDetail)
      .finally(() => setDetailLoading(false));
  }

  const models = ["all", "gpt", "gemini", "mistral", "deepseek"];

  return (
    <div className="fade-up">
      <SectionTitle>Portfolio History</SectionTitle>

      {/* Filter */}
      <div style={{ display: "flex", gap: 8, marginBottom: 18 }}>
        {models.map((m) => (
          <button key={m} onClick={() => { setFilter(m); setDetail(null); }} style={{
            fontFamily: "var(--font-display)", fontSize: 11, fontWeight: 600,
            letterSpacing: "0.08em", textTransform: "uppercase",
            padding: "5px 12px", borderRadius: 5, border: "1px solid var(--border)",
            cursor: "pointer", transition: "all 0.15s",
            background: filter === m ? (MODEL_COLORS[m] ?? "var(--accent)") : "var(--card)",
            color: filter === m ? "#000" : "var(--text-muted)",
            borderColor: filter === m ? (MODEL_COLORS[m] ?? "var(--accent)") : "var(--border)",
          }}>
            {m === "all" ? "All" : MODEL_LABELS[m] ?? m}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ display: "flex", justifyContent: "center", paddingTop: 40 }}><Spinner /></div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: detail ? "1fr 1fr" : "1fr", gap: 20 }}>
          {/* List */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {list.length === 0 ? (
              <div style={{ color: "var(--text-muted)", textAlign: "center", padding: 40 }}>No portfolios found</div>
            ) : (
              list.map((p) => {
                const color = MODEL_COLORS[p.model] ?? "#888";
                return (
                  <div key={p.id} onClick={() => openDetail(p.id)} style={{
                    background: "var(--card)", border: `1px solid ${detail?.id === p.id ? color : "var(--border)"}`,
                    borderRadius: 8, padding: "12px 16px", cursor: "pointer", transition: "all 0.15s",
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600, color }}>{MODEL_LABELS[p.model] ?? p.model}</div>
                        <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>{p.date}</div>
                      </div>
                      <Tag>{p.holdings_count} holdings</Tag>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Detail */}
          {detail && (
            <div>
              {detailLoading ? (
                <div style={{ display: "flex", justifyContent: "center", padding: 40 }}><Spinner /></div>
              ) : (
                <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 10, padding: 20, display: "flex", flexDirection: "column", gap: 18 }}>
                  {/* Header */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div>
                      <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                        Portfolio Detail
                      </div>
                      <div style={{
                        fontFamily: "var(--font-display)", fontSize: 16, fontWeight: 700, marginTop: 4,
                        color: MODEL_COLORS[detail.model] ?? "var(--text)",
                      }}>
                        {MODEL_ICONS[detail.model]} {MODEL_LABELS[detail.model] ?? detail.model}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>{detail.date}</div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <Tag color={RISK_COLOR[detail.risk_level] ?? "var(--text-muted)"}>{detail.risk_level}</Tag>
                      {detail.latest_valuation && (
                        <div style={{
                          fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 800, marginTop: 6,
                          color: returnColor(detail.latest_valuation.return_pct),
                        }}>
                          {pct(detail.latest_valuation.return_pct)}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Key Stats */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                    {[
                      { label: "Capital",  value: fmtINR(detail.starting_capital),  color: "var(--text)" },
                      { label: "Invested", value: fmtINR(detail.total_invested),     color: MODEL_COLORS[detail.model] ?? "var(--accent)" },
                      { label: "Cash",     value: fmtINR(detail.remaining_cash),     color: "var(--text-muted)" },
                      ...(detail.latest_valuation ? [
                        { label: "Curr. Value", value: fmtINR(detail.latest_valuation.portfolio_value), color: "var(--text)" },
                        { label: "Unr. P&L",   value: fmtINR(detail.latest_valuation.unrealized_pnl),  color: returnColor(detail.latest_valuation.unrealized_pnl) },
                        { label: "Holdings",    value: String(detail.holdings_count),                   color: "var(--gold)" },
                      ] : [
                        { label: "Holdings", value: String(detail.holdings_count), color: "var(--gold)" },
                      ]),
                    ].map(({ label, value, color }) => (
                      <div key={label} style={{
                        background: "var(--card2)", borderRadius: 7, padding: "10px 12px",
                        border: "1px solid var(--border)",
                      }}>
                        <div style={{ fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 4 }}>
                          {label}
                        </div>
                        <div style={{ fontSize: 13, fontFamily: "var(--font-display)", fontWeight: 700, color }}>
                          {value}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Strategy */}
                  <div style={{ background: "var(--card2)", borderRadius: 7, padding: "10px 14px", border: "1px solid var(--border)" }}>
                    <div style={{ fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}>
                      Strategy
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.6 }}>
                      {detail.strategy_summary}
                    </div>
                  </div>

                  {/* Valuation History Sparkline */}
                  {detail.valuation_history.length > 0 && (
                    <div>
                      <div style={{ fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>
                        Value Over Time
                      </div>
                      <div style={{ background: "var(--card2)", borderRadius: 7, padding: "12px 8px", border: "1px solid var(--border)" }}>
                        <ResponsiveContainer width="100%" height={100}>
                          <AreaChart data={detail.valuation_history}>
                            <defs>
                              <linearGradient id="detailGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%"  stopColor={MODEL_COLORS[detail.model] ?? "#888"} stopOpacity={0.3} />
                                <stop offset="95%" stopColor={MODEL_COLORS[detail.model] ?? "#888"} stopOpacity={0} />
                              </linearGradient>
                            </defs>
                            <XAxis dataKey="date" tick={{ fontSize: 9, fill: "var(--text-dim)" }} />
                            <YAxis tick={{ fontSize: 9, fill: "var(--text-dim)" }} width={55}
                              tickFormatter={(v: number) => fmtINR(v)} />
                            <Tooltip
                              contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 6, fontSize: 10 }}
                              formatter={(v: number) => [fmtINR(v), "Portfolio Value"]}
                            />
                            <Area
                              type="monotone" dataKey="portfolio_value"
                              stroke={MODEL_COLORS[detail.model] ?? "#888"} strokeWidth={2}
                              fill="url(#detailGrad)"
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  )}

                  {/* Holdings Table */}
                  {detail.holdings.length > 0 && (
                    <div>
                      <div style={{ fontSize: 9, color: "var(--text-dim)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>
                        Holdings
                      </div>
                      <HoldingsTable
                        holdings={detail.holdings}
                        modelColor={MODEL_COLORS[detail.model] ?? "#888"}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── History Page ─────────────────────────────────────────────────────────────

function HistoryPage() {
  const [history, setHistory] = useState<HistoryMap>({});
  const [activeModels, setActiveModels] = useState<string[]>(["gpt", "gemini", "mistral", "deepseek"]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<HistoryMap>("/analytics/history")
      .then(setHistory)
      .finally(() => setLoading(false));
  }, []);

  function toggleModel(m: string) {
    setActiveModels((prev) =>
      prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]
    );
  }

  if (loading) return <div style={{ display: "flex", justifyContent: "center", paddingTop: 60 }}><Spinner /></div>;

  // Merge all dates
  const allDates = Array.from(new Set(
    Object.values(history).flatMap((rows) => rows.map((r) => r.date))
  )).sort();

  const chartData = allDates.map((date) => {
    const point: Record<string, string | number> = { date };
    for (const [model, rows] of Object.entries(history)) {
      const row = rows.find((r) => r.date === date);
      if (row) point[model] = row.return_pct;
    }
    return point;
  });

  // Win rate bar data
  const winData = Object.entries(history).map(([model, rows]) => ({
    model: MODEL_LABELS[model] ?? model,
    winRate: rows.length > 0 ? Math.round((rows.filter((r) => r.return_pct > 0).length / rows.length) * 100) : 0,
    color: MODEL_COLORS[model] ?? "#888",
  }));

  return (
    <div className="fade-up" style={{ display: "flex", flexDirection: "column", gap: 28 }}>
      <div>
        <SectionTitle>Performance History</SectionTitle>

        {/* Toggle buttons */}
        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          {Object.keys(history).map((m) => (
            <button key={m} onClick={() => toggleModel(m)} style={{
              fontFamily: "var(--font-display)", fontSize: 11, fontWeight: 600,
              letterSpacing: "0.06em", textTransform: "uppercase",
              padding: "5px 12px", borderRadius: 5,
              border: `1px solid ${MODEL_COLORS[m] ?? "#888"}`,
              cursor: "pointer", transition: "all 0.15s",
              background: activeModels.includes(m) ? (MODEL_COLORS[m] ?? "#888") : "transparent",
              color: activeModels.includes(m) ? "#000" : (MODEL_COLORS[m] ?? "#888"),
            }}>
              {MODEL_LABELS[m] ?? m}
            </button>
          ))}
        </div>

        <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 10, padding: "20px 16px" }}>
          {chartData.length === 0 ? (
            <div style={{ textAlign: "center", color: "var(--text-muted)", padding: 40 }}>No history data yet</div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={chartData}>
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--text-dim)" }} />
                <YAxis
                  tick={{ fontSize: 10, fill: "var(--text-dim)" }}
                  tickFormatter={(v: number) => `${v > 0 ? "+" : ""}${v.toFixed(2)}%`}
                />
                <Tooltip
                  contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 11 }}
                  formatter={(v: number, name: string) => [pct(v), MODEL_LABELS[name] ?? name]}
                />
                <Legend formatter={(v) => MODEL_LABELS[v] ?? v} wrapperStyle={{ fontSize: 11 }} />
                {Object.keys(history).filter((m) => activeModels.includes(m)).map((model) => (
                  <Line
                    key={model} type="monotone"
                    dataKey={model}
                    stroke={MODEL_COLORS[model] ?? "#888"}
                    strokeWidth={2} dot={false}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Win Rate Bar Chart */}
      {winData.length > 0 && (
        <div>
          <SectionTitle>Win Rate Comparison</SectionTitle>
          <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 10, padding: "20px 16px" }}>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={winData}>
                <XAxis dataKey="model" tick={{ fontSize: 10, fill: "var(--text-dim)" }} />
                <YAxis tick={{ fontSize: 10, fill: "var(--text-dim)" }} domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} />
                <Tooltip
                  contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 11 }}
                  formatter={(v: number) => [`${v}%`, "Win Rate"]}
                />
                <Bar dataKey="winRate" radius={[4, 4, 0, 0]}>
                  {winData.map((d, i) => (
                    <Cell key={i} fill={d.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Admin Banner ─────────────────────────────────────────────────────────────

function AdminBanner() {
  const [status, setStatus]   = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function runSimulation() {
    setRunning(true);
    setStatus("Running simulation…");
    try {
      const res = await fetch(`${API}/simulate-and-save`, { method: "POST" });
      const data = await res.json() as { message: string };
      setStatus(data.message);
    } catch {
      setStatus("Error contacting backend");
    } finally {
      setRunning(false);
    }
  }

  async function updateValuations() {
    setRunning(true);
    setStatus("Updating valuations…");
    try {
      const res  = await fetch(`${API}/update-valuations`, { method: "POST" });
      const data = await res.json() as { message: string };
      setStatus(data.message);
    } catch {
      setStatus("Error contacting backend");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div style={{
      background: "var(--card)", border: "1px solid var(--border)",
      borderRadius: 10, padding: "14px 18px",
      display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
    }}>
      <span style={{
        fontFamily: "var(--font-display)", fontSize: 11, fontWeight: 600,
        letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--text-muted)",
      }}>
        Admin
      </span>
      <AdminBtn label="▶ Run Simulation"     onClick={runSimulation}    disabled={running} />
      <AdminBtn label="↻ Update Valuations"  onClick={updateValuations} disabled={running} />
      {status && (
        <span style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
          {running && <span style={{ marginRight: 6 }}>⟳</span>}{status}
        </span>
      )}
    </div>
  );
}

function AdminBtn({ label, onClick, disabled }: { label: string; onClick: () => void; disabled: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      fontFamily: "var(--font-display)", fontSize: 11, fontWeight: 600,
      letterSpacing: "0.06em", textTransform: "uppercase",
      padding: "6px 14px", borderRadius: 6,
      border: "1px solid var(--border-hi)",
      background: disabled ? "var(--card2)" : "var(--surface)",
      color: disabled ? "var(--text-dim)" : "var(--text)",
      cursor: disabled ? "not-allowed" : "pointer",
      transition: "all 0.15s",
    }}>
      {label}
    </button>
  );
}

// ─── Root ─────────────────────────────────────────────────────────────────────

export default function Home() {
  const [isDark, setIsDark] = useState(true);
  const [page, setPage]     = useState<Page>("dashboard");
  const [sim, setSim]       = useState<SimData | null>(null);
  const [simLoading, setSimLoading] = useState(true);

  // Apply theme to document
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
  }, [isDark]);

  const loadSim = useCallback(() => {
    setSimLoading(true);
    apiFetch<SimData>("/simulation/today")
      .then(setSim)
      .catch((e: unknown) => console.error("sim load failed", e))
      .finally(() => setSimLoading(false));
  }, []);

  useEffect(() => { loadSim(); }, [loadSim]);

  return (
    <>
      <Navbar
        page={page}
        setPage={setPage}
        isDark={isDark}
        onToggle={() => setIsDark((d) => !d)}
        simDate={sim?.date ?? null}
      />

      <main style={{
        maxWidth: 1400, margin: "0 auto",
        padding: "76px 24px 60px",
        display: "flex", flexDirection: "column", gap: 24,
      }}>
        {/* Page content */}
        <div className="fade-up-1">
          {page === "dashboard"   && <DashboardPage  sim={sim}  loading={simLoading} />}
          {page === "leaderboard" && <LeaderboardPage />}
          {page === "market"      && <MarketPage      sim={sim}  loading={simLoading} />}
          {page === "portfolios"  && <PortfoliosPage />}
          {page === "history"     && <HistoryPage />}
        </div>
      </main>
    </>
  );
}