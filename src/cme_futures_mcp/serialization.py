"""Compact, token-efficient serialization of OHLCV data for MCP responses.

Bars use short keys (t,o,h,l,c,v) and ISO-8601 UTC timestamps without
microseconds. Prices are rounded to the contract tick size when known.
"""
from __future__ import annotations

from typing import Any

import pandas as pd


def fmt_ts(ts: pd.Timestamp) -> str:
    """ISO-8601 UTC, second precision, no microseconds (e.g. 2026-06-09T00:00:00Z)."""
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _round_price(x: float, tick_size: float | None) -> float:
    """Round to the tick's decimal precision if known, else to 4 decimals.

    Uses the tick's own decimal places (e.g. 0.25 -> 2 decimals) instead of
    floor(log10(tick)), which under-rounds quarter/half ticks (0.25 -> 1 decimal
    turns 15000.25 into 15000.2). NaN -> None handled by caller.
    """
    if tick_size and tick_size > 0:
        s = f"{tick_size:.10f}".rstrip("0")
        decimals = len(s.split(".")[1]) if "." in s else 0
        return round(float(x), decimals)
    return round(float(x), 4)


def df_to_bars(
    df: pd.DataFrame, max_rows: int, tick_size: float | None = None
) -> tuple[list[dict[str, Any]], bool, int]:
    """Convert an OHLCV DataFrame to compact records.

    Returns (bars, truncated, n_total). If len(df) > max_rows, keeps the most
    recent max_rows rows and sets truncated=True. n_total is the pre-cap count.
    """
    n_total = len(df)
    truncated = n_total > max_rows
    if truncated:
        df = df.iloc[-max_rows:]

    bars: list[dict[str, Any]] = []
    for ts, row in df.iterrows():
        def _px(col: str) -> float | None:
            val = row[col]
            return None if pd.isna(val) else _round_price(val, tick_size)

        bars.append(
            {
                "t": fmt_ts(ts),
                "o": _px("open"),
                "h": _px("high"),
                "l": _px("low"),
                "c": _px("close"),
                "v": int(row["volume"]) if pd.notna(row["volume"]) else 0,
            }
        )
    return bars, truncated, n_total
