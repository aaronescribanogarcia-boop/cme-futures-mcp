"""Server-layer tests: tools must return {"error": ...} instead of raising."""
from __future__ import annotations

from cme_futures_mcp import server as s


def test_ping():
    assert s.ping() == "pong"


def test_list_instruments(fake_data):
    out = s.list_instruments()
    assert any(x["symbol"] == "NQ" for x in out)


def test_get_ohlcv_ok(fake_data):
    r = s.get_ohlcv("NQ", "1d", n_bars=3)
    assert r["n_returned"] == 3
    assert r["source"] == s.da.SOURCE_BADJ


def test_get_ohlcv_unknown_returns_error(fake_data):
    assert "error" in s.get_ohlcv("ZZZZ", "1d")


def test_get_ohlcv_bad_timeframe_returns_error(fake_data):
    assert "error" in s.get_ohlcv("NQ", "999x")


def test_get_ohlcv_nbars_returns_error(fake_data):
    assert "error" in s.get_ohlcv("NQ", "1d", n_bars=-1)


def test_get_contract_specs_ok(fake_data):
    assert s.get_contract_specs("MNQ")["tick_value"] == 0.5


def test_get_contract_specs_unknown_returns_error(fake_data):
    assert "error" in s.get_contract_specs("GC")


def test_get_summary_stats_ok(fake_data):
    r = s.get_summary_stats("NQ", "1d")
    assert r["n_bars"] == 40
