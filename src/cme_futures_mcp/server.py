"""FastMCP stdio server for algo-trading futures data.

Thin tools that delegate to the pure `data_access` layer and translate domain
errors into helpful messages. Run:
  uv run --project <repo> python -m src.mcp_server.server
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from . import data_access as da

mcp = FastMCP("algotrading-data")


@mcp.tool()
def ping() -> str:
    """Health check. Returns 'pong' if the server is wired correctly."""
    return "pong"


@mcp.tool()
def list_instruments() -> list[dict[str, Any]]:
    """List available futures instruments.

    For each symbol reports whether contract specs exist and, per data source,
    the timeframes and date range. Sources: 'databento-badj' (back-adjusted
    continuous, DAILY only) and 'yahoo-unadjusted' (stitched front-month, NOT
    adjusted). Use this first to discover what to request.
    """
    return da.list_instruments()


@mcp.tool()
def get_ohlcv(
    symbol: str,
    timeframe: str = "1d",
    start: str | None = None,
    end: str | None = None,
    n_bars: int | None = None,
) -> dict[str, Any]:
    """Return OHLCV bars for a futures instrument.

    Daily requests for a back-adjusted symbol are served from 'databento-badj'
    (adjusted=true); everything else from 'yahoo-unadjusted' (adjusted=false).
    The response always labels 'source' and 'adjusted'. Filter with ISO dates
    (start/end) or n_bars (most recent N). Output is capped (most recent rows);
    check 'truncated' and 'n_total'.

    Args:
        symbol: Root symbol, e.g. "NQ", "MNQ", "ES".
        timeframe: One of 1m, 5m, 15m, 1h, 1d (availability varies by symbol).
        start: Inclusive ISO date/datetime UTC, e.g. "2026-01-01".
        end: Inclusive ISO date/datetime UTC.
        n_bars: Return only the most recent N bars.
    """
    try:
        return da.get_ohlcv(symbol, timeframe, start, end, n_bars)
    except (da.InstrumentError, da.TimeframeError) as e:
        return {"error": str(e)}
    except (ValueError, TypeError, ArithmeticError) as e:
        return {"error": f"Request error: {type(e).__name__}: {e}"}


@mcp.tool()
def get_contract_specs(symbol: str) -> dict[str, Any]:
    """Return contract specifications for a registered futures symbol.

    Includes tick_size, point_value, tick_value (USD/tick), exchange,
    commission_per_side, initial_margin_day, currency and RTH session hours (ET).

    Args:
        symbol: Root symbol, case-insensitive, e.g. "MNQ", "es".
    """
    try:
        return da.get_contract_specs(symbol)
    except da.InstrumentError as e:
        return {"error": str(e)}
    except (ValueError, TypeError) as e:
        return {"error": f"Request error: {type(e).__name__}: {e}"}


@mcp.tool()
def get_summary_stats(
    symbol: str,
    timeframe: str = "1d",
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    """Summary statistics for a series without returning the bars.

    Returns period return, annualized volatility (approximate), max/min close,
    max drawdown and bar count. Cheaper than get_ohlcv when you only need a
    high-level read. Labels 'source' and 'adjusted'.

    Args:
        symbol: Root symbol, e.g. "NQ".
        timeframe: One of 1m, 5m, 15m, 1h, 1d.
        start: Inclusive ISO date/datetime UTC.
        end: Inclusive ISO date/datetime UTC.
    """
    try:
        return da.get_summary_stats(symbol, timeframe, start, end)
    except (da.InstrumentError, da.TimeframeError) as e:
        return {"error": str(e)}
    except (ValueError, TypeError, ArithmeticError) as e:
        return {"error": f"Request error: {type(e).__name__}: {e}"}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
