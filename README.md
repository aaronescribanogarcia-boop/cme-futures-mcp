# cme-futures-mcp

[![CI](https://github.com/aaronescribanogarcia-boop/cme-futures-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/aaronescribanogarcia-boop/cme-futures-mcp/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue)](LICENSE)

MCP server that exposes **normalized CME futures data** to any MCP client
(Claude Code, Cursor, Windsurf). It serves back-adjusted continuous daily bars,
front-month intraday bars, contract specifications and summary statistics through
five tools — with honest source labelling (`adjusted` true/false) so an agent
never silently mixes adjusted and unadjusted series.

## Tools

| Tool | Purpose |
|------|---------|
| `list_instruments()` | Symbols, sources, timeframes and date ranges. Start here. |
| `get_ohlcv(symbol, timeframe='1d', start, end, n_bars)` | OHLCV bars. Labels `source` and `adjusted`. Row-capped (`truncated`/`n_total`). |
| `get_contract_specs(symbol)` | tick_size, point_value, tick_value, exchange, margin, RTH, currency. |
| `get_summary_stats(symbol, timeframe='1d', start, end)` | Return, annualized vol (approx.), max/min, max drawdown — without returning bars. |

`ping()` is a health check.

### Example response (`get_ohlcv("NQ", "1d", n_bars=3)`)

```json
{
  "symbol": "NQ",
  "timeframe": "1d",
  "source": "databento-badj",
  "adjusted": true,
  "schema_version": "1",
  "n_returned": 3,
  "n_total": 3,
  "truncated": false,
  "bars": [
    {"t": "2026-06-17T00:00:00Z", "o": 22014.25, "h": 22180.50, "l": 21975.00, "c": 22156.75, "v": 412233},
    {"t": "2026-06-18T00:00:00Z", "o": 22156.75, "h": 22240.00, "l": 22090.25, "c": 22118.50, "v": 388910},
    {"t": "2026-06-19T00:00:00Z", "o": 22118.50, "h": 22305.75, "l": 22101.00, "c": 22287.25, "v": 401557}
  ]
}
```

Prices are tick-rounded; `bars` use compact keys (`t,o,h,l,c,v`) to keep token
usage low in agent contexts.

## Data sources (honest labelling)

- **`databento-badj`** — back-adjusted, continuous, **daily only**. `adjusted=true`.
- **`yahoo-unadjusted`** — front-month stitched, **not adjusted**. `adjusted=false`.
  Intraday (1m/5m/15m/1h) and daily for the micros.

A daily request for a back-adjusted symbol is served from `databento-badj`
(preferred). Everything else from `yahoo-unadjusted`. Each response states the
source and whether it is adjusted; series are never mixed.

## Installation

```bash
pip install -e .          # or: uvx cme-futures-mcp  (once published)
```

## Data provision (BYOD)

**Data is not bundled with this package.** Point the server at your own Parquet
datasets via the `CME_FUTURES_DATA_DIR` environment variable:

```
$CME_FUTURES_DATA_DIR/
  futures_daily_badj/<SYM>/1d.parquet     # back-adjusted continuous, daily
  futures/<SYM>/<tf>.parquet              # front-month, intraday
```

Each Parquet must have a UTC `DatetimeIndex` and `open, high, low, close, volume`
columns. If `CME_FUTURES_DATA_DIR` is unset, the server falls back to a `data/`
directory next to the package.

## Run

```bash
CME_FUTURES_DATA_DIR=/path/to/data python -m cme_futures_mcp.server
```

## Client registration

The same server block works across MCP clients (it speaks stdio).

**Claude Code** — `.mcp.json` in the repo root:

```json
{
  "mcpServers": {
    "cme-futures": {
      "command": "uvx",
      "args": ["cme-futures-mcp"],
      "env": { "CME_FUTURES_DATA_DIR": "/path/to/data" }
    }
  }
}
```

**Cursor** — `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global): same
`mcpServers` block as above.

**Claude Desktop** — `claude_desktop_config.json` (Settings → Developer → Edit
Config): same `mcpServers` block.

Restart the client and confirm `cme-futures` shows as connected (`/mcp` in
Claude Code).

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest -m "not slow"      # synthetic data; no real datasets required
```

The MCP logic is maintained in a private research monorepo (source of truth) and
synced here with `python tools/sync_from_monorepo.py`. Do not hand-edit the
synced modules (`server.py`, `data_access.py`, `serialization.py`, `contracts.py`,
`storage.py`); they are regenerated on every release.
