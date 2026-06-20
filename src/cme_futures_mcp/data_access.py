"""Pure data-access layer for the futures MCP server (no MCP imports).

Routes requests across two on-disk datasets and the contract registry, returns
plain serializable dicts, and raises domain errors that the server translates
into helpful messages. Unit-testable without any MCP transport.

Datasets (universes do NOT fully overlap):
  - databento-badj: data/futures_daily_badj/{SYM}/1d.parquet  (back-adjusted,
    continuous, DAILY ONLY). index 'date' UTC; extra cols contract, n_rolls.
  - yahoo-unadjusted: data/futures/{SYM}/{tf}.parquet  (stitched front-month,
    NOT adjusted). index 'timestamp' UTC.
  - specs: src.execution.contracts registry.
"""
from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from . import contracts, paths
from .serialization import df_to_bars, fmt_ts
from .storage import get_parquet_path_ro, load_ohlcv

logger = logging.getLogger(__name__)

# Bumped when the shape of any tool response changes (clients can pin to it).
SCHEMA_VERSION = "1"

SOURCE_BADJ = "databento-badj"
SOURCE_YAHOO = "yahoo-unadjusted"

_INDEX_CANDIDATES = ("timestamp", "date", "ts_event")
# Approximate bars-per-year used to annualize volatility. Intraday futures trade
# ~23h/day; these are deliberate approximations and are reported as such.
PERIODS_PER_YEAR: dict[str, float] = {
    "1m": 252 * 1380,
    "5m": 252 * 276,
    "15m": 252 * 92,
    "30m": 252 * 46,
    "1h": 252 * 23,
    "4h": 252 * 6,
    "1d": 252,
    "1w": 52,
}


class InstrumentError(ValueError):
    """Symbol is not known in any dataset."""


class TimeframeError(ValueError):
    """Symbol exists but the requested timeframe is unavailable."""


# --------------------------------------------------------------------------- #
# Discovery helpers
# --------------------------------------------------------------------------- #
def _badj_symbols() -> list[str]:
    if not paths.BADJ_DIR.exists():
        return []
    return sorted(
        d.name for d in paths.BADJ_DIR.iterdir()
        if d.is_dir() and (d / "1d.parquet").exists()
    )


def _yahoo_symbols() -> list[str]:
    if not paths.FUTURES_DIR.exists():
        return []
    return sorted(
        d.name for d in paths.FUTURES_DIR.iterdir()
        if d.is_dir() and any(d.glob("*.parquet"))
    )


def _yahoo_timeframes(symbol: str) -> list[str]:
    d = paths.FUTURES_DIR / symbol
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.parquet"))


def _has_badj(symbol: str) -> bool:
    return (paths.BADJ_DIR / symbol / "1d.parquet").exists()


def _tick_size(symbol: str) -> float | None:
    try:
        return contracts.get(symbol).tick_size
    except KeyError:
        return None


def _parquet_span(path) -> tuple[int, str | None, str | None]:
    """Cheaply read (n_rows, start_iso, end_iso) reading only the index column."""
    pf = pq.ParquetFile(path)
    n = pf.metadata.num_rows
    names = pf.schema_arrow.names
    idx_col = next((c for c in _INDEX_CANDIDATES if c in names), None)
    if idx_col is None or n == 0:
        return n, None, None
    col = pf.read(columns=[idx_col]).column(0).to_pandas()
    return n, fmt_ts(col.min()), fmt_ts(col.max())


