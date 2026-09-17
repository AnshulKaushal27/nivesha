"use client";

import type { FactorKey } from "@/lib/api";
import { FACTOR_LABEL, FACTOR_ORDER } from "@/lib/signals";

/**
 * Diverging bars of factor contributions (z × weight). Positive = helped the
 * rank (green), negative = hurt (rose). A neutral midline, values labelled.
 */
export function FactorBars({ contributions, compact = false }: {
  contributions: Record<FactorKey, number | null>; compact?: boolean;
}) {
  const vals = FACTOR_ORDER.map((k) => contributions?.[k] ?? 0);
  const max = Math.max(0.05, ...vals.map((v) => Math.abs(v)));
  return (
    <div style={{ display: "grid", gap: compact ? 6 : 10 }}>
      {FACTOR_ORDER.map((k) => {
        const v = contributions?.[k];
        const pct = v == null ? 0 : (Math.abs(v) / max) * 50;
        const pos = (v ?? 0) >= 0;
        return (
          <div key={k} style={{ display: "grid", gridTemplateColumns: compact ? "120px 1fr 52px" : "180px 1fr 60px", alignItems: "center", gap: 10 }}>
            <div style={{ fontSize: compact ? 12 : 13, fontWeight: 600, color: "var(--text-2)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}
                 title={FACTOR_LABEL[k].plain}>
              {FACTOR_LABEL[k].name}
            </div>
            <div style={{ position: "relative", height: compact ? 10 : 14, background: "var(--card2)", borderRadius: 999 }}>
              <div aria-hidden style={{ position: "absolute", left: "50%", top: -2, bottom: -2, width: 1, background: "var(--axis)" }} />
              <div style={{
                position: "absolute", top: 0, bottom: 0,
                left: pos ? "50%" : `${50 - pct}%`, width: `${pct}%`,
                background: pos ? "var(--strong)" : "var(--weak)",
                borderRadius: pos ? "0 999px 999px 0" : "999px 0 0 999px",
                transition: "width 0.5s ease, left 0.5s ease",
              }} />
            </div>
            <div className="tnum" style={{ fontSize: compact ? 12 : 13, fontWeight: 700, textAlign: "right",
                 color: v == null ? "var(--text-dim)" : pos ? "var(--strong-ink)" : "var(--weak-ink)" }}>
              {v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}`}
            </div>
          </div>
        );
      })}
    </div>
  );
}
