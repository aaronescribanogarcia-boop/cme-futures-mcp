"""Pure serialization tests (no filesystem)."""
from __future__ import annotations

import pandas as pd

from cme_futures_mcp.serialization import _round_price, df_to_bars, fmt_ts


def test_fmt_ts_tz_aware():
    assert fmt_ts(pd.Timestamp("2026-06-09T00:00:00Z")) == "2026-06-09T00:00:00Z"


def test_fmt_ts_tz_naive_localizes_utc():
    assert fmt_ts(pd.Timestamp("2026-06-09 12:00:00")) == "2026-06-09T12:00:00Z"


def test_round_price_with_tick():
    assert _round_price(15000.123, 0.25) == 15000.12


def test_round_price_preserves_quarter_tick():
    # Regression: tick 0.25 must keep 2 decimals (15000.25 must NOT become 15000.2).
    assert _round_price(15000.25, 0.25) == 15000.25
    assert _round_price(15000.75, 0.25) == 15000.75


def test_round_price_without_tick():
    assert _round_price(1.23456, None) == 1.2346


def _df(values: dict, n: int):
    idx = pd.date_range("2026-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame(values, index=idx)


def test_df_to_bars_no_truncation():
    df = _df({c: [1, 2, 3] for c in ("open", "high", "low", "close", "volume")}, 3)
    bars, truncated, n_total = df_to_bars(df, 10, None)
    assert n_total == 3
    assert truncated is False
    assert len(bars) == 3
    assert bars[0]["v"] == 1


def test_df_to_bars_truncation_keeps_most_recent():
    df = _df({c: [1, 2, 3, 4, 5] for c in ("open", "high", "low", "close", "volume")}, 5)
    bars, truncated, n_total = df_to_bars(df, 2, None)
    assert truncated is True
    assert n_total == 5
    assert len(bars) == 2
    assert bars[-1]["c"] == 5  # most recent retained


def test_df_to_bars_nan_volume_becomes_zero():
    df = _df(
        {"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [float("nan")]},
        1,
    )
    bars, _, _ = df_to_bars(df, 10, None)
    assert bars[0]["v"] == 0


def test_df_to_bars_nan_ohlc_becomes_none():
    df = _df(
        {"open": [float("nan")], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [5]},
        1,
    )
    bars, _, _ = df_to_bars(df, 10, None)
    assert bars[0]["o"] is None
    assert bars[0]["h"] == 1.0


def test_df_to_bars_empty():
    df = pd.DataFrame(
        {c: [] for c in ("open", "high", "low", "close", "volume")},
        index=pd.DatetimeIndex([], tz="UTC"),
    )
    bars, truncated, n_total = df_to_bars(df, 10, None)
    assert bars == []
    assert truncated is False
    assert n_total == 0
