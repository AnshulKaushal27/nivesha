"use client";

import type { CSSProperties, ReactNode } from "react";

/* ── Page header: every page opens the same way ─────────────────────── */
export function PageHeader({ eyebrow, title, blurb, aside }: {
  eyebrow: string; title: string; blurb?: ReactNode; aside?: ReactNode;
}) {
  return (
    <section className="fade-up" style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 16 }}>
      <div style={{ maxWidth: 720 }}>
        <div className="eyebrow">{eyebrow}</div>
        <h1 style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 32, letterSpacing: "-0.02em", marginTop: 6, lineHeight: 1.15 }}>{title}</h1>
        {blurb && <p style={{ color: "var(--text-2)", marginTop: 8, lineHeight: 1.55 }}>{blurb}</p>}
      </div>
      {aside && <div style={{ fontSize: 13, color: "var(--text-muted)" }}>{aside}</div>}
    </section>
  );
}

/* ── Glass segmented tabs ───────────────────────────────────────────── */
export function Tabs<T extends string>({ tabs, value, onChange, ariaLabel }: {
  tabs: { id: T; label: string; icon?: string; count?: number }[]; value: T; onChange: (t: T) => void; ariaLabel: string;
}) {
  return (
    <div role="tablist" aria-label={ariaLabel} className="glass" style={{ display: "inline-flex", flexWrap: "wrap", gap: 4, padding: 4, borderRadius: 999 }}>
      {tabs.map((t) => {
        const active = t.id === value;
        return (
          <button key={t.id} role="tab" aria-selected={active} onClick={() => onChange(t.id)} style={{
            padding: "8px 14px", borderRadius: 999, fontSize: 13.5, fontWeight: 700, whiteSpace: "nowrap",
            color: active ? "var(--accent-ink)" : "var(--text-2)",
            background: active ? "var(--card)" : "transparent",
            boxShadow: active ? "var(--shadow)" : "none",
            transition: "all 0.18s ease",
          }}>
            {t.icon && <span aria-hidden style={{ marginRight: 6, opacity: 0.85 }}>{t.icon}</span>}
            {t.label}
            {t.count != null && <span className="tnum" style={{ marginLeft: 6, fontSize: 11, color: "var(--text-muted)" }}>{t.count}</span>}
          </button>
        );
      })}
    </div>
  );
}

/* ── Stat tile: one number, one label, optional tone ────────────────── */
export function StatTile({ label, value, sub, tone, style }: {
  label: string; value: ReactNode; sub?: ReactNode; tone?: "strong" | "good" | "neutral" | "weak" | "accent"; style?: CSSProperties;
}) {
  const soft = tone ? `var(--${tone}-soft)` : "var(--card)";
  const ink = tone ? `var(--${tone}-ink)` : "var(--text)";
  return (
    <div className="card" style={{ padding: "16px 18px", background: soft, borderColor: tone ? "transparent" : "var(--border)", ...style }}>
      <div className="eyebrow" style={{ color: tone ? ink : "var(--text-muted)", opacity: 0.85 }}>{label}</div>
      <div className="tnum" style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 28, marginTop: 6, color: ink, lineHeight: 1.1 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: tone ? ink : "var(--text-muted)", marginTop: 4, opacity: 0.9 }}>{sub}</div>}
    </div>
  );
}

/* ── Section card with a title row ──────────────────────────────────── */
export function Section({ title, sub, action, children, style, className }: {
  title: string; sub?: ReactNode; action?: ReactNode; children: ReactNode; style?: CSSProperties; className?: string;
}) {
  return (
    <section className={`card ${className ?? ""}`} style={{ padding: 22, ...style }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, marginBottom: 14 }}>
        <div>
          <h2 style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 18 }}>{title}</h2>
          {sub && <div style={{ fontSize: 12.5, color: "var(--text-muted)", marginTop: 2 }}>{sub}</div>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

/* ── Load more ──────────────────────────────────────────────────────── */
export function LoadMore({ shown, total, step = 20, onMore }: { shown: number; total: number; step?: number; onMore: () => void }) {
  if (shown >= total) return total > 0 ? <div style={{ textAlign: "center", padding: 14, fontSize: 12.5, color: "var(--text-dim)" }}>All {total} shown</div> : null;
  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 14, padding: 16 }}>
      <span style={{ fontSize: 12.5, color: "var(--text-muted)" }}>Showing {shown} of {total}</span>
      <button onClick={onMore} className="glass" style={{ padding: "9px 18px", borderRadius: 999, fontWeight: 800, fontSize: 13, color: "var(--accent-ink)" }}>
        Load {Math.min(step, total - shown)} more ↓
      </button>
    </div>
  );
}

/* ── Empty / error ──────────────────────────────────────────────────── */
export function EmptyState({ icon = "○", title, body, action }: { icon?: string; title: string; body?: ReactNode; action?: ReactNode }) {
  return (
    <div className="card" style={{ padding: 36, textAlign: "center" }}>
      <div aria-hidden style={{ fontSize: 26, color: "var(--text-dim)" }}>{icon}</div>
      <div style={{ fontWeight: 800, marginTop: 8 }}>{title}</div>
      {body && <div style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 4, lineHeight: 1.5 }}>{body}</div>}
      {action && <div style={{ marginTop: 14 }}>{action}</div>}
    </div>
  );
}

export function Pill({ children, tone = "accent" }: { children: ReactNode; tone?: "strong" | "good" | "neutral" | "weak" | "accent" | "wait" }) {
  return <span className="chip" style={{ background: `var(--${tone}-soft)`, color: `var(--${tone}-ink)` }}>{children}</span>;
}

export function Button({ children, onClick, disabled, variant = "primary" }: {
  children: ReactNode; onClick?: () => void; disabled?: boolean; variant?: "primary" | "ghost";
}) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      padding: "9px 16px", borderRadius: 999, fontWeight: 800, fontSize: 13,
      background: variant === "primary" ? "var(--accent-soft)" : "transparent",
      color: "var(--accent-ink)", border: variant === "ghost" ? "1px solid var(--border)" : "1px solid transparent",
      opacity: disabled ? 0.55 : 1, cursor: disabled ? "not-allowed" : "pointer",
    }}>{children}</button>
  );
}
