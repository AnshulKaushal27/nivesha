import os
import sys
from pathlib import Path

# Tests run against an isolated SQLite file and never touch a real .env database.
os.environ.setdefault("DATABASE_URL", "sqlite:///./_test.db")
os.environ.setdefault("AICREDITS_API_KEY", "")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np   # noqa: E402
import pandas as pd  # noqa: E402
import pytest        # noqa: E402


@pytest.fixture(scope="session")
def synthetic_bars() -> pd.DataFrame:
    """
    40 tickers × 420 business days of geometric random walks. Half the tickers
    get a positive drift so momentum carries real signal in the tests.
    """
    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2024-01-01", periods=420)
    frames = []
    for i in range(40):
        drift = 0.0008 if i % 2 == 0 else -0.0003
        vol = 0.012 + 0.01 * (i % 5) / 4
        rets = rng.normal(drift, vol, len(dates))
        close = 100 * (1 + i / 10) * np.exp(np.cumsum(rets))
        volume = rng.lognormal(mean=13.5, sigma=0.4, size=len(dates))   # ≈ 7e5 shares
        frames.append(pd.DataFrame({
            "ticker": f"T{i:02d}.NS", "date": dates,
            "open": close, "high": close * 1.01, "low": close * 0.99, "close": close, "volume": volume,
        }))
    return pd.concat(frames, ignore_index=True)