# --------------------------------------------------------------------------- #
# Core series loader (shared routing)
# --------------------------------------------------------------------------- #
def _load_series(symbol: str, timeframe: str) -> tuple[pd.DataFrame, str, bool]:
    """Return (df, source, adjusted). Raises InstrumentError/TimeframeError.

    Routing: daily for a back-adjusted symbol -> databento-badj (preferred,
    adjusted). Everything else -> yahoo-unadjusted.
    """
    sym = symbol.upper().strip()

    # Validate before touching the filesystem. The symbol whitelist is the real
    # guard against path traversal (e.g. "../evil" is never a known symbol);
    # the timeframe check rejects arbitrary strings before any path is built.
    if timeframe not in PERIODS_PER_YEAR:
        logger.warning("rejected invalid timeframe %r", timeframe)
        raise TimeframeError(
            f"Unknown timeframe '{timeframe}'. Valid: {sorted(PERIODS_PER_YEAR)}"
        )
    if sym not in (
        set(_badj_symbols()) | set(_yahoo_symbols()) | set(contracts.all_symbols())
    ):
        logger.warning("rejected unknown symbol %r", symbol)
        raise InstrumentError(
            f"Unknown instrument '{symbol}'. "
            "Call list_instruments() to see available symbols."
        )

    if timeframe == "1d" and _has_badj(sym):
        path = paths.BADJ_DIR / sym / "1d.parquet"
        df = pd.read_parquet(path, engine="pyarrow")
        df = df[["open", "high", "low", "close", "volume"]].sort_index()
        return df, SOURCE_BADJ, True

    path = get_parquet_path_ro(paths.DATA_DIR, "futures", sym, timeframe)
    df = load_ohlcv(path)
    if df is not None:
        df = df[["open", "high", "low", "close", "volume"]].sort_index()
        return df, SOURCE_YAHOO, False

    # Not found: build a helpful error.
    yahoo_tfs = _yahoo_timeframes(sym)
    has_badj = _has_badj(sym)
    if not yahoo_tfs and not has_badj:
        raise InstrumentError(
            f"Unknown instrument '{symbol}'. "
            "Call list_instruments() to see available symbols."
        )
    available = list(yahoo_tfs)
    if has_badj and "1d" not in available:
        available.append("1d (databento-badj)")
    raise TimeframeError(
        f"{sym}: no data for timeframe '{timeframe}'. Available: {sorted(available)}"
    )


# --------------------------------------------------------------------------- #
# Public API (one per MCP tool)
# --------------------------------------------------------------------------- #
def list_instruments() -> list[dict[str, Any]]:
    """Union of all datasets. Per symbol: has_specs + one entry per source."""
    symbols = sorted(
        set(contracts.all_symbols()) | set(_yahoo_symbols()) | set(_badj_symbols())
    )
    out: list[dict[str, Any]] = []
    for sym in symbols:
        sources: list[dict[str, Any]] = []

        if _has_badj(sym):
            n, start, end = _parquet_span(paths.BADJ_DIR / sym / "1d.parquet")
            sources.append({
                "source": SOURCE_BADJ,
                "adjusted": True,
                "timeframes": ["1d"],
                "start": start,
                "end": end,
                "n_bars": n,
            })

        ytfs = _yahoo_timeframes(sym)
        if ytfs:
            # Report span for a representative timeframe (prefer 1d, then 1h).
            rep = "1d" if "1d" in ytfs else ("1h" if "1h" in ytfs else ytfs[0])
            n, start, end = _parquet_span(paths.FUTURES_DIR / sym / f"{rep}.parquet")
            sources.append({
                "source": SOURCE_YAHOO,
                "adjusted": False,
                "timeframes": ytfs,
                "span_timeframe": rep,
                "start": start,
                "end": end,
                "n_bars": n,
            })

        out.append({
            "symbol": sym,
            "has_specs": sym in set(contracts.all_symbols()),
            "sources": sources,
        })
    return out


def get_ohlcv(
    symbol: str,
    timeframe: str = "1d",
    start: str | None = None,
    end: str | None = None,
    n_bars: int | None = None,
    max_rows: int = 1000,
) -> dict[str, Any]:
    """OHLCV bars with explicit source/adjusted labels and a row cap."""
    sym = symbol.upper().strip()
    if n_bars is not None and n_bars <= 0:
        raise ValueError(f"n_bars must be a positive integer, got {n_bars}")
    df, source, adjusted = _load_series(sym, timeframe)

    if start is not None:
        df = df[df.index >= pd.Timestamp(start, tz="UTC")]
    if end is not None:
        df = df[df.index <= pd.Timestamp(end, tz="UTC")]
    if n_bars is not None:
        df = df.iloc[-n_bars:]

    bars, truncated, n_total = df_to_bars(df, max_rows, _tick_size(sym))
    return {
        "schema_version": SCHEMA_VERSION,
        "symbol": sym,
        "timeframe": timeframe,
        "source": source,
        "adjusted": adjusted,
        "n_returned": len(bars),
        "n_total": n_total,
        "truncated": truncated,
        "start": bars[0]["t"] if bars else None,
        "end": bars[-1]["t"] if bars else None,
        "bars": bars,
    }


