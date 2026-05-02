import math
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional
import MetaTrader5 as mt5

# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class TradingMode(Enum):
    BUY_ONLY  = "BUY_ONLY"
    SELL_ONLY = "SELL_ONLY"

class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"

class TimeFrame(Enum):
    M1  = "M1"
    M5  = "M5"
    M15 = "M15"
    H1  = "H1"

# ─────────────────────────────────────────────────────────────────────────────
# Timeframe constants
# ─────────────────────────────────────────────────────────────────────────────

TIMEFRAME_MAP = {
    TimeFrame.M1:  mt5.TIMEFRAME_M1,
    TimeFrame.M5:  mt5.TIMEFRAME_M5,
    TimeFrame.M15: mt5.TIMEFRAME_M15,
    TimeFrame.H1:  mt5.TIMEFRAME_H1,
}

TIMEFRAME_META = {
    TimeFrame.M1:  {"bars": 300, "candle_seconds": 60,   "close_cooldown": 5,   "open_cooldown": 3},
    TimeFrame.M5:  {"bars": 400, "candle_seconds": 300,  "close_cooldown": 25,  "open_cooldown": 15},
    TimeFrame.M15: {"bars": 500, "candle_seconds": 900,  "close_cooldown": 75,  "open_cooldown": 45},
    TimeFrame.H1:  {"bars": 600, "candle_seconds": 3600, "close_cooldown": 300, "open_cooldown": 180},
}

# ─────────────────────────────────────────────────────────────────────────────
# Config dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SymbolConfig:
    symbol: str
    mode: TradingMode
    enabled: bool = True
    lot_size: float = 0.01
    timeframe: TimeFrame = TimeFrame.M15
    max_positions: int = 1
    use_volatility_scaling: bool = True
    max_daily_trades: Optional[int] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None

@dataclass
class RiskConfig:
    max_risk_per_trade: float = 0.02
    max_total_risk: float = 0.20
    max_daily_loss: float = 0.05
    max_correlation_exposure: float = 0.30
    min_free_margin_ratio: float = 0.10

@dataclass
class StrategyConfig:
    """EWMAC Strategy Configuration - EXACTLY Matches Pine Script"""
    fast_length: int = 16
    slow_length: int = 64
    vol_lookback: int = 25
    cap_min: float = -20.0
    cap_max: float = 20.0
    buy_threshold: float = 10.0  
    sell_threshold: float = -10.0  

    @property
    def f_scalar(self) -> float:
        """EXACTLY matches Pine Script: 10.0 / math.sqrt(Lfast)"""
        return 10.0 / math.sqrt(self.fast_length)

@dataclass
class SystemConfig:
    symbols: Dict[str, SymbolConfig]
    risk: RiskConfig
    strategy: StrategyConfig
    poll_interval: int = 10
    magic_number: int = 123456
    enable_dashboard: bool = True
    log_to_file: bool = True
    max_retries: int = 3
    retry_delay: float = 1.0

# Default configurations
DEFAULT_SYMBOLS_CONFIG: Dict[str, SymbolConfig] = {
    "GOLD": SymbolConfig(
        symbol="GOLD",
        mode=TradingMode.BUY_ONLY,
        enabled=False,
        lot_size=0.01,
        timeframe=TimeFrame.M1,
    ),
    "BTCUSD": SymbolConfig(
        symbol="BTCUSD",
        mode=TradingMode.SELL_ONLY,
        enabled=False,
        lot_size=0.01,
        timeframe=TimeFrame.M1,
    ),
    "USDZAR": SymbolConfig(
        symbol="US_30",
        mode=TradingMode.BUY_ONLY,
        enabled=False,
        lot_size=0.01,
        timeframe=TimeFrame.M1,
    ),
    "US_TECH100": SymbolConfig(
        symbol="US_TECH100",
        mode=TradingMode.BUY_ONLY,
        enabled=False,
        lot_size=0.01,
        timeframe=TimeFrame.M1,
    ),
}

def load_config(custom_symbols: Optional[Dict[str, SymbolConfig]] = None) -> SystemConfig:
    symbols = custom_symbols if custom_symbols else DEFAULT_SYMBOLS_CONFIG
    return SystemConfig(
        symbols=symbols,
        risk=RiskConfig(),
        strategy=StrategyConfig(),
        poll_interval=10,
        magic_number=123456,
        enable_dashboard=True,
        log_to_file=True,
        max_retries=3,
        retry_delay=1.0,
    )