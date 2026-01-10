# Scaled Price Breakout.py

import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from datetime import datetime

# -------------------------------------
# CONFIGURATION
# -------------------------------------

tickers = []

start_date = "2025-01-01"
end_date = datetime.today().strftime("%Y-%m-%d")

output_dir = "breakout_plots"
os.makedirs(output_dir, exist_ok=True)

# -------------------------------------
# FUNCTIONS
# -------------------------------------

def download_and_clean(ticker, start, end):
    df = yf.download(
        ticker,
        start=start,
        end=end,
        progress=False,
        auto_adjust=False
    )

    if df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.dropna(inplace=True)

    return df


def add_scaled_price_features(df, window=20):
    close = df["Close"]

    df["RollingMax"] = close.rolling(window).max()
    df["RollingMin"] = close.rolling(window).min()
    df["RollingAvg"] = close.rolling(window).mean()
    df["Range"] = df["RollingMax"] - df["RollingMin"]
    df["ScaledPrice"] = (close - df["RollingAvg"]) / (df["Range"] + 1e-8)

    return df


def build_pro_chart(df, ticker):
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3]
    )

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="OHLC",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
            showlegend=False
        ),
        row=1,
        col=1
    )

    fig.add_trace(go.Scatter(x=df.index, y=df["RollingMax"], name="20D High",
                             line=dict(color="#ff4444", width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["RollingMin"], name="20D Low",
                             line=dict(color="#00ccff", width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["RollingAvg"], name="20D Avg",
                             line=dict(color="#ffbb33", width=2)), row=1, col=1)

    fig.add_trace(
        go.Scatter(
            x=np.concatenate([df.index, df.index[::-1]]),
            y=np.concatenate([df["RollingMax"].values,
                              df["RollingMin"][::-1].values]),
            fill="toself",
            fillcolor="rgba(180,180,180,0.12)",
            line=dict(color="rgba(0,0,0,0)"),
            hoverinfo="skip",
            showlegend=False
        ),
        row=1,
        col=1
    )

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["ScaledPrice"],
            name="Scaled Price",
            line=dict(color="#e91e63", width=3),
            fill="tozeroy",
            fillcolor="rgba(233,30,99,0.2)"
        ),
        row=2,
        col=1
    )

    for lvl in [1.0, 0.5, 0, -0.5, -1.0]:
        fig.add_hline(y=lvl, line_dash="dot", line_color="gray",
                      opacity=0.6, row=2, col=1)

    pretty_name = ticker.replace("=F", " Futures").replace("-", "/")

    fig.update_layout(
        title=dict(
            text=f"<b>{pretty_name}</b>\nScaled Price Breakout Strategy",
            x=0.5,
            font_size=22
        ),
        template="plotly_dark",
        height=900,
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        xaxis_rangeslider_visible=False,
        margin=dict(l=60, r=60, t=100, b=60)
    )

    fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
    fig.update_yaxes(title_text="Scaled Price",
                     range=[-2.2, 2.2], row=2, col=1)

    return fig

# -------------------------------------
# MAIN LOOP
# -------------------------------------

print("Starting Scaled Price Breakout charts...\n")

for ticker in tickers:
    print(f"Processing {ticker}...")

    df = download_and_clean(ticker, start_date, end_date)

    if df is None or len(df) < 50:
        print(f" → Not enough data for {ticker}\n")
        continue

    df = add_scaled_price_features(df, window=20)
    df = df.dropna()

    fig = build_pro_chart(df, ticker)

    filename = f"{ticker.replace('=', '').replace('-', '')}_ScaledPriceBreakout_.png"
    path = os.path.join(output_dir, filename)

    fig.write_image(path, width=1920, height=1080, scale=3)

    print(f" → Saved {filename}\n")

print("All charts generated successfully!")
print(f"Folder: {os.path.abspath(output_dir)}")
