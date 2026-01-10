import pandas as pd
import yfinance as yf

def get_ohlc_from_yf(
    ticker: str, period: str = "2y", interval: str = "1d"
) -> pd.DataFrame:
    """
    Get OHLC DataFrame with Volume from Yahoo Finance.
    Save some supplementary data in attrs before returning.
    Valid periods:'1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'
    Valid intervals: 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo
    """
    res = yf.Ticker(ticker=ticker).history(period=period, interval=interval)
    
    if res.shape[0] == 0:
        fallback_options = [
            ("1d", "1m"),
            ("5d", "5m"),
            ("1mo", "1d"),
        ]
        for p, i in fallback_options:
            res = yf.Ticker(ticker=ticker).history(period=p, interval=i)
            if res.shape[0] > 0:
                print(f"[INFO] Fallback worked for {ticker}: using period={p}, interval={i}")
                period, interval = p, i
                break
    
    if res.shape[0] == 0:
        raise RuntimeError(
            f"get_ohlc_with_typical: Yahoo Finance returned empty Df for {ticker=}, tried {period=} and {interval=} (with fallbacks)"
        )
    
    res = res[["Open", "High", "Low", "Close", "Volume"]]
    res.attrs["ticker"] = ticker
    res.attrs["period"] = period
    res.attrs["interval"] = interval
    return res