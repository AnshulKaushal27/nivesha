from types import SimpleNamespace

from llm.audit import allowed_from, numbers_in, offending_numbers
from llm.explain import build_table, template_explanation


def test_numbers_in_normalises():
    assert numbers_in("up 1,234.50 and -0.30%") == ["1234.5", "0.3"]
    assert numbers_in("12-month momentum") == ["12"]


def test_offending_respects_rounding_and_structural():
    allowed = allowed_from([18.437, 0.62, 1.5])
    assert offending_numbers("Momentum of 18.4% helped; z 0.62.", allowed) == []
    assert offending_numbers("Momentum of 18% over 12 months.", allowed) == []
    assert offending_numbers("It rose 27% recently.", allowed) == ["27"]


def _fake_score():
    return SimpleNamespace(
        ticker="RELIANCE.NS", date="2026-09-16", buy_rank=78, band="Good", close=2950.5, sector="Energy",
        raw={"mom_12_1": 0.17, "mom_6_1": 0.05, "trend_frac": 0.8, "trend_slope": 0.03, "neg_vol_60": -0.22,
             "log_turnover_20": 20.7, "vol_conf": 1.1, "ret_5d": 0.01, "rsi14": 58.0},
        z={f: v for f, v in zip(["mom_12_1", "mom_6_1", "trend", "low_vol", "liquidity", "vol_conf", "overheat"],
                                [1.2, 0.4, 0.9, 0.1, 1.5, 0.2, -0.3])},
        contributions={"mom_12_1": 0.3, "mom_6_1": 0.04, "trend": 0.18, "low_vol": 0.015,
                       "liquidity": 0.15, "vol_conf": 0.02, "overheat": 0.03},
    )


def test_build_table_allows_its_own_numbers():
    table, allowed = build_table(_fake_score())
    assert "Buy Rank: 78/100" in table
    assert offending_numbers(table, allowed) == []


def test_template_explanation_is_grounded():
    s = _fake_score()
    table, allowed = build_table(s)
    t = template_explanation(s)
    assert len(t["bullets"]) == 3
    for b in [*t["bullets"], t["watch_out"]]:
        assert offending_numbers(b, allowed) == [], b
