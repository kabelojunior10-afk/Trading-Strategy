import pandas as pd
import numpy as np
from typing import Tuple
from dataclasses import dataclass
import logging
from signal import SignalType
from strategy_base import Strategy

logger = logging.getLogger(__name__)

@dataclass
class StrategyConfig:
    fast_length: int = 16
    slow_length: int = 64
    vol_lookback: int = 25
    cap_min: float = -20.0
    cap_max: float = 20.0
    buy_threshold: float = 10.0
    sell_threshold: float = -10.0
    
    @property
    def f_scalar(self) -> float:
        return 10.0 / np.sqrt(self.fast_length)

class EWMACStrategy(Strategy):
    def __init__(self, config: StrategyConfig):
        self.config = config

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
     
        df = df.copy()
    
        df["fast_ewma"] = df["close"].ewm(
            span=self.config.fast_length, 
            adjust=False
        ).mean()
        
        df["slow_ewma"] = df["close"].ewm(
            span=self.config.slow_length, 
            adjust=False
        ).mean()
        
        df["raw_ewmac"] = df["fast_ewma"] - df["slow_ewma"]
       
        df["ret"] = df["close"].diff() / df["close"].shift(1)
        
        df["ret_squared"] = df["ret"] ** 2
        df["vol"] = np.sqrt(
            df["ret_squared"].ewm(
                span=self.config.vol_lookback, 
                adjust=False
            ).mean()
        )
        
        df["vol_adj"] = np.where(
            (df["vol"] > 0) & df["vol"].notna(),
            df["raw_ewmac"] / df["vol"],
            np.nan
        )
        
        # Apply scalar to get forecast
        df["forecast"] = df["vol_adj"] * self.config.f_scalar
        
        # Cap the forecast - EXACTLY matches math.max(capmin, math.min(capmax, forecast))
        df["capped_forecast"] = df["forecast"].clip(
            self.config.cap_min, 
            self.config.cap_max
        )
        
        return df

    def get_signal(self, df: pd.DataFrame) -> Tuple[SignalType, float]:
    
        if len(df) < 2:
            return SignalType.NEUTRAL, 0.0
        
        # Use most recent completed candle to avoid look-ahead bias
        curr_forecast = float(df.iloc[-2]["capped_forecast"]) if not pd.isna(df.iloc[-2]["capped_forecast"]) else None
        
        if curr_forecast is None:
            return SignalType.NEUTRAL, 0.0
        
        # SIMPLE LEVEL-BASED SIGNALS for trading
        if curr_forecast >= 10.0:
            return SignalType.BUY, curr_forecast
        elif curr_forecast <= -10.0:
            return SignalType.SELL, curr_forecast
        else:
            return SignalType.NEUTRAL, curr_forecast

    def get_trend(self, forecast: float) -> str:
        """
        Determine trend based on forecast value.
        """
        if forecast > 0:
            return "BULLISH"
        elif forecast < 0:
            return "BEARISH"
        return "NEUTRAL"
    
    def get_trend_from_ewma(self, df: pd.DataFrame) -> str:
        """
        EXACT trend determination matching Pine Script's fast_ewma > slow_ewma.
        This is used for visualization in Pine Script.
        """
        if len(df) < 2:
            return "NEUTRAL"
        
        row = df.iloc[-1]
        if pd.isna(row["fast_ewma"]) or pd.isna(row["slow_ewma"]):
            return "NEUTRAL"
        
        if row["fast_ewma"] > row["slow_ewma"]:
            return "BULLISH"
        elif row["fast_ewma"] < row["slow_ewma"]:
            return "BEARISH"
        
        return "NEUTRAL"

    def get_strategy_name(self) -> str:
        return "EWMAC"
    
    def get_bull_cross(self, df: pd.DataFrame) -> bool:

        if len(df) < 3:
            return False
        
        curr_fast = df["fast_ewma"].iloc[-1]
        curr_slow = df["slow_ewma"].iloc[-1]
        prev_fast = df["fast_ewma"].iloc[-2]
        prev_slow = df["slow_ewma"].iloc[-2]
        
        if pd.isna(curr_fast) or pd.isna(curr_slow) or pd.isna(prev_fast) or pd.isna(prev_slow):
            return False
        
        return (prev_fast <= prev_slow) and (curr_fast > curr_slow)
    
    def get_bear_cross(self, df: pd.DataFrame) -> bool:
        
        if len(df) < 3:
            return False
        
        curr_fast = df["fast_ewma"].iloc[-1]
        curr_slow = df["slow_ewma"].iloc[-1]
        prev_fast = df["fast_ewma"].iloc[-2]
        prev_slow = df["slow_ewma"].iloc[-2]
        
        if pd.isna(curr_fast) or pd.isna(curr_slow) or pd.isna(prev_fast) or pd.isna(prev_slow):
            return False
        
        return (prev_fast >= prev_slow) and (curr_fast < curr_slow)