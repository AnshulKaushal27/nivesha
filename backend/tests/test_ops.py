"""Operations layer: calendar, alert classification, usage costing. No network, no LLM."""

from datetime import date

import pytest

from ops import holidays
from ops.alerts import classify_llm_error
from ops.llm_usage import estimate_cost


class _Status(Exception):
    def __init__(self, msg, status_code):
        super().__init__(msg)
        self.status_code = status_code


def test_fixed_national_holidays_cover_any_year():
    h = holidays.fixed_holidays(2029)
    assert date(2029, 1, 26) in h and date(2029, 8, 15) in h and date(2029, 12, 25) in h


def test_is_trading_day_rules(monkeypatch):
    monkeypatch.setattr(holidays, "_load", lambda: {**holidays.STATIC_HOLIDAYS, **holidays.fixed_holidays(2029)})
    assert not holidays.is_trading_day(date(2026, 9, 19))     # Saturday
    assert not holidays.is_trading_day(date(2026, 10, 2))     # Gandhi Jayanti (static)
    assert not holidays.is_trading_day(date(2029, 1, 26))     # Republic Day, year nobody loaded (fixed fallback)
    assert holidays.is_trading_day(date(2026, 9, 17))          # a plain Thursday
    assert holidays.next_trading_day(date(2026, 10, 1)) == date(2026, 10, 5)   # Fri holiday + weekend → Monday


@pytest.mark.parametrize("exc, kind, severity", [
    (_Status("Insufficient credits", 402), "credits_exhausted", "critical"),
    (_Status("You exceeded your current quota", 429), "credits_exhausted", "critical"),
    (_Status("Incorrect API key provided", 401), "llm_auth_failed", "critical"),
    (_Status("Too many requests", 429), "llm_rate_limited", "warning"),
    (ConnectionError("Connection reset by peer"), "llm_gateway_down", "warning"),
    (ValueError("schema mismatch"), "llm_error", "warning"),
])
def test_llm_error_classification(exc, kind, severity):
    assert classify_llm_error(exc) == (kind, severity)


def test_classification_walks_cause_chain():
    try:
        try:
            raise _Status("Payment required", 402)
        except _Status as inner:
            raise RuntimeError("wrapped") from inner
    except RuntimeError as exc:
        assert classify_llm_error(exc)[0] == "credits_exhausted"


def test_cost_estimate_uses_price_table():
    assert abs(estimate_cost("gpt-4o-mini", 1_000_000, 0) - 0.15) < 1e-9
    assert abs(estimate_cost("gpt-4o-mini", 0, 1_000_000) - 0.60) < 1e-9
    assert estimate_cost("some/unknown-model", 1_000_000, 1_000_000) == 2.0     # fallback 0.5 + 1.5
