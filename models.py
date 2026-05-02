from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from signal import SignalType, PositionType

@dataclass
class Trade:
    ticket: int
    symbol: str
    signal_type: SignalType
    position_type: PositionType
    entry_price: float
    entry_time: datetime
    volume: float
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    profit: Optional[float] = None
    strategy: str = "EWMAC"
    
    @property
    def is_open(self) -> bool:
        return self.exit_price is None

@dataclass
class SignalData:
    signal: SignalType
    forecast: float
    trend: str
    timestamp: datetime

@dataclass
class PositionState:
    has_position: bool
    position_type: Optional[PositionType]
    ticket: Optional[int]
    entry_price: Optional[float]
    volume: Optional[float]
    unrealized_pnl: float = 0.0
    
    @classmethod
    def empty(cls) -> "PositionState":
        return cls(
            has_position=False,
            position_type=None,
            ticket=None,
            entry_price=None,
            volume=None,
            unrealized_pnl=0.0
        )