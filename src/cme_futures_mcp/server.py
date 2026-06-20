"""FastMCP stdio server for algo-trading futures data.

Thin tools that delegate to the pure `data_access` layer. Domain and unexpected
errors are surfaced via ToolError (the protocol marks the result isError=true);
unexpected errors are logged to stderr and never leak a stack trace to the
client. Run:
  uv run --project <repo> python -m src.mcp_server.server
"""
from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from . import data_access as da

logger = logging.getLogger(__name__)

mcp = FastMCP("algotrading-data")

# Every tool here is a pure read: no state change, safe to retry.
_READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)


def _call(fn: Callable[..., Any], *args: Any) -> Any:
    """Run a data_access call, mapping errors to ToolError (isError=true).

    Expected domain/validation errors keep their message; anything unexpected is
    logged with traceback to stderr and returned as a generic message so no
    stack trace or internal path reaches the client.
    """
    try:
        return fn(*args)
    except (da.InstrumentError, da.TimeframeError, ValueError) as e:
        raise ToolError(str(e)) from e
    except Exception as e:  # noqa: BLE001 - last-resort guard for the transport
        logger.exception("tool %s failed", getattr(fn, "__name__", "?"))
        raise ToolError(f"internal error: {type(e).__name__}") from e


@mcp.tool(annotations=_READ_ONLY)
def ping() -> str:
    """Health check. Returns 'pong' if the server is wired correctly."""
    return "pong"


@mcp.tool(annotations=_READ_ONLY)
def list_instruments() -> list[dict[str, Any]]:
    """List available futures instruments.

    For each symbol reports whether contract specs exist and, per data source,
    the timeframes and date range. Sources: 'databento-badj' (back-adjusted
    continuous, DAILY only) and 'yahoo-unadjusted' (stitched front-month, NOT
    adjusted). Use this first to discover what to request.
    """
    return _call(da.list_instruments)


@mcp.tool(annotations=_READ_ONLY)
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
    return _call(da.get_ohlcv, symbol, timeframe, start, end, n_bars)


@mcp.tool(annotations=_READ_ONLY)
def get_contract_specs(symbol: str) -> dict[str, Any]:
    """Return contract specifications for a registered futures symbol.

    Includes tick_size, point_value, tick_value (USD/tick), exchange,
    commission_per_side, initial_margin_day, currency and RTH session hours (ET).

    Args:
        symbol: Root symbol, case-insensitive, e.g. "MNQ", "es".
    """
    return _call(da.get_contract_specs, symbol)


@mcp.tool(annotations=_READ_ONLY)
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
    return _call(da.get_summary_stats, symbol, timeframe, start, end)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("starting algotrading-data MCP server (stdio)")
    mcp.run()


if __name__ == "__main__":
    main()
