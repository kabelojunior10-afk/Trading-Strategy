import mplfinance as mpf
import pandas as pd
import os
from import_ohlc.yahoo_finance import get_ohlc_from_yf
import matplotlib.pyplot as plt

def draw_5_days_avg(ticker: str, interval: str = "15m"):
    """
    Draw 5-day SMA with candles safely. Skips tickers with insufficient or missing data.
    """
    try:
        if interval not in ["15m", "30m"]:
            raise ValueError(f"{interval=}, must be 15m or 30m")
        df = get_ohlc_from_yf(ticker=ticker, period="1mo", interval=interval)
        if df.empty:
            print(f"{ticker}: No OHLC data returned, skipping.")
            return
        
        if not pd.api.types.is_datetime64_any_dtype(df.index):
            df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_convert(None)
        ma_candles_count = 130 if interval == "15m" else 65
        if len(df) < ma_candles_count:
            print(f"{ticker}: Insufficient data ({len(df)} candles), skipping plot.")
            return
        ma_values = df["Close"].rolling(ma_candles_count).mean().values
        ma_df = pd.DataFrame(dict(ma_vals=ma_values), index=df.index)
        ap = mpf.make_addplot(ma_df, type="line")
        os.makedirs("five_day_sma", exist_ok=True)
        file_path = f"five_day_sma/5_d_avg_{ticker}.png"
        mpf.plot(
            df,
            type="candle",
            addplot=ap,
            figratio=(12, 8),
            datetime_format="%b-%d",
            title={
                "title": f"{ticker}, interval {interval}, MA last {round(ma_df['ma_vals'].iloc[-1], 2)}",
                "y": 1
            },
            tight_layout=True,
            savefig=file_path
        )
        print(f"{ticker}: 5-day SMA plot saved.")
    except Exception as e:
        print(f"{ticker}: Skipping 5-day SMA due to error: {e}")