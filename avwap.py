import os
import warnings
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from import_ohlc.yahoo_finance import get_ohlc_from_yf
from misc.atr import add_atr_col_to_df
from misc.fill_min_max import fill_is_min_max
from constants import ATR_SMOOTHING_N, first_day_of_year
from vwaps_plot import vwaps_plot_build_save
from misc.chart_annotation import get_chart_annotation_1d
from draw_avg import draw_5_days_avg
from price_volume import draw_profile_of_data

# ---------------------------
# Setup directories
# ---------------------------
os.makedirs("volume_profile", exist_ok=True)
os.makedirs("daily_vwap", exist_ok=True)
os.makedirs("five_day_sma", exist_ok=True)
trade_summary_folder = "trade_summaries"
os.makedirs(trade_summary_folder, exist_ok=True)
warnings.filterwarnings("ignore", category=UserWarning)

# ---------------------------
# Prepare ticker data
# ---------------------------
def prepare_data(ticker: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    try:
        df = get_ohlc_from_yf(ticker=ticker, period=period, interval=interval)
    except Exception as e:
        print(f"Failed to fetch data for {ticker} from Yahoo Finance: {e}")
        return pd.DataFrame()
    df = add_atr_col_to_df(df, n=ATR_SMOOTHING_N, exponential=False)
    df = fill_is_min_max(df)
    print(f"Prepared data for {ticker}:")
    return df

tickers = []

ticker_data = {ticker: prepare_data(ticker) for ticker in tickers if not prepare_data(ticker).empty}

# ---------------------------
# Anchor dates
# ---------------------------
def get_anchor_dates(df: pd.DataFrame, custom_dates: list[str] = None) -> list[str]:
    last_min_date = df[df["is_min"]].index.max()
    last_max_date = df[df["is_max"]].index.max()
    anchor_dates = [first_day_of_year]
    if pd.notna(last_min_date):
        anchor_dates.append(last_min_date.strftime('%Y-%m-%d %H:%M:%S'))
    if pd.notna(last_max_date):
        anchor_dates.append(last_max_date.strftime('%Y-%m-%d %H:%M:%S'))
    if custom_dates:
        anchor_dates.extend(custom_dates)
    return [date for date in anchor_dates if pd.notna(date)]

anchor_dates_dict = {ticker: get_anchor_dates(df) for ticker, df in ticker_data.items()}
print("Anchor dates have been successfully generated for all tickers.")

# ---------------------------
# Analyze tickers
# ---------------------------
def analyze_ticker(df: pd.DataFrame, ticker: str, anchor_dates: list[str]):
    df.attrs["ticker"] = ticker
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_convert(None)
    dates_only = df.index.normalize().date
    for i, anchor_date in enumerate(anchor_dates, 1):
        anchor_ts = pd.Timestamp(anchor_date).date()
        if anchor_ts in dates_only:
            anchor_idx = list(dates_only).index(anchor_ts)
        else:
            anchor_idx = 0
        df_from_anchor = df.iloc[anchor_idx:]
        typical_price = (df_from_anchor["Open"] + df_from_anchor["High"] +
                         df_from_anchor["Low"] + df_from_anchor["Close"]) / 4
        cumulative_typical_volume = (typical_price * df_from_anchor["Volume"]).cumsum()
        cumulative_volume = df_from_anchor["Volume"].cumsum()
        vwap = cumulative_typical_volume / cumulative_volume.replace(0, pd.NA)
        vwap = vwap.ffill()
        df.loc[df_from_anchor.index, f"A_VWAP_{i}"] = vwap
    file_name = f"daily_vwap/daily_{ticker}_annotated.png"
    vwaps_plot_build_save(
        input_df=df,
        anchor_dates=anchor_dates,
        chart_title=f"{ticker} Daily with Anchored VWAPs",
        chart_annotation_func=get_chart_annotation_1d,
        add_last_min_max=False,
        file_name=file_name,
        print_df=False
    )
    print(f"Daily VWAP chart saved for {ticker} at '{file_name}'")
    last_close = df["Close"].iloc[-1]
    vwap_year = df["A_VWAP_1"].iloc[-1]
    vwap_min = df["A_VWAP_2"].iloc[-1]
    vwap_max = df["A_VWAP_3"].iloc[-1]
    atr = df[f"atr_{ATR_SMOOTHING_N}"].iloc[-1]
    trend = "Neutral"
    if last_close > vwap_year and last_close > vwap_min:
        trend = "Bullish"
    elif last_close < vwap_year and last_close < vwap_max:
        trend = "Bearish"
    signal = None
    if trend == "Bullish" and last_close > vwap_min and abs(last_close - vwap_min) < atr * 0.5:
        signal = "Long"
    elif trend == "Bearish" and last_close < vwap_max and abs(vwap_max - last_close) < atr * 0.5:
        signal = "Short"
    if signal == "Long":
        entry_price = last_close
        stop_loss = vwap_min - atr
        take_profit = vwap_max
        risk = entry_price - stop_loss
    elif signal == "Short":
        entry_price = last_close
        stop_loss = vwap_max + atr
        take_profit = vwap_min
        risk = stop_loss - entry_price
    else:
        entry_price = stop_loss = take_profit = risk = None
    account_size = 10000
    risk_percent = 0.01
    position_size = (account_size * risk_percent) / risk if risk else 0
    return {
        "trend": trend,
        "signal": signal,
        "last_close": last_close,
        "vwap_year": vwap_year,
        "vwap_min": vwap_min,
        "vwap_max": vwap_max,
        "atr": atr,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "position_size": position_size
    }

# ---------------------------
# Main execution
# ---------------------------
if __name__ == "__main__":
    results = {}
    for ticker, df in ticker_data.items():
        if df.empty:
            print(f"Skipping {ticker}: no data available.")
            continue
        try:
            res = analyze_ticker(df, ticker, anchor_dates_dict[ticker])
            results[ticker] = res
        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")
            continue
    results_df = pd.DataFrame(results).T
    results_df.to_csv("anchored_vwap.csv", index=True)
    print("Anchored VWAP analysis completed and CSV saved as 'anchored_vwap.csv'")
    
    # Save trade summaries
    for ticker, res in results.items():
        file_path = os.path.join(trade_summary_folder, f"{ticker}_trade_summary.txt")
        with open(file_path, "w") as f:
            f.write(f"Trade Summary for {ticker} on {datetime.now().date()}\n")
            f.write(f"Trend: {res['trend']}\n")
            f.write(f"Signal: {res['signal']}\n")
            f.write(f"Last Close: {res['last_close']:.2f}\n")
            f.write(f"VWAPs - Year: {res['vwap_year']:.2f}, Min: {res['vwap_min']:.2f}, Max: {res['vwap_max']:.2f}\n")
            f.write(f"ATR: {res['atr']:.2f}\n")
            if res["signal"]:
                f.write(f"Entry: {res['entry_price']:.2f}, Stop Loss: {res['stop_loss']:.2f}, "
                        f"Take Profit: {res['take_profit']:.2f}\n")
                f.write(f"Position Size: {res['position_size']:.2f} shares\n")
                f.write(f"Executing {res['signal']} trade for {ticker}\n")
            else:
                f.write("No trade signal generated.\n")
        print(f"Trade summary saved for {ticker} at '{file_path}'")
    
    # Generate additional plots
    GENERATE_INTRADAY_VWAP = False
    for ticker, df in ticker_data.items():
        if df.empty:
            continue
        print(f"Data for {ticker}: {df.shape}")
        try:
            draw_5_days_avg(ticker=ticker, interval="15m")
            print(f"{ticker}: 5-day SMA image generated")
        except Exception as e:
            print(f"Skipping 5-day SMA for {ticker}: {e}")
        try:
            draw_profile_of_data(ohlc_df=df, ticker=ticker)
            print(f"{ticker}: Price and Volume profile image generated")
        except Exception as e:
            print(f"Skipping Price/Volume profile for {ticker}: {e}")
        try:
            intraday_df = get_ohlc_from_yf(ticker=ticker, period="5d", interval="1m")
            intraday_df = add_atr_col_to_df(intraday_df, n=ATR_SMOOTHING_N, exponential=False)
            if GENERATE_INTRADAY_VWAP:
                vwaps_plot_build_save(
                    input_df=intraday_df,
                    anchor_dates=anchor_dates_dict[ticker],
                    chart_title=f"{ticker} 1m with Anchored VWAPs",
                    chart_annotation_func=get_chart_annotation_1d,
                    add_last_min_max=False,
                    file_name=f"daily_vwap/intraday_{ticker}.png",
                    hide_extended_hours=True,
                    print_df=False
                )
                print(f"{ticker}: Intraday VWAP image generated")
        except Exception as e:
            print(f"Skipping intraday VWAP for {ticker}: {e}")
        plt.close('all')