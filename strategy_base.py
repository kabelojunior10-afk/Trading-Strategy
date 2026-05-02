from abc import ABC, abstractmethod
from typing import Tuple, Optional
import pandas as pd
from signal import SignalType

class Strategy(ABC):
    @abstractmethod
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate strategy indicators."""
        pass
    
    @abstractmethod
    def get_signal(self, df: pd.DataFrame) -> Tuple[SignalType, float]:
        """Get current trading signal."""
        pass
    
    @abstractmethod
    def get_trend(self, forecast: float) -> str:
        """Get trend direction from forecast."""
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        """Get strategy name."""
        pass