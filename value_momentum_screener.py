import numpy as np
import pandas as pd
import yfinance as yf
import math
from scipy import stats
import warnings
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

warnings.filterwarnings("ignore")

# -----------------------------
# Stock list
# -----------------------------

stocks = []

# -----------------------------
# Function to fetch valuation ratios
# -----------------------------
def get_valuation_ratios(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.get_info()
        price = info.get('regularMarketPrice', np.nan) 
        price_str = f"${price:,.2f}" if not np.isnan(price) else "N/A"
        name = info.get("shortName", ticker)
        sector = info.get("sector", "N/A")
        pe_ratio = info.get('trailingPE', np.nan)
        pb_ratio = info.get('priceToBook', np.nan)
        ps_ratio = info.get('priceToSalesTrailing12Months', np.nan)
        ev = info.get('enterpriseValue', np.nan)
        ebitda = info.get('ebitda', np.nan)
        gross_profit = info.get('grossProfits', np.nan)
        ev_to_ebitda = ev / ebitda if ev and ebitda else np.nan
        ev_to_gp = ev / gross_profit if ev and gross_profit else np.nan

        return {
            'Ticker': ticker,
            'Name': name,
            'Sector': sector,
            'Price': price_str,
            'P/E': pe_ratio,
            'P/B': pb_ratio,
            'P/S': ps_ratio,
            'EV/EBITDA': ev_to_ebitda,
            'EV/GP': ev_to_gp
        }
    except Exception as e:
        print(f"Error fetching ratios for {ticker}: {e}")
        return {
            'Ticker': ticker,
            'Name': 'N/A',
            'Sector': 'N/A',
            'Price': 'N/A',
            'P/E': np.nan,
            'P/B': np.nan,
            'P/S': np.nan,
            'EV/EBITDA': np.nan,
            'EV/GP': np.nan
        }

# -----------------------------
# Save per-sector CSVs with raw + ranks
# -----------------------------
def save_sector_csvs(full_df):
    output_dir = "fundamentals"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for sector, sector_df in full_df.groupby("Sector"):
        safe_sector = "".join(c if c.isalnum() else "_" for c in sector)
        file_path = os.path.join(output_dir, f"{safe_sector}.csv")
        sector_df.to_csv(file_path, index=False)
        print(f"Saved: {file_path}")

# -----------------------------
# Main workflow
# -----------------------------
def main():
    # Fetch valuation ratios
    value_data = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(get_valuation_ratios, ticker): ticker for ticker in stocks}
        for future in as_completed(futures):
            value_data.append(future.result())

    value_df = pd.DataFrame(value_data)

    # Round numeric metrics
    value_metrics = ['P/E', 'P/B', 'P/S', 'EV/EBITDA', 'EV/GP']
    for col in value_metrics:
        value_df[col] = (
            pd.to_numeric(value_df[col], errors='coerce')
            .replace([np.inf, -np.inf], np.nan)
            .round(0)
            .astype('Int64')
        )

    # Fetch historical prices
    end_date = datetime.today()
    start_date = end_date - timedelta(days=730)
    price_data = yf.download(stocks, start=start_date, end=end_date)['Close']

    # Compute momentum
    momentum_df = pd.DataFrame(index=stocks)
    lookback_periods = {'1M': 21, '3M': 63, '6M': 126, '12M': 252}

    for label, days in lookback_periods.items():
        returns = price_data.pct_change(periods=days).iloc[-1]
        momentum_df[f"{label} Return"] = returns

    for col in momentum_df.columns:
        momentum_df[col] = momentum_df[col].apply(lambda x: f"{x:.2%}")

    # Merge valuation and momentum
    combined_df = pd.merge(value_df, momentum_df, left_on='Ticker', right_index=True)

    # Save raw combined CSV (all sectors together)
    combined_df.to_csv("stock_valuation_momentum.csv", index=False)

    # -----------------------------
    # Clean data: fill missing values
    # -----------------------------
    valuation_columns = ['P/E', 'P/B', 'P/S', 'EV/EBITDA', 'EV/GP']
    momentum_columns = ['1M Return', '3M Return', '6M Return', '12M Return']

    for column in valuation_columns:
        combined_df[column] = combined_df[column].astype(float)
        combined_df[column].fillna(combined_df[column].mean(), inplace=True)

    for column in momentum_columns:
        combined_df[column] = combined_df[column].str.rstrip('%').astype(float) / 100
        combined_df[column].fillna(combined_df[column].mean(), inplace=True)

    # -----------------------------
    # Compute percentile ranks
    # -----------------------------
    value_metrics = {
        'P/E': 'PE Percentile',
        'P/B': 'PB Percentile',
        'P/S': 'PS Percentile',
        'EV/EBITDA': 'EV/EBITDA Percentile',
        'EV/GP': 'EV/GP Percentile'
    }

    momentum_metrics = {
        '1M Return': '1M Percentile',
        '3M Return': '3M Percentile',
        '6M Return': '6M Percentile',
        '12M Return': '12M Percentile'
    }

    for row in combined_df.index:
        for metric, pct_col in value_metrics.items():
            combined_df.loc[row, pct_col] = stats.percentileofscore(
                combined_df[metric], combined_df.loc[row, metric]
            ) / 100
        for metric, pct_col in momentum_metrics.items():
            combined_df.loc[row, pct_col] = stats.percentileofscore(
                combined_df[metric], combined_df.loc[row, metric]
            ) / 100

    combined_df['Value Score'] = combined_df[list(value_metrics.values())].mean(axis=1)
    combined_df['Momentum Score'] = combined_df[list(momentum_metrics.values())].mean(axis=1)
    combined_df['Value Rank'] = combined_df['Value Score'].rank(method='min').astype(int)
    combined_df['Momentum Rank'] = combined_df['Momentum Score'].rank(ascending=False, method='min').astype(int)

    # Save final ranks CSV (all tickers, compact view)
    final_df = combined_df[['Ticker', 'Value Score', 'Value Rank', 'Momentum Score', 'Momentum Rank']]
    final_df.sort_values(by='Ticker', inplace=True)
    final_df.reset_index(drop=True, inplace=True)
    final_df.to_csv("value_momentum_ranks.csv", index=False)

    # Save per-sector fundamentals + ranks
    save_sector_csvs(combined_df)

    print("CSV files generated successfully! (global + fundamentals per sector)")

# -----------------------------
# Run script
# -----------------------------
if __name__ == "__main__":
    main()