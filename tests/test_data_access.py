"""Data-access layer tests against synthetic Parquet data (via the fake_data fixture)."""
from __future__ import annotations

import math

import pandas as pd
import pytest

from cme_futures_mcp import data_access as da


def test_list_instruments_union_and_flags(fake_data):
    by = {x["symbol"]: x for x in da.list_instruments()}
    assert {"NQ", "MNQ", "GC"} <= set(by)
    assert da.SOURCE_BADJ in {s["source"] for s in by["NQ"]["sources"]}
    assert by["MNQ"]["has_specs"] is True          # registry spec, yahoo data
    assert by["GC"]["has_specs"] is False          # data but no registry spec


def test_get_ohlcv_badj_routing(fake_data):
    r = da.get_ohlcv("NQ", "1d", n_bars=5)
    assert r["source"] == da.SOURCE_BADJ
    assert r["adjusted"] is True
    assert r["n_returned"] == 5
    assert set(r["bars"][0]) == {"t", "o", "h", "l", "c", "v"}


def test_get_ohlcv_yahoo_routing_case_insensitive(fake_data):
    r = da.get_ohlcv("mnq", "1h", n_bars=3)
    assert r["source"] == da.SOURCE_YAHOO
    assert r["adjusted"] is False
    assert r["symbol"] == "MNQ"


def test_get_ohlcv_truncation(fake_data):
    r = da.get_ohlcv("NQ", "1d", max_rows=3)
    assert r["n_returned"] == 3
    assert r["truncated"] is True
    assert r["n_total"] > 3


def test_get_ohlcv_unknown_instrument(fake_data):
    with pytest.raises(da.InstrumentError):
        da.get_ohlcv("ZZZZ", "1d")


def test_get_ohlcv_badj_only_intraday_raises(fake_data):
    with pytest.raises(da.TimeframeError):
        da.get_ohlcv("GC", "1h")


def test_get_ohlcv_path_traversal_blocked(fake_data):
    before = set(fake_data.joinpath("futures").iterdir())
    with pytest.raises(da.InstrumentError):
        da.get_ohlcv("../evil", "1d")
    assert set(fake_data.joinpath("futures").iterdir()) == before  # no dirs created


def test_get_ohlcv_invalid_timeframe_blocked(fake_data):
    with pytest.raises(da.TimeframeError):
        da.get_ohlcv("NQ", "999x")


def test_get_ohlcv_nbars_nonpositive_raises(fake_data):
    with pytest.raises(ValueError):
        da.get_ohlcv("NQ", "1d", n_bars=0)


def test_get_contract_specs_case_insensitive(fake_data):
    s = da.get_contract_specs("mNq")
    assert s["symbol"] == "MNQ"
    assert s["tick_size"] == 0.25
    assert s["tick_value"] == 0.5
    assert s["exchange"] == "CME"


def test_get_contract_specs_unknown_raises(fake_data):
    with pytest.raises(da.InstrumentError):
        da.get_contract_specs("GC")  # has data but no registered spec


def test_get_summary_stats_basic(fake_data):
    s = da.get_summary_stats("NQ", "1d")
    assert s["n_bars"] == 40
    assert s["period_return_pct"] is not None
    assert s["source"] == da.SOURCE_BADJ


def test_summary_stats_zero_initial_close_no_crash(monkeypatch):
    idx = pd.date_range("2026-01-01", periods=3, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "open": [0.0, 50.0, 75.0],
            "high": [0.0, 50.0, 75.0],
            "low": [0.0, 50.0, 75.0],
            "close": [0.0, 50.0, 75.0],
            "volume": [1, 1, 1],
        },
        index=idx,
    )
    monkeypatch.setattr(da, "_load_series", lambda s, t: (df, da.SOURCE_BADJ, True))
    s = da.get_summary_stats("FAKE", "1d")
    assert s["period_return_pct"] is None
    assert "period_return_note" in s
    for v in s.values():
        if isinstance(v, float):
            assert math.isfinite(v), f"non-finite value leaked: {v}"
