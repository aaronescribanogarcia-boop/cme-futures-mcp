"""Server-layer tests: errors surface as ToolError (protocol isError=true)."""
from __future__ import annotations

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from cme_futures_mcp import server as s


def test_ping():
    assert s.ping() == "pong"


def test_tools_have_readonly_annotations():
    # All five tools are pure reads; clients rely on these hints for safe retries.
    ann = s._READ_ONLY
    assert ann.readOnlyHint is True
    assert ann.idempotentHint is True


def test_list_instruments(fake_data):
    out = s.list_instruments()
    assert any(x["symbol"] == "NQ" for x in out)


def test_get_ohlcv_ok(fake_data):
    r = s.get_ohlcv("NQ", "1d", n_bars=3)
    assert r["n_returned"] == 3
    assert r["source"] == s.da.SOURCE_BADJ
    assert r["schema_version"] == "1"


def test_get_ohlcv_unknown_raises_toolerror(fake_data):
    with pytest.raises(ToolError):
        s.get_ohlcv("ZZZZ", "1d")


def test_get_ohlcv_bad_timeframe_raises_toolerror(fake_data):
    with pytest.raises(ToolError):
        s.get_ohlcv("NQ", "999x")


def test_get_ohlcv_nbars_raises_toolerror(fake_data):
    with pytest.raises(ToolError):
        s.get_ohlcv("NQ", "1d", n_bars=-1)


def test_get_contract_specs_ok(fake_data):
    assert s.get_contract_specs("MNQ")["tick_value"] == 0.5


def test_get_contract_specs_unknown_raises_toolerror(fake_data):
    with pytest.raises(ToolError):
        s.get_contract_specs("GC")


def test_get_summary_stats_ok(fake_data):
    r = s.get_summary_stats("NQ", "1d")
    assert r["n_bars"] == 40
    assert r["schema_version"] == "1"
