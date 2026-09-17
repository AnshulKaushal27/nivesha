"""
Does Buy Rank predict anything? The gate before the score is shown to anyone.

    python -m research.factor_eval                # uses bars in the database
    python -m research.factor_eval --horizon 21 --out research/reports

Reports:
  * daily Spearman IC between the TOPSIS score and the next-`horizon` return,
    its rolling 12-month mean and t-statistic;
  * the same IC per factor (marginal usefulness, drives weight changes);
  * decile portfolios rebalanced every `horizon` days: gross and net spread.

Pass criteria from docs/DESIGN.md: rolling mean IC ≥ 0.03 with t ≥ 2, and a
positive top-minus-bottom decile spread after 0.3% round-trip cost.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from quant.buyrank import rank_cross_section
from quant.factors import FACTOR_NAMES, bars_to_panels, compute_factors, compute_raw, eligibility

logger = logging.getLogger(__name__)


def evaluate(bars: pd.DataFrame, horizon: int = 21, cost: float = 0.003) -> dict:
    close, volume = bars_to_panels(bars)
    raw = compute_raw(close, volume)
    eligible = eligibility(raw)
    z = compute_factors(raw, eligible)
    ranked = rank_cross_section(z, eligible)

    logp = np.log(close)
    fwd = (logp.shift(-horizon) - logp).stack(future_stack=True)
    fwd.index.names = ["date", "ticker"]

    df = pd.concat([z, ranked[["topsis", "buy_rank"]], fwd.rename("fwd")], axis=1)
    df = df[eligible.reindex(df.index).fillna(False).astype(bool)].dropna(subset=["topsis", "fwd"])
    if df.empty:
        raise ValueError("Not enough history for an evaluation (need > 252 + horizon days).")

    # ── Information coefficient ────────────────────────────────────────
    def ic_of(col: str) -> pd.Series:
        return df.groupby(level="date").apply(lambda g: g[col].corr(g["fwd"], method="spearman") if len(g) >= 20 else np.nan).dropna()

    ic = ic_of("topsis")
    per_factor = {f: ic_of(f) for f in FACTOR_NAMES}

    def summarise(s: pd.Series) -> dict:
        n = len(s)
        return {
            "mean": float(s.mean()), "std": float(s.std()),
            "t_stat": float(s.mean() / s.std() * np.sqrt(n)) if n > 1 and s.std() > 0 else float("nan"),
            "hit_rate": float((s > 0).mean()), "n_days": int(n),
            "rolling_12m_mean_latest": float(s.rolling(252, min_periods=120).mean().dropna().iloc[-1]) if n >= 120 else float("nan"),
        }

    # ── Decile portfolios ──────────────────────────────────────────────
    dates = sorted(df.index.get_level_values("date").unique())
    rebalance_dates = dates[::horizon]
    rows = []
    for d in rebalance_dates:
        g = df.xs(d, level="date")
        if len(g) < 50:
            continue
        dec = pd.qcut(g["topsis"].rank(method="first"), 10, labels=False) + 1
        rows.append(g.groupby(dec)["fwd"].mean().rename(d))
    deciles = pd.DataFrame(rows)
    decile_mean = deciles.mean() if not deciles.empty else pd.Series(dtype=float)
    periods_per_year = 252 / horizon
    spread_gross = float(decile_mean.get(10, np.nan) - decile_mean.get(1, np.nan)) if not decile_mean.empty else float("nan")
    spread_net = spread_gross - 2 * cost                     # buy and sell each period, both legs

    return {
        "horizon": horizon,
        "n_dates": len(dates),
        "first_date": str(dates[0].date()), "last_date": str(dates[-1].date()),
        "ic": summarise(ic),
        "ic_series": ic,
        "per_factor_ic": {f: summarise(s) for f, s in per_factor.items()},
        "decile_mean_period_return": {int(k): float(v) for k, v in decile_mean.items()},
        "decile_mean_annualised": {int(k): float(v * periods_per_year) for k, v in decile_mean.items()},
        "spread_gross_period": spread_gross,
        "spread_net_period": spread_net,
        "spread_net_annualised": spread_net * periods_per_year,
        "n_rebalances": int(len(deciles)),
        "passes": bool(
            not np.isnan(summarise(ic)["t_stat"]) and summarise(ic)["mean"] >= 0.03
            and summarise(ic)["t_stat"] >= 2 and spread_net > 0
        ),
    }


def to_markdown(r: dict) -> str:
    ic = r["ic"]
    lines = [
        f"# Buy Rank factor evaluation — {date.today()}",
        "",
        f"Sample: {r['first_date']} → {r['last_date']}, {r['n_dates']} days, horizon {r['horizon']} trading days.",
        "",
        "## Verdict",
        "",
        f"**{'PASS' if r['passes'] else 'FAIL'}** — mean IC {ic['mean']:.4f} (t = {ic['t_stat']:.2f}, "
        f"hit rate {ic['hit_rate']:.0%}), net decile spread {r['spread_net_period']:.2%} per period "
        f"({r['spread_net_annualised']:.1%} annualised).",
        "",
        "Pass criteria: mean IC ≥ 0.03, t ≥ 2, net top-minus-bottom spread > 0.",
        "",
        "## Composite score",
        "",
        "| metric | value |", "| --- | --- |",
        f"| mean daily IC | {ic['mean']:.4f} |",
        f"| IC std | {ic['std']:.4f} |",
        f"| t-stat | {ic['t_stat']:.2f} |",
        f"| IC > 0 share of days | {ic['hit_rate']:.1%} |",
        f"| rolling 12m mean IC (latest) | {ic['rolling_12m_mean_latest']:.4f} |",
        "",
        "## Per-factor IC (marginal usefulness)",
        "",
        "| factor | mean IC | t-stat | hit rate |", "| --- | --- | --- | --- |",
    ]
    for f, s in r["per_factor_ic"].items():
        lines.append(f"| {f} | {s['mean']:.4f} | {s['t_stat']:.2f} | {s['hit_rate']:.0%} |")
    lines += ["", "A factor with negative mean IC and |t| > 2 should have its weight set to zero in config.", "",
              "## Decile portfolios (equal-weight, rebalanced every horizon)", "",
              "| decile | mean period return | annualised |", "| --- | --- | --- |"]
    for k in sorted(r["decile_mean_period_return"]):
        lines.append(f"| {k} | {r['decile_mean_period_return'][k]:.2%} | {r['decile_mean_annualised'][k]:.1%} |")
    lines += ["", f"Top − bottom, gross: {r['spread_gross_period']:.2%} per period; net of 0.3% round-trip: "
              f"{r['spread_net_period']:.2%}. Rebalances: {r['n_rebalances']}."]
    return "\n".join(lines)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--horizon", type=int, default=21)
    p.add_argument("--cost", type=float, default=0.003)
    p.add_argument("--out", default="research/reports")
    a = p.parse_args()

    from data.bars import load_bars
    from data.universe import universe_tickers
    from database import SessionLocal

    db = SessionLocal()
    try:
        bars = load_bars(db, tickers=universe_tickers(db), start=date(2000, 1, 1))
    finally:
        db.close()
    logger.info("Loaded %d bars for %d tickers", len(bars), bars["ticker"].nunique() if not bars.empty else 0)

    r = evaluate(bars, horizon=a.horizon, cost=a.cost)
    md = to_markdown(r)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"factor_eval_{date.today()}.md"
    path.write_text(md)
    r["ic_series"].rename("ic").to_csv(out / f"ic_series_{date.today()}.csv")
    print(md)
    print(f"\nSaved → {path}")


if __name__ == "__main__":
    main()
