"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ChatDock } from "@/components/ChatDock";

const NAV = [
  { href: "/",        label: "Strength Rank", icon: "◎", hint: "Which stocks are strongest today, scored 1–100" },
  { href: "/predict", label: "3-Month Odds",  icon: "◆", hint: "Each stock's chance of beating the market over the next 3 months" },
  { href: "/arena",   label: "AI Managers",   icon: "⬡", hint: "Four AI managers compete with paper money" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [dark, setDark] = useState(false);

  useEffect(() => {
    try { if (localStorage.getItem("arena-theme") === "dark") setDark(true); } catch { /* private mode */ }
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    try { localStorage.setItem("arena-theme", dark ? "dark" : "light"); } catch { /* ignore */ }
  }, [dark]);

  if (path?.startsWith("/legacy")) return <>{children}</>;

  return (
    <>
      {/* soft pastel wash behind everything */}
      <div aria-hidden style={{
        position: "fixed", inset: 0, zIndex: -1, pointerEvents: "none",
        background: "radial-gradient(900px 500px at 8% -10%, var(--strong-soft), transparent 60%), radial-gradient(800px 500px at 100% 0%, var(--accent-soft), transparent 55%), radial-gradient(700px 400px at 50% 110%, var(--good-soft), transparent 60%)",
        opacity: 0.8,
      }} />

      <header style={{ position: "sticky", top: 0, zIndex: 50, padding: "12px 24px" }}>
        <div className="glass" style={{ maxWidth: 1240, margin: "0 auto", height: 60, borderRadius: 999, display: "flex", alignItems: "center", gap: 14, padding: "0 10px 0 16px" }}>
          <Link href="/" style={{ display: "flex", alignItems: "center", gap: 10, marginRight: 6 }}>
            <span aria-hidden style={{
              width: 34, height: 34, borderRadius: 12, display: "grid", placeItems: "center",
              background: "linear-gradient(135deg, var(--strong-soft), var(--accent-soft))",
              color: "var(--accent-ink)", fontWeight: 800, fontSize: 16,
            }}>◎</span>
            <span style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 16.5, letterSpacing: "-0.01em" }}>Nivesha</span>
          </Link>

          <nav aria-label="Primary" style={{ display: "flex", gap: 4, padding: 4, borderRadius: 999, background: "color-mix(in srgb, var(--card2) 60%, transparent)" }}>
            {NAV.map((n) => {
              const active = n.href === "/" ? path === "/" || path?.startsWith("/rank") : path?.startsWith(n.href);
              return (
                <Link key={n.href} href={n.href} title={n.hint} aria-current={active ? "page" : undefined} style={{
                  padding: "8px 14px", borderRadius: 999, fontSize: 13.5, fontWeight: 700, whiteSpace: "nowrap",
                  color: active ? "var(--accent-ink)" : "var(--text-2)",
                  background: active ? "var(--card)" : "transparent",
                  boxShadow: active ? "var(--shadow)" : "none",
                  transition: "all 0.18s ease",
                }}>
                  <span aria-hidden style={{ marginRight: 6, opacity: 0.85 }}>{n.icon}</span>{n.label}
                </Link>
              );
            })}
          </nav>

          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
            <button onClick={() => setDark((d) => !d)} aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} style={{
              width: 40, height: 40, borderRadius: 999, background: "var(--card)", boxShadow: "var(--shadow)", display: "grid", placeItems: "center", fontSize: 15,
            }}>
              {dark ? "☀" : "☾"}
            </button>
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 1240, margin: "0 auto", padding: "20px 24px 64px" }}>
        {children}
      </main>

      <footer style={{ borderTop: "1px solid var(--border)", padding: "20px 24px", textAlign: "center", fontSize: 12, color: "var(--text-muted)", lineHeight: 1.6 }}>
        Educational simulation. Not investment advice. Past performance of simulated portfolios does not predict future results.
        <br /><Link href="/legacy" style={{ color: "var(--text-dim)" }}>Legacy v1 interface</Link>
      </footer>

      <ChatDock />
    </>
  );
}
