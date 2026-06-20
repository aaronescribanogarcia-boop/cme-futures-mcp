"""Synthetic-data fixtures so the suite runs without the real Parquet datasets.

The fixture writes UTC-aware Parquet files into a tmp dir and patches the
``paths`` module so the data-access layer reads from there. No proprietary data
is required to run the tests (important for CI).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _daily(n: int, start_price: float, index_name: str, extra: dict | None = None):
    idx = pd.date_range("2026-01-02", periods=n, freq="D", tz="UTC")
    idx.name = index_name
    close = start_price + np.arange(n, dtype=float) * 5.0
    data = {
        "open": close,
        "high": close + 10.0,
        "low": close - 10.0,
        "close": close,
        "volume": (np.arange(n) + 1000).astype("int64"),
    }
    if extra:
        data.update(extra)
    return pd.DataFrame(data, index=idx)


def _intraday(n: int, freq: str, index_name: str = "timestamp"):
    idx = pd.date_range("2026-01-02", periods=n, freq=freq, tz="UTC")
    idx.name = index_name
    close = 15000.0 + np.arange(n, dtype=float)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 2.0,
            "low": close - 2.0,
            "close": close,
            "volume": (np.arange(n) + 10).astype("int64"),
        },
        index=idx,
    )


@pytest.fixture
def fake_data(tmp_path, monkeypatch):
    from cme_futures_mcp import paths

    badj = tmp_path / "futures_daily_badj"
    fut = tmp_path / "futures"

    n = 40
    # Back-adjusted daily: NQ (has a registry spec), GC (data but NO spec).
    for sym, price in (("NQ", 15000.0), ("GC", 2000.0)):
        p = badj / sym / "1d.parquet"
        p.parent.mkdir(parents=True, exist_ok=True)
        _daily(
            n, price, "date",
            extra={"contract": [f"{sym}H26"] * n, "n_rolls": [0] * n},
        ).to_parquet(p, engine="pyarrow")

    # Yahoo front-month intraday: MNQ at 1h and 1m.
    for tf, freq in (("1h", "h"), ("1m", "min")):
        p = fut / "MNQ" / f"{tf}.parquet"
        p.parent.mkdir(parents=True, exist_ok=True)
        _intraday(n, freq).to_parquet(p, engine="pyarrow")

    monkeypatch.setattr(paths, "DATA_DIR", tmp_path)
    monkeypatch.setattr(paths, "BADJ_DIR", badj)
    monkeypatch.setattr(paths, "FUTURES_DIR", fut)
    return tmp_path