def get_summary_stats(
    symbol: str,
    timeframe: str = "1d",
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    """Summary statistics over a series without returning the bars.

    Volatility is annualized with an approximate bars-per-year factor (declared
    in PERIODS_PER_YEAR; intraday futures are ~23h/day, treat as approximate).
    """
    sym = symbol.upper().strip()
    df, source, adjusted = _load_series(sym, timeframe)

    if start is not None:
        df = df[df.index >= pd.Timestamp(start, tz="UTC")]
    if end is not None:
        df = df[df.index <= pd.Timestamp(end, tz="UTC")]

    n = len(df)
    if n == 0:
        return {
            "schema_version": SCHEMA_VERSION,
            "symbol": sym, "timeframe": timeframe, "source": source,
            "adjusted": adjusted, "n_bars": 0, "start": None, "end": None,
            "note": "No bars in the requested range.",
        }

    close = df["close"].astype(float)
    # pct_change yields +/-inf when the series starts at or crosses zero
    # (back-adjusted history); drop those before computing volatility so a single
    # bad bar does not poison the annualized vol with NaN/inf.
    rets = close.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    ppy = PERIODS_PER_YEAR.get(timeframe)
    ann_vol = (
        float(rets.std() * (ppy ** 0.5) * 100)
        if ppy is not None and len(rets) > 1 else None
    )
    if ann_vol is not None and not math.isfinite(ann_vol):
        ann_vol = None
    # Back-adjusted continuous series can have prices <= 0 in deep history (the
    # roll adjustment can drag the panel below zero). Guard both the drawdown
    # division and the period-return ratio against a zero/negative base.
    running_max = close.cummax()
    valid = running_max > 0
    if valid.any():
        dd = (close[valid] - running_max[valid]) / running_max[valid]
        max_dd = round(float(dd.min() * 100), 2)  # negative magnitude
    else:
        max_dd = None

    first_close = float(close.iloc[0])
    last_close = float(close.iloc[-1])
    period_return = (
        round((last_close / first_close - 1) * 100, 2) if first_close != 0 else None
    )

    out = {
        "schema_version": SCHEMA_VERSION,
        "symbol": sym,
        "timeframe": timeframe,
        "source": source,
        "adjusted": adjusted,
        "n_bars": n,
        "start": fmt_ts(df.index.min()),
        "end": fmt_ts(df.index.max()),
        "first_close": round(first_close, 4),
        "last_close": round(last_close, 4),
        "period_return_pct": period_return,
        "annualized_vol_pct": round(ann_vol, 2) if ann_vol is not None else None,
        "vol_annualization_note": "approximate (bars/year factor; intraday ~23h/day)",
        "max_close": round(float(close.max()), 4),
        "min_close": round(float(close.min()), 4),
        "max_drawdown_pct": max_dd,
    }
    if first_close <= 0:
        out["period_return_note"] = (
            "initial close <= 0 (back-adjusted); return not meaningful"
        )
    return out


def get_contract_specs(symbol: str) -> dict[str, Any]:
    """Contract specification from the registry."""
    try:
        spec = contracts.get(symbol)
    except KeyError as e:
        raise InstrumentError(str(e)) from e
    return {
        "schema_version": SCHEMA_VERSION,
        "symbol": spec.symbol,
        "exchange": spec.exchange,
        "tick_size": spec.tick_size,
        "point_value": spec.point_value,
        "tick_value": spec.tick_value,
        "commission_per_side": spec.commission_per_side,
        "initial_margin_day": spec.initial_margin_day,
        "currency": spec.currency,
        "rth_start_et": spec.rth_start_et.strftime("%H:%M"),
        "rth_end_et": spec.rth_end_et.strftime("%H:%M"),
    }
