"""Read-only Parquet helpers (minimal shim for the MCP server).

Only the functions the server needs at read time. Writing/ingestion lives in the
research monorepo and is intentionally excluded from this distribution.
"""
from pathlib import Path

import pandas as pd


def get_parquet_path_ro(
    data_dir: Path, asset_type: str, symbol: str, timeframe: str
) -> Path:
    """Resolve the Parquet path WITHOUT creating directories."""
    return data_dir / asset_type / symbol / f"{timeframe}.parquet"


def load_ohlcv(path: Path) -> pd.DataFrame | None:
    """Load an OHLCV DataFrame from Parquet, or None if the file is absent."""
    if not path.exists():
        return None
    return pd.read_parquet(path, engine="pyarrow")
