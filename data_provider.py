""" Market data provider for MT5. """
import pandas as pd
from typing import Optional
import MetaTrader5 as mt5
import logging
from config import TimeFrame, TIMEFRAME_MAP

logger = logging.getLogger(__name__)

class DataProvider:
    """Provides market data from MetaTrader 5."""
    
    def __init__(self):
        self._cache = {}
    
    def get_historical_data(
        self,
        symbol: str,
        timeframe: TimeFrame,
        bars: int,
    ) -> pd.DataFrame:
        """ Get historical price data for a symbol. """
        mtf = TIMEFRAME_MAP[timeframe]
        rates = mt5.copy_rates_from_pos(symbol, mtf, 0, bars)
        
        if rates is None:
            logger.warning(f"No data for {symbol} on {timeframe.value}")
            return pd.DataFrame()
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        
        return df