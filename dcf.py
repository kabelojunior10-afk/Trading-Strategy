import os
import numpy as np
import pandas as pd
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor
import warnings
warnings.filterwarnings("ignore")

# -----------------------------
# Helper formatting functions
# -----------------------------
def format_currency(x: float | int | None, prefix: str = "$") -> str:
    if x is None or not isinstance(x, (int, float)):
        return "N/A"
    return f"{prefix}{x:,.2f}"

def format_percentage(x: float | int | None) -> str:
    if x is None or not isinstance(x, (int, float)):
        return "N/A"
    return f"{x*100:.2f}%"

# -----------------------------
# Helper function to safely extract balance sheet data
# -----------------------------
def safe_get_balance_item(balance_sheet, possible_names):
    """Try multiple possible field names and return the first valid value"""
    for name in possible_names:
        if name in balance_sheet.index:
            value = balance_sheet.loc[name].iloc[0]
            if not pd.isna(value):
                return value
    return 0

# -----------------------------
# Folders for outputs
# -----------------------------
dcf_output_folder = "dcf_reports"
financial_output_folder = "financial_data"
os.makedirs(dcf_output_folder, exist_ok=True)
os.makedirs(financial_output_folder, exist_ok=True)

# Master list to collect financial data for CSV
financial_data_records = []

