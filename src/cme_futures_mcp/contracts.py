"""Contract specifications for CME / CBOT / NYMEX futures.

Static tick size, point value and session hours per root symbol. All values are
public exchange specifications. Margins are conservative day-trade defaults and
can be overridden by the caller via register().
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True)
class ContractSpec:
    """Static specification for a futures contract.

    Attributes:
        symbol: Root symbol as used internally (e.g. "MNQ").
        exchange: Exchange code (e.g. "CME").
        tick_size: Minimum price increment in points.
        point_value: USD value of a 1 point move per contract.
        commission_per_side: Broker commission charged per side per contract in USD.
        initial_margin_day: Day-trade initial margin in USD (typical).
        currency: Settlement currency.
        rth_start_et: Regular Trading Hours start (Eastern Time).
        rth_end_et: Regular Trading Hours end (Eastern Time).
    """

    symbol: str
    exchange: str
    tick_size: float
    point_value: float
    commission_per_side: float
    initial_margin_day: float
    currency: str = "USD"
    rth_start_et: time = time(9, 30)
    rth_end_et: time = time(16, 0)

    @property
    def tick_value(self) -> float:
        """USD value of a 1-tick move per contract."""
        return self.tick_size * self.point_value


# Defaults based on CME micros as of 2026. Commissions reflect typical day-trade
# round-trip rates (~$0.74-1.50 per side for MNQ/MES).
MNQ = ContractSpec(
    symbol="MNQ",
    exchange="CME",
    tick_size=0.25,
    point_value=2.00,
    commission_per_side=0.74,
    initial_margin_day=1760.0,
)

# E-mini Nasdaq-100 (full mini, 10x MNQ). Day-trade margin from day-trade brokers
# (NQ ~$1-3K intraday; CME maintenance ~$20K for retail).
NQ = ContractSpec(
    symbol="NQ",
    exchange="CME",
    tick_size=0.25,
    point_value=20.00,
    commission_per_side=2.50,
    initial_margin_day=17600.0,
)

MES = ContractSpec(
    symbol="MES",
    exchange="CME",
    tick_size=0.25,
    point_value=5.00,
    commission_per_side=0.74,
    initial_margin_day=1320.0,
)

MYM = ContractSpec(
    symbol="MYM",
    exchange="CBOT",
    tick_size=1.0,
    point_value=0.50,
    commission_per_side=0.50,
    initial_margin_day=880.0,
)

# Micro E-mini Russell 2000. $5 per index point; tick 0.1 = $0.50.
M2K = ContractSpec(
    symbol="M2K",
    exchange="CME",
    tick_size=0.1,
    point_value=5.00,
    commission_per_side=0.74,
    initial_margin_day=1320.0,
)

# Energies. NYMEX pit RTH is 09:00-14:30 ET (the Globex session extends further).
CL = ContractSpec(
    symbol="CL",
    exchange="NYMEX",
    tick_size=0.01,
    point_value=1000.0,
    commission_per_side=2.50,
    initial_margin_day=1500.0,
    rth_start_et=time(9, 0),
    rth_end_et=time(14, 30),
)

MCL = ContractSpec(
    symbol="MCL",
    exchange="NYMEX",
    tick_size=0.01,
    point_value=100.0,
    commission_per_side=0.74,
    initial_margin_day=500.0,
    rth_start_et=time(9, 0),
    rth_end_et=time(14, 30),
)

NG = ContractSpec(
    symbol="NG",
    exchange="NYMEX",
    tick_size=0.001,
    point_value=10000.0,
    commission_per_side=2.50,
    initial_margin_day=1500.0,
    rth_start_et=time(9, 0),
    rth_end_et=time(14, 30),
)

MNG = ContractSpec(
    symbol="MNG",
    exchange="NYMEX",
    tick_size=0.001,
    point_value=1000.0,
    commission_per_side=0.74,
    initial_margin_day=100.0,
    rth_start_et=time(9, 0),
    rth_end_et=time(14, 30),
)

# FX. CME FX day session is 07:20-14:00 CT = 08:20-15:00 ET.
EUR = ContractSpec(
    symbol="6E",
    exchange="CME",
    tick_size=0.00005,
    point_value=125000.0,
    commission_per_side=2.50,
    initial_margin_day=1100.0,
    rth_start_et=time(8, 20),
    rth_end_et=time(15, 0),
)

M6E = ContractSpec(
    symbol="M6E",
    exchange="CME",
    tick_size=0.0001,
    point_value=12500.0,
    commission_per_side=0.74,
    initial_margin_day=400.0,
    rth_start_et=time(8, 20),
    rth_end_et=time(15, 0),
)

# Crypto. MBT tick = 5 index points (@ $0.10/pt = $0.50). MET tick = 0.5 index
# points (@ $0.10/pt = $0.05). Underlying is nearly 24h but we default to the
# equity RTH window for cross-asset strategy consistency; override via config
# if testing overnight sessions.
MBT = ContractSpec(
    symbol="MBT",
    exchange="CME",
    tick_size=5.0,
    point_value=0.10,
    commission_per_side=2.00,
    initial_margin_day=500.0,
)

MET = ContractSpec(
    symbol="MET",
    exchange="CME",
    tick_size=0.5,
    point_value=0.10,
    commission_per_side=0.75,
    initial_margin_day=400.0,
)


_REGISTRY: dict[str, ContractSpec] = {
    "MNQ": MNQ,
    "NQ": NQ,
    "MES": MES,
    "MYM": MYM,
    "M2K": M2K,
    "CL": CL,
    "MCL": MCL,
    "NG": NG,
    "MNG": MNG,
    "6E": EUR,
    "M6E": M6E,
    "MBT": MBT,
    "MET": MET,
}


def get(symbol: str) -> ContractSpec:
    """Lookup a contract spec by root symbol (case-insensitive).

    Args:
        symbol: Root symbol (e.g. "MNQ", "mes").

    Returns:
        ContractSpec for the symbol.

    Raises:
        KeyError: If the symbol is not registered.
    """
    key = symbol.upper().strip()
    if key not in _REGISTRY:
        raise KeyError(
            f"Unknown contract '{symbol}'. Registered: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[key]


def register(spec: ContractSpec) -> None:
    """Register or replace a contract spec. Used to load overrides from YAML."""
    _REGISTRY[spec.symbol.upper()] = spec


def all_symbols() -> list[str]:
    """Return registered symbols in deterministic order."""
    return sorted(_REGISTRY)
