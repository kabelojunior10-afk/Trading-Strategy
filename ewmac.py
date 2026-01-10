"""
EXPONENTIAL WEIGHTED MOVING AVERAGE CROSSOVER (EWMAC)
A systematic trading strategy using fast and slow exponentially weighted moving averages.
"""

import os
import time
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime

# -------------------------------
# Parameters
# -------------------------------

tickers = ["GC=F"] 

start_date = "2024-01-01"
end_date = datetime.today().strftime("%Y-%m-%d")

Lfast = 16
Lslow = 4 * Lfast
vol_lookback = 25
capmin, capmax = -20, 20

# Output folder
output_folder = "ewmac_charts"
os.makedirs(output_folder, exist_ok=True)

# -----------------------------------
# Helper functions
# -----------------------------------
def ewmac_forecast_scalar(Lfast, Lslow):
    return 10 / np.sqrt(Lfast)

def retry_download(ticker, start, end, max_retries=3):
    """Try multiple times if Yahoo Finance fails."""
    for attempt in range(max_retries):
        try:
            df = yf.download(ticker, start=start, end=end, progress=False)
            if not df.empty:
                return df
        except Exception as e:
            print(f"[Retry {attempt+1}] Error downloading {ticker}: {e}")
    print(f"Failed to retrieve data for {ticker} after {max_retries} attempts.")
    return pd.DataFrame()

# -----------------------------------
# Main Loop
# -----------------------------------
f_scalar = ewmac_forecast_scalar(Lfast, Lslow)
signals = []  # collect latest signals

for ticker in tickers:
    try:
        df = retry_download(ticker, start_date, end_date)
        if df.empty:
            continue

        price = df["Close"].dropna()

        # Fast and slow EWMA
        fast_ewma = price.ewm(span=Lfast).mean()
        slow_ewma = price.ewm(span=Lslow).mean()

        # Raw signal
        raw_ewmac = fast_ewma - slow_ewma

        # Volatility adjustment
        returns = price.pct_change()
        vol = returns.ewm(span=vol_lookback).std()
        vol_adj_ewmac = raw_ewmac / vol

        # Forecast signal
        forecast = vol_adj_ewmac * f_scalar
        cap_forecast = forecast.clip(lower=capmin, upper=capmax)

        # Save latest signal
        latest_signal = cap_forecast.iloc[-1]
        signals.append({"Ticker": ticker, "LatestSignal": latest_signal})

        # -------------------------------
        # Plot
        # -------------------------------
        fig, axs = plt.subplots(1, 2, figsize=(18, 6))

        axs[0].plot(price, label="Price", color="black")
        axs[0].plot(fast_ewma, label=f"Fast EWMA ({Lfast})", linestyle="--")
        axs[0].plot(slow_ewma, label=f"Slow EWMA ({Lslow})", linestyle="--")
        axs[0].set_title(f"EWMAC Crossover\n{ticker}")
        axs[0].set_xlabel("Date")
        axs[0].set_ylabel("Price")
        axs[0].legend()
        axs[0].grid(True)

        axs[1].plot(cap_forecast, label="Capped Forecast Signal", color="blue")
        axs[1].axhline(10, color="green", linestyle="--", label="Buy Threshold")
        axs[1].axhline(-10, color="red", linestyle="--", label="Sell Threshold")
        axs[1].set_title("Capped EWMAC Forecast Signal")
        axs[1].set_xlabel("Date")
        axs[1].set_ylabel("Forecast Value")
        axs[1].legend()
        axs[1].grid(True)

        plt.tight_layout()
        save_path = os.path.join(output_folder, f"EWMAC_{ticker}.png")
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        plt.close()

        print(f"Saved chart: {save_path}")
        time.sleep(0.2)

    except Exception as e:
        print(f"Error with {ticker}: {e}")