# -----------------------------
# DCF Calculation
# -----------------------------
def calculate_dcf(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        info = stock.get_info()
        financials = stock.financials
        balance_sheet = stock.balance_sheet
        cashflow = stock.cashflow
        
        # Basic company info
        name = info.get("shortName", ticker)
        sector = info.get("sector", "N/A")
        industry = info.get("industry", "N/A")
        country = info.get("country", "N/A")
        website = info.get("website", "N/A")
        desc_snippet = info.get("longBusinessSummary", "N/A")[:250]
        
        # Pull line items safely with multiple possible field names
        ebit = safe_get_balance_item(financials, ["EBIT", "Operating Income"])
        taxes = safe_get_balance_item(financials, ["Income Tax Expense", "Tax Provision"])
        income_before_tax = safe_get_balance_item(financials, ["Pretax Income", "Income Before Tax"])
        depreciation = safe_get_balance_item(cashflow, ["Depreciation", "Depreciation And Amortization"])
        capex = -safe_get_balance_item(cashflow, ["Capital Expenditure", "Capital Expenditures"])
        working_capital_change = safe_get_balance_item(cashflow, ["Change in Working Capital", "Change In Working Capital"])
        interest_expense = safe_get_balance_item(financials, ["Interest Expense", "Interest Expense Non Operating"])
        total_debt = safe_get_balance_item(balance_sheet, ["Total Debt", "Long Term Debt", "Net Debt"])
        cash_equivalents = safe_get_balance_item(balance_sheet, ["Cash And Cash Equivalents", "Cash", "Cash Cash Equivalents And Short Term Investments"])
        
        # FIXED: Multiple possible field names for current assets and liabilities
        current_assets = safe_get_balance_item(balance_sheet, [
            "Current Assets",
            "Total Current Assets",
            "CurrentAssets"
        ])
        
        current_liabilities = safe_get_balance_item(balance_sheet, [
            "Current Liabilities",
            "Total Current Liabilities",
            "CurrentLiabilities"
        ])
        
        net_ppe = safe_get_balance_item(balance_sheet, [
            "Net PPE",
            "Property Plant Equipment Net",
            "Net Property Plant And Equipment",
            "Gross PPE"
        ])
        
        shares_outstanding = info.get("sharesOutstanding", 0)
        market_cap = info.get("marketCap", 0)
        beta = info.get("beta", 1)
        current_price = info.get("currentPrice", 0)
        
        # Assumptions
        risk_free_rate = 0.045
        market_return = 0.09
        growth_rate = 0.05
        perpetual_growth_rate = 0.025
        forecast_years = 5
        
        # FCFF
        fcff = ebit * (1 - (taxes / income_before_tax if income_before_tax else 0.25)) + depreciation - capex - working_capital_change
        
        if np.isnan(fcff) or fcff <= 0:
            net_income = safe_get_balance_item(financials, ["Net Income", "Net Income Common Stockholders"])
            effective_tax_rate = taxes / income_before_tax if income_before_tax != 0 else 0.25
            nopat = net_income + interest_expense * (1 - effective_tax_rate)
            fcff = nopat + depreciation - capex - working_capital_change
        
        # WACC
        effective_tax_rate = taxes / income_before_tax if income_before_tax != 0 else 0.25
        cost_of_debt = (interest_expense / total_debt) * (1 - effective_tax_rate) if total_debt != 0 else 0
        cost_of_equity = risk_free_rate + beta * (market_return - risk_free_rate)
        total_weight = total_debt + market_cap
        weight_debt = total_debt / total_weight if total_weight != 0 else 0
        weight_equity = market_cap / total_weight if total_weight != 0 else 1
        wacc = (weight_equity * cost_of_equity) + (weight_debt * cost_of_debt)
        wacc = min(max(wacc, 0.06), 0.14)  # Clamp WACC between 6% and 14%
        
        # ROIC
        invested_capital = current_assets - current_liabilities + net_ppe
        roic = (ebit * (1 - effective_tax_rate)) / invested_capital if invested_capital != 0 else 0
        excess_returns = roic - wacc if roic != 0 and wacc != 0 else 0
        
        # Forecast FCFFs
        future_fcff = [fcff * (1 + growth_rate) ** t for t in range(1, forecast_years + 1)]
        last_fcff = future_fcff[-1] if future_fcff else fcff
        terminal_value = (last_fcff * (1 + perpetual_growth_rate)) / (wacc - perpetual_growth_rate) if wacc > perpetual_growth_rate else 0
        
        pv_fcff = [fcf / (1 + wacc) ** t for t, fcf in enumerate(future_fcff, 1)]
        pv_terminal = terminal_value / (1 + wacc) ** forecast_years if terminal_value != 0 else 0
        
        total_pv = sum(pv_fcff) + pv_terminal
        market_equity_value = total_pv + cash_equivalents - total_debt
        fair_value_per_share = market_equity_value / shares_outstanding if shares_outstanding != 0 else 0
        upside = ((fair_value_per_share - current_price) / current_price) * 100 if current_price else 0
        margin_of_safety_pct = ((fair_value_per_share - current_price) / fair_value_per_share) * 100 if fair_value_per_share != 0 else 0
        valuation = "Undervalued" if upside > 0 else "Overvalued"
        
        # -------------------------
        # Save report (text file)
        # -------------------------
        output = f"\n{'='*80}\n"
        output += f"DCF Analysis for {ticker} - {name}\n"
        output += f"Sector: {sector}\nIndustry: {industry}\nCountry: {country}\nWebsite: {website}\n"
        output += f"Description: {desc_snippet}\n\n"
        output += f"FCFF: {format_currency(fcff)}\n"
        output += f"WACC: {format_percentage(wacc)}\n"
        output += f"ROIC: {format_percentage(roic)}\n"
        output += f"Excess Returns: {format_percentage(excess_returns)}\n"
        output += f"Future FCFF: {[format_currency(x, prefix='$') for x in future_fcff]}\n"
        output += f"PV of FCFF: {[format_currency(x) for x in pv_fcff]}\n"
        output += f"Terminal Value: {format_currency(terminal_value)}\n"
        output += f"PV of Terminal Value: {format_currency(pv_terminal)}\n"
        output += f"Market Equity Value: {format_currency(market_equity_value)}\n"
        output += f"Fair Value Per Share: {format_currency(fair_value_per_share)}\n"
        output += f"Current Price: {format_currency(current_price)}\n"
        output += f"Upside: {upside:.2f}%\n"
        output += f"Margin of Safety: {margin_of_safety_pct:.2f}%\n"
        output += f"Valuation: {valuation}\n"
        output += f"{'='*80}\n"
        
        file_path = os.path.join(dcf_output_folder, f"{ticker}_dcf.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(output)
        
        # -------------------------
        # Append financial data row
        # -------------------------
        financial_data_records.append({
            "Ticker": ticker,
            "Name": name,
            "Sector": sector,
            "Industry": industry,
            "Country": country,
            "Current Price": current_price,
            "Fair Value Per Share": fair_value_per_share,
            "Upside (%)": upside,
            "Margin of Safety (%)": margin_of_safety_pct,
            "Valuation": valuation,
            "EBIT": ebit,
            "Taxes": taxes,
            "Income Before Tax": income_before_tax,
            "Depreciation": depreciation,
            "CapEx": capex,
            "Change in WC": working_capital_change,
            "Interest Expense": interest_expense,
            "Total Debt": total_debt,
            "Cash Equivalents": cash_equivalents,
            "Shares Outstanding": shares_outstanding,
            "Market Cap": market_cap,
            "Current Assets": current_assets,
            "Current Liabilities": current_liabilities,
            "Net PPE": net_ppe,
            "Beta": beta,
            "WACC": wacc,
            "ROIC": roic,
            "Excess Returns": excess_returns,
            "FCFF": fcff,
            "Terminal Value": terminal_value,
            "Market Equity Value": market_equity_value
        })
        
        print(f"Saved DCF report and financial data for {ticker}")
        return None
        
    except Exception as e:
        return f"Error fetching data or calculating DCF for {ticker}: {e}"

# -----------------------------
# Safe wrapper
# -----------------------------
def safe_calculate_dcf(ticker: str):
    try:
        return calculate_dcf(ticker)
    except Exception as e:
        return f"Error for {ticker}: {e}"

# -----------------------------
# List of tickers 
# -----------------------------
tickers = []

max_threads = 5

# -----------------------------
# Main execution
# -----------------------------
if __name__ == "__main__":
    # Run DCF on all tickers in parallel
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        results = list(executor.map(safe_calculate_dcf, tickers))
    
    # Print errors
    for res in results:
        if isinstance(res, str) and "Error" in res:
            print(res)
    
    # -----------------------------
    # Save financial data CSV
    # -----------------------------
    if financial_data_records:
        df = pd.DataFrame(financial_data_records)
        file_path = os.path.join(financial_output_folder, "financial_data.csv")
        df.to_csv(file_path, index=False)
        print(f"\nAll financial data saved to {file_path}")
    
    print(f"All DCF reports saved in folder: {dcf_output_folder}")