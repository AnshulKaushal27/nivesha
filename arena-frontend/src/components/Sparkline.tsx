"use client";

import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fmtDate } from "@/lib/signals";

/** Strength Score over time. One series, so no legend; the title names it. */
export function RankSparkline({ data, height = 160, color = "var(--accent)" }: {
  data: { date: string; buy_rank: number }[]; height?: number; color?: string;
}) {
  if (!data?.length) return <div className="skeleton" style={{ height }} />;
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
          <defs>
            <linearGradient id="rankFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.28} />
              <stop offset="100%" stopColor={color} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <XAxis dataKey="date" tickFormatter={(d: string) => fmtDate(d).slice(0, 6)} tick={{ fontSize: 11, fill: "var(--text-muted)" }}
                 axisLine={{ stroke: "var(--axis)" }} tickLine={false} minTickGap={36} />
          <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={{ fontSize: 11, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} />
          <Tooltip
            cursor={{ stroke: "var(--axis)", strokeDasharray: "3 3" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload as { date: string; buy_rank: number; close?: number };
              return (
                <div className="card" style={{ padding: "8px 12px", fontSize: 12, boxShadow: "var(--shadow-lg)" }}>
                  <div style={{ color: "var(--text-muted)" }}>{fmtDate(p.date)}</div>
                  <div style={{ fontWeight: 800, fontSize: 14 }}>Rank {p.buy_rank}</div>
                  {p.close != null && <div style={{ color: "var(--text-2)" }}>₹{p.close.toFixed(2)}</div>}
                </div>
              );
            }}
          />
          <Area type="monotone" dataKey="buy_rank" stroke={color} strokeWidth={2} fill="url(#rankFill)"
                dot={false} activeDot={{ r: 5, strokeWidth: 2, stroke: "var(--card)" }} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
