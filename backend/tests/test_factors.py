import numpy as np
import pandas as pd

from quant.buyrank import band_for, rank_cross_section, topsis_closeness
from quant.factors import FACTOR_NAMES, factor_panel


def test_factor_panel_shapes_and_bounds(synthetic_bars):
    raw, z, eligible = factor_panel(synthetic_bars)
    assert set(z.columns) == set(FACTOR_NAMES)
    last = z.index.get_level_values("date").max()
    zl = z.xs(last, level="date")
    el = eligible.xs(last, level="date")
    assert el.sum() >= 30, "most synthetic tickers should be eligible on the last day"
    assert np.nanmax(np.abs(zl.to_numpy())) <= 3.0 + 1e-9, "winsorised at ±3σ"
    # z-scores are centred on the eligible cross-section
    for f in ("mom_12_1", "low_vol", "liquidity"):
        assert abs(zl.loc[el, f].mean()) < 0.15


def test_first_year_is_ineligible(synthetic_bars):
    raw, z, eligible = factor_panel(synthetic_bars)
    first = z.index.get_level_values("date").min()
    assert not eligible.xs(first, level="date").any()


def test_rank_is_percentile_and_monotone(synthetic_bars):
    raw, z, eligible = factor_panel(synthetic_bars)
    ranked = rank_cross_section(z, eligible)
    last = ranked.index.get_level_values("date").max()
    r = ranked.xs(last, level="date").dropna(subset=["buy_rank"])
    assert r["buy_rank"].between(1, 100).all()
    assert r["buy_rank"].max() == 100
    order = r.sort_values("topsis")
    assert order["buy_rank"].is_monotonic_increasing
    # contributions = z × weight, so signs follow config
    assert (r["c_overheat"] * r_z(z, last)["overheat"] <= 1e-12).all()


def r_z(z, d):
    return z.xs(d, level="date")


def test_momentum_signal_is_captured(synthetic_bars):
    """Even-numbered tickers have positive drift; they should rank higher on average."""
    raw, z, eligible = factor_panel(synthetic_bars)
    ranked = rank_cross_section(z, eligible)
    last = ranked.index.get_level_values("date").max()
    r = ranked.xs(last, level="date").dropna(subset=["buy_rank"])
    even = r[[int(t[1:3]) % 2 == 0 for t in r.index]]["buy_rank"].mean()
    odd = r[[int(t[1:3]) % 2 == 1 for t in r.index]]["buy_rank"].mean()
    assert even > odd + 10


def test_topsis_extremes():
    Z = np.array([[1.0, 1.0], [0.0, 0.0], [-1.0, -1.0]])
    c = topsis_closeness(Z, np.array([0.5, 0.5]))
    assert c[0] > c[1] > c[2]
    assert np.isclose(c[0], 1.0) and np.isclose(c[2], 0.0)


def test_topsis_handles_nan_and_empty():
    assert topsis_closeness(np.empty((0, 3)), np.ones(3)).size == 0
    c = topsis_closeness(np.array([[np.nan, 1.0], [0.0, 0.0]]), np.array([1.0, 1.0]))
    assert np.isfinite(c).all()


def test_bands():
    assert band_for(85, None) == "Strong"
    assert band_for(85, "Cloudy") == "Strong"
    assert band_for(82, "Cloudy") == "Good"
    assert band_for(45, "Sunny") == "Neutral"
    assert band_for(10, "Sunny") == "Weak"
    assert band_for(95, "Stormy") == "Watch"
    assert band_for(85, "Stormy") == "Wait"
