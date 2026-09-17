"use client";

import type { Band } from "@/lib/api";
import { BAND } from "@/lib/signals";

/**
 * The Buy Rank ring: a 1–100 percentile drawn as an arc, coloured by band,
 * with the band word always visible so colour never carries meaning alone.
 */
export function RankRing({ rank, band, size = 96, stroke = 9, showWord = true }: {
  rank: number; band: Band; size?: number; stroke?: number; showWord?: boolean;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - Math.max(0, Math.min(100, rank)) / 100);
  const s = BAND[band];
  const decimal = !Number.isInteger(rank);
  const text = decimal ? rank.toFixed(1) : String(rank);
  const fontSize = Math.round(size * (decimal ? 0.24 : 0.3));
  return (
    <div role="img" aria-label={`Buy Rank ${text} out of 100, ${s.word}`}
         style={{ position: "relative", width: size, height: size, flex: "0 0 auto" }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={s.soft} strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={s.fill} strokeWidth={stroke}
                strokeLinecap="round" strokeDasharray={c} strokeDashoffset={offset}
                style={{ transition: "stroke-dashoffset 0.6s cubic-bezier(.2,.8,.2,1)" }} />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", textAlign: "center" }}>
        <div>
          <div className="tnum" style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize, lineHeight: 1, color: "var(--text)", letterSpacing: "-0.02em" }}>
            {text}
          </div>
          {showWord && (
            <div style={{ fontSize: Math.max(10, Math.round(size * 0.115)), fontWeight: 800, color: s.ink, marginTop: 3, letterSpacing: "0.02em" }}>
              {s.word}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function BandChip({ band, size = "md" }: { band: Band; size?: "sm" | "md" }) {
  const s = BAND[band];
  return (
    <span className="chip" style={{ background: s.soft, color: s.ink, fontSize: size === "sm" ? 11 : 12 }}>
      <span className="chip-dot" style={{ background: s.fill }} aria-hidden />
      {s.word}
    </span>
  );
}
