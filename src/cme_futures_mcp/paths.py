"""Absolute path resolution with an environment override for deployment.

Layout: ``src/cme_futures_mcp/paths.py`` -> the project root is ``parents[2]``.
Set ``CME_FUTURES_DATA_DIR`` to point the server at a data directory anywhere on
disk. This is required in production / BYOD setups where the Parquet datasets
live outside the installed package.
"""
from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_ROOT: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = Path(
    os.environ.get("CME_FUTURES_DATA_DIR", str(_DEFAULT_ROOT / "data"))
)
FUTURES_DIR: Path = DATA_DIR / "futures"
BADJ_DIR: Path = DATA_DIR / "futures_daily_badj"


def project_root() -> Path:
    return _DEFAULT_ROOT
