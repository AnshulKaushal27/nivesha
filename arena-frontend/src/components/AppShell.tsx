"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const NAV = [
  { href: "/",        label: "Buy Rank",  icon: "◎" },
  { href: "/legacy",  label: "Arena v1",  icon: "⬡" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [dark, setDark] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("arena-theme");
      if (saved === "dark") setDark(true);
    } catch { /* private mode */ }
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    try { localStorage.setItem("arena-theme", dark ? "dark" : "light"); } catch { /* ignore */ }
  }, [dark]);

  // The legacy page ships its own fixed navbar; give it the whole viewport.
  if (path?.startsWith("/legacy")) return <>{children}</>;

  return (
    <>
      <header style={{
        position: "sticky", top: 0, zIndex: 50,
        background: "color-mix(in srgb, var(--bg) 82%, transparent)",
        backdropFilter: "saturate(1.4) blur(12px)", WebkitBackdropFilter: "saturate(1.4) blur(12px)",
        borderBottom: "1px solid var(--border)",
      }}>
        <div style={{ maxWidth: 1240, margin: "0 auto", padding: "0 24px", height: 64, display: "flex", alignItems: "center", gap: 20 }}>
          <Link href="/" style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span aria-hidden style={{
              width: 34, height: 34, borderRadius: 10, display: "grid", placeItems: "center",
              background: "linear-gradient(135deg, var(--strong-soft), var(--accent-soft))",
              color: "var(--accent-ink)", fontWeight: 800, fontSize: 16,
            }}>◎</span>
            <span style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 17, letterSpacing: "-0.01em" }}>
              AI Investment Arena
            </span>
          </Link>

          <nav aria-label="Primary" style={{ display: "flex", gap: 4, marginLeft: 16 }}>
            {NAV.map((n) => {
              const active = n.href === "/" ? path === "/" : path?.startsWith(n.href);
              return (
                <Link key={n.href} href={n.href} aria-current={active ? "page" : undefined} style={{
                  padding: "7px 12px", borderRadius: 999, fontSize: 13.5, fontWeight: 700,
                  color: active ? "var(--accent-ink)" : "var(--text-2)",
                  background: active ? "var(--accent-soft)" : "transparent",
                  transition: "background 0.15s",
                }}>
                  <span aria-hidden style={{ marginRight: 6, opacity: 0.8 }}>{n.icon}</span>{n.label}
                </Link>
              );
            })}
          </nav>

          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10 }}>
            <button onClick={() => setDark((d) => !d)} aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} style={{
              width: 36, height: 36, borderRadius: 999, border: "1px solid var(--border)",
              background: "var(--card)", display: "grid", placeItems: "center", fontSize: 15,
            }}>
              {dark ? "☀" : "☾"}
            </button>
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 1240, margin: "0 auto", padding: "28px 24px 64px" }}>
        {children}
      </main>

      <footer style={{ borderTop: "1px solid var(--border)", padding: "20px 24px", textAlign: "center", fontSize: 12, color: "var(--text-muted)" }}>
        Educational simulation. Not investment advice. Past performance of simulated portfolios does not predict future results.
      </footer>
    </>
  );
}
