"""
Number audit: every number in model output must exist in the input it was given.

This is the guard rail that turns "the model was told not to invent numbers"
into something checked in code. Used by the rank explainer today and by the
Arena thesis checker later.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Iterable

_NUM_RE = re.compile(r"(?<![\w.])[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])[-+]?\d+(?:\.\d+)?")

# Numbers that are part of factor names or common phrasing, never a data claim.
STRUCTURAL: frozenset[str] = frozenset({
    "1", "2", "3", "5", "6", "10", "12", "14", "20", "21", "30", "50", "52", "60",
    "100", "126", "200", "252",
})


def normalize(token: str) -> str:
    """'1,234.50' → '1234.5'; '-0.30' → '0.3'; '18%' handled by the caller."""
    t = token.replace(",", "").lstrip("+-")
    try:
        d = Decimal(t)
    except InvalidOperation:
        return t
    if d == d.to_integral_value():
        return str(int(d))
    return format(d.normalize(), "f")


def numbers_in(text: str) -> list[str]:
    return [normalize(m.group(0)) for m in _NUM_RE.finditer(text or "")]


def allowed_from(values: Iterable[float | int | str | None]) -> set[str]:
    """
    Build the allowed set from input values, including their rounded forms so
    "18.4%" written as "18%" still passes.
    """
    out: set[str] = set()
    for v in values:
        if v is None:
            continue
        if isinstance(v, str):
            out.update(numbers_in(v))
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f != f:                       # NaN
            continue
        for nd in (0, 1, 2, 3, 4):
            out.add(normalize(f"{abs(f):.{nd}f}"))
            out.add(normalize(f"{f:.{nd}f}"))
    return out


def offending_numbers(text: str, allowed: set[str]) -> list[str]:
    """Numbers in `text` that are neither allowed nor structural."""
    return [n for n in numbers_in(text) if n not in allowed and n not in STRUCTURAL]
