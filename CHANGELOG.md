# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project adheres to
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-06-20
### Added
- Initial standalone extraction from the research monorepo.
- MCP stdio server (`cme-futures`) with 5 tools: `ping`, `list_instruments`,
  `get_ohlcv`, `get_contract_specs`, `get_summary_stats`.
- Routing across two datasets: `databento-badj` (back-adjusted continuous, daily)
  and `yahoo-unadjusted` (front-month, intraday).
- `CME_FUTURES_DATA_DIR` environment override for BYOD / remote deployment.
- Synthetic-data test suite and GitHub Actions CI (Python 3.11 / 3.12).

### Security
- Symbol/timeframe whitelisting prevents path traversal.
- Read-only path resolution: lookups never create directories.
- Domain and arithmetic errors are returned as `{"error": ...}`, never raised to
  the transport.
