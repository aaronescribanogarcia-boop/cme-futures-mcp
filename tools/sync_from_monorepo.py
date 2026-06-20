#!/usr/bin/env python3
"""Regenerate the synced modules of cme-futures-mcp from the research monorepo.

The monorepo (algo-trading) is the SOURCE OF TRUTH for the MCP data logic. This
script copies the shared modules and rewrites their absolute ``src.*`` imports
into package-relative imports, strips the proprietary contracts docstring, and
writes a minimal read-only storage shim.

Run before every release. Never hand-edit the synced files (they will be
overwritten); edit the logic in the monorepo instead.

Synced (copied + transformed): server.py, data_access.py, serialization.py,
contracts.py. storage.py is written from a fixed minimal template (read-only
helpers only; ingestion/writing stays in the monorepo). NOT synced (native to
this repo): paths.py, __init__.py, pyproject.toml, tests, CI.

Usage:
    python tools/sync_from_monorepo.py [--monorepo PATH]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Assume the research monorepo sits next to this repo (../algo-trading). Override
# with --monorepo. Kept relative so no developer-specific absolute path is committed.
DEFAULT_MONOREPO = Path(__file__).resolve().parents[2] / "algo-trading"
PKG = "cme_futures_mcp"

IMPORT_REWRITES = [
    ("from src.mcp_server import data_access as da", "from . import data_access as da"),
    ("from src.data.storage import", "from .storage import"),
    ("from src.execution import contracts", "from . import contracts"),
    ("from src.mcp_server import paths", "from . import paths"),
    ("from src.mcp_server.serialization import", "from .serialization import"),
]

STORAGE_TEMPLATE = '''"""Read-only Parquet helpers (minimal shim for the MCP server).

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
'''

CONTRACTS_DOCSTRING = '''"""Contract specifications for CME / CBOT / NYMEX futures.

Static tick size, point value and session hours per root symbol. All values are
public exchange specifications. Margins are conservative day-trade defaults and
can be overridden by the caller via register().
"""'''

# Neutralize proprietary broker / prop-firm references in inline comments. The
# catch-all entries at the end guarantee no sensitive term survives even if the
# upstream wording changes.
TERM_REPLACEMENTS = [
    ("(prop firm typical)", "(typical)"),
    (" negotiated via Tradovate", ""),
    ("Topstep 50K NQ ~$1-3K", "NQ ~$1-3K intraday"),
    ("prop firms", "day-trade brokers"),
    ("prop firm", "day-trade"),
    ("Tradovate", "a broker"),
    ("Topstep", "a broker"),
    ("Apex", "CME"),
]


def rewrite_imports(text: str) -> str:
    for src, dst in IMPORT_REWRITES:
        text = text.replace(src, dst)
    return text


def sync_contracts(src_text: str) -> str:
    """Neutralize the module docstring and proprietary broker terms in comments."""
    m = re.match(r'""".*?"""', src_text, re.DOTALL)
    if not m:
        raise SystemExit("contracts.py: module docstring not found")
    text = CONTRACTS_DOCSTRING + src_text[m.end():]
    for old, new in TERM_REPLACEMENTS:
        text = text.replace(old, new)
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--monorepo", type=Path, default=DEFAULT_MONOREPO)
    args = ap.parse_args()
    mono: Path = args.monorepo
    if not mono.exists():
        raise SystemExit(f"monorepo not found: {mono}")

    pkg_dir = Path(__file__).resolve().parents[1] / "src" / PKG
    pkg_dir.mkdir(parents=True, exist_ok=True)

    (pkg_dir / "server.py").write_text(
        rewrite_imports((mono / "src/mcp_server/server.py").read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    (pkg_dir / "data_access.py").write_text(
        rewrite_imports((mono / "src/mcp_server/data_access.py").read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    (pkg_dir / "serialization.py").write_text(
        rewrite_imports((mono / "src/mcp_server/serialization.py").read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    (pkg_dir / "contracts.py").write_text(
        sync_contracts((mono / "src/execution/contracts.py").read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    (pkg_dir / "storage.py").write_text(STORAGE_TEMPLATE, encoding="utf-8")

    # Guard: no absolute src.* imports may leak into the distributable package.
    for f in ("server.py", "data_access.py", "serialization.py", "contracts.py", "storage.py"):
        t = (pkg_dir / f).read_text(encoding="utf-8")
        if re.search(r"\bfrom src\.|\bimport src\b", t):
            raise SystemExit(f"{f}: leaked absolute src.* import after sync")

    # Auto-format the generated package so it passes the lint gate. The import
    # rewrite leaves `from . import x` lines unsorted; ruff --fix sorts/combines
    # them deterministically. Best-effort: warn if ruff is unavailable.
    import subprocess

    try:
        subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--fix", "--quiet", str(pkg_dir)],
            check=False,
        )
    except FileNotFoundError:
        print("warning: ruff not found; generated imports may need manual sorting")

    print(f"Synced 5 modules into {pkg_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
