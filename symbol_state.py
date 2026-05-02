from datetime import datetime
from typing import Optional
from config import SymbolConfig, TradingMode
from signal import SignalType, PositionType
from models import SignalData, PositionState
import time

class SymbolState:
    def __init__(self, config: SymbolConfig):
        self.config = config
        self.symbol = config.symbol
        
        # Signal state
        self.current_signal: SignalType = SignalType.NEUTRAL
        self.current_forecast: float = 0.0
        self.current_trend: str = "NEUTRAL"
        self.last_signal_time: Optional[datetime] = None
        
        # Position state
        self.position_state: PositionState = PositionState.empty()
        
        # Operational state
        self.last_candle_time: Optional[datetime] = None
        self.last_close_attempt: float = 0.0
        self.last_open_attempt: float = 0.0
        self.daily_trades: int = 0
        self.last_reset_day: int = datetime.now().day
        
        # Market data
        self.current_price: float = 0.0
        self.last_price: float = 0.0
        self.price_change_pct: float = 0.0
    
    def reset_daily_counter(self) -> None:
        current_day = datetime.now().day
        if current_day != self.last_reset_day:
            self.daily_trades = 0
            self.last_reset_day = current_day
    
    def can_open_position(self, config: SymbolConfig) -> bool:
        if config.max_daily_trades and self.daily_trades >= config.max_daily_trades:
            return False
        now = time.time()
        timeframe_meta = self._get_timeframe_meta()
        if now - self.last_open_attempt < timeframe_meta["open_cooldown"]:
            return False
        return True
    
    def can_close_position(self) -> bool:
        now = time.time()
        timeframe_meta = self._get_timeframe_meta()
        return now - self.last_close_attempt >= timeframe_meta["close_cooldown"]
    
    def _get_timeframe_meta(self) -> dict:
        from config import TIMEFRAME_META
        return TIMEFRAME_META[self.config.timeframe]
    
    def update_signal(self, signal_data: SignalData) -> None:
        self.current_signal = signal_data.signal
        self.current_forecast = signal_data.forecast
        self.current_trend = signal_data.trend
        self.last_signal_time = signal_data.timestamp
    
    def should_enter_position(self) -> bool:
        """
        ENTER based on FORECAST VALUE (not crossover)
        
        Trading Logic:
            - BUY_ONLY: Enter LONG when forecast >= +10
            - SELL_ONLY: Enter SHORT when forecast <= -10
        """
        if self.position_state.has_position:
            return False
        
        mode = self.config.mode
        if mode == TradingMode.BUY_ONLY:
            # Enter LONG when forecast reaches +10 or above
            return self.current_forecast >= 10.0
        elif mode == TradingMode.SELL_ONLY:
            # Enter SHORT when forecast reaches -10 or below
            return self.current_forecast <= -10.0
        return False
    
    def should_exit_position(self) -> bool:
        if not self.position_state.has_position:
            return False
        
        mode = self.config.mode
        if mode == TradingMode.BUY_ONLY:
            
            return (self.position_state.position_type == PositionType.LONG and 
                   self.current_forecast < 10.0)
        elif mode == TradingMode.SELL_ONLY:
          
            return (self.position_state.position_type == PositionType.SHORT and 
                   self.current_forecast > -10.0)
        return False
    
    def should_reverse_position(self) -> bool:
        return False
    
    def get_desired_action(self) -> str:
        if self.should_exit_position():
            return "EXIT"
        elif self.should_enter_position():
            return "ENTER"
        else:
            return "HOLD"
    
    def get_position_type_from_signal(self) -> PositionType:
        if self.current_signal == SignalType.BUY:
            return PositionType.LONG
        elif self.current_signal == SignalType.SELL:
            return PositionType.SHORT
        else:
            return PositionType.NONE