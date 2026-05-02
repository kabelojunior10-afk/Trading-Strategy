# EWMAC Trading Bot — ACM

> **Exponentially Weighted Moving Average Crossover** — A volatility-adjusted, systematic trend-following trading bot for MetaTrader 5, with a matching TradingView Pine Script indicator.
> 
## Overview

This repository contains the full source code for the **EWMAC algorithmic trading system** developed by [Amare Capital Management (Pty) Ltd]. The system runs a two-layer architecture:

| Layer | Tool | Role |
|-------|------|------|
|  Human Analyst | TradingView (Pine Script) | Visual signal monitoring & discretionary override |
|  Machine | Python + MetaTrader 5 | Autonomous signal calculation & order execution |

Both layers are mathematically identical — the Pine Script indicator and the Python strategy engine produce the exact same EWMAC forecast, ensuring no divergence between what the analyst sees and what the bot trades.

---

##  Strategy: How EWMAC Works

The **Exponentially Weighted Moving Average Crossover (EWMAC)** is a classical institutional momentum strategy that generates a *volatility-adjusted, capped forecast* instead of a raw crossover signal.

### Signal Pipeline

```
Close Prices
    │
    ├─► Fast EWMA (span=16)  ─┐
    │                          ├─► Raw EWMAC = Fast − Slow
    └─► Slow EWMA (span=64)  ─┘
                                        │
                        ┌───────────────▼────────────────┐
                        │  Volatility = √(EMA(ret², 25)) │
                        └───────────────┬────────────────┘
                                        │
                              Vol-Adjusted = Raw / Vol
                                        │
                              Scalar = 10 / √(16) ≈ 2.5
                                        │
                              Forecast = Vol-Adjusted × Scalar
                                        │
                        ┌───────────────▼────────────────┐
                        │   Capped Forecast ∈ [−20, +20] │
                        └───────────────┬────────────────┘
                                        │
                     ┌──────────────────┼──────────────────┐
                     ▼                  ▼                   ▼
              forecast ≥ +10    −10 < forecast < +10   forecast ≤ −10
                  BUY                 HOLD                  SELL
```

### Trading Thresholds

| Condition | Action |
|-----------|--------|
| `capped_forecast ≥ +10` | **BUY** — enter / hold long |
| `capped_forecast ≤ −10` | **SELL** — enter / hold short |
| `-10 < capped_forecast < +10` | **NEUTRAL** — hold / exit |

---

## Repository Structure

```
trading-bot/
│
├── main.py               # Entry point — initialises and runs the bot
├── bot.py                # TradingBot orchestrator — main trading loop
├── ewmac.py              # EWMAC strategy — signal calculation engine
├── strategy_base.py      # Abstract Strategy base class
├── signal.py             # SignalType & PositionType enums
├── models.py             # Trade, SignalData, PositionState dataclasses
├── config.py             # All configuration (strategy, symbols, risk)
├── order_manager.py      # MT5 order execution & position management
├── data_provider.py      # MT5 historical data fetcher
├── symbol_state.py       # Per-symbol state machine & trading logic
├── dashboard.py          # Live terminal dashboard (colorama)
│
└── tradingview/
    └── ewmac_indicator.pine   # TradingView Pine Script v6 indicator
```

---

## Module Reference

### `strategy_base.py` — Abstract Interface
Defines the contract that all strategies must implement. Enables clean swap-in of future strategies without touching the rest of the system.

```python
class Strategy(ABC):
    def calculate(df)         -> pd.DataFrame      # compute indicators
    def get_signal(df)        -> (SignalType, float) # signal + forecast
    def get_trend(forecast)   -> str               # BULLISH/BEARISH/NEUTRAL
    def get_strategy_name()   -> str               # identifier
```

---

### `ewmac.py` — Strategy Engine
The mathematical core. Replicates Pine Script calculations exactly using `pandas` and `NumPy`. Uses `.ewm(span=n, adjust=False)` to match TradingView's `ta.ema()` behaviour precisely.

```python
# Key calculation steps
df["fast_ewma"]      = close.ewm(span=16, adjust=False).mean()
df["slow_ewma"]      = close.ewm(span=64, adjust=False).mean()
df["raw_ewmac"]      = fast_ewma - slow_ewma
df["vol"]            = sqrt(ret_squared.ewm(span=25, adjust=False).mean())
df["vol_adj"]        = raw_ewmac / vol
df["forecast"]       = vol_adj * (10.0 / sqrt(fast_length))
df["capped_forecast"]= forecast.clip(-20, 20)
```

**Look-ahead bias prevention**: `get_signal()` uses `df.iloc[-2]` (the last *completed* candle), never the live forming candle.

---

### `signal.py` — Type-Safe Signal Representation

```python
class SignalType(Enum):   BUY | SELL | NEUTRAL
class PositionType(Enum): LONG | SHORT | NONE
```

Using enums prevents silent bugs from string comparisons (`"buy"` vs `"BUY"` vs `"Buy"`).

---

### `models.py` — Data Structures

| Class | Purpose |
|-------|---------|
| `Trade` | Full record of an executed trade (entry, exit, P&L, ticket) |
| `SignalData` | Snapshot of signal + forecast + trend at a point in time |
| `PositionState` | Current live position for a symbol (`PositionState.empty()` for flat) |

---

### `config.py` — Configuration

All parameters are centralised in typed `dataclass` objects. The `StrategyConfig` defaults **exactly match** the Pine Script indicator inputs:

```python
@dataclass
class StrategyConfig:
    fast_length:    int   = 16       # Pine: Lfast
    slow_length:    int   = 64       # Pine: Lslow
    vol_lookback:   int   = 25       # Pine: vol_lookback
    cap_min:        float = -20.0    # Pine: capmin
    cap_max:        float = 20.0     # Pine: capmax
    buy_threshold:  float = 10.0     # Pine: buy_thresh
    sell_threshold: float = -10.0    # Pine: sell_thresh

    @property
    def f_scalar(self) -> float:
        return 10.0 / math.sqrt(self.fast_length)  # Pine: 10.0 / math.sqrt(Lfast)
```

#### Per-Symbol Configuration

```python
SymbolConfig(
    symbol   = "GOLD",
    mode     = TradingMode.BUY_ONLY,   # or SELL_ONLY
    enabled  = True,
    lot_size = 0.01,
    timeframe= TimeFrame.M15,          # M1 | M5 | M15 | H1
    max_daily_trades = 5,              # optional daily cap
)
```

---

### `order_manager.py` — MT5 Execution

Handles all communication with MetaTrader 5:

- **Place orders** — market buy/sell with configurable deviation and magic number
- **Close positions** — closes by ticket with retry logic
- **Sync positions** — reconciles internal state with actual MT5 positions on every cycle
- **Reversal validation** — blocks reversals where floating loss exceeds `2 × spread_cost`

```python
# Retry logic on every order
for attempt in range(max_retries):
    result = mt5.order_send(request)
    if result.retcode == TRADE_RETCODE_DONE:
        break
    time.sleep(retry_delay)
```

---

### `symbol_state.py` — State Machine

Each symbol runs its own state machine. Entry/exit logic:

```python
# BUY_ONLY: long when forecast ≥ +10, exit when forecast drops below +10
# SELL_ONLY: short when forecast ≤ −10, exit when forecast rises above −10

def get_desired_action() -> "ENTER" | "EXIT" | "HOLD"
```

Built-in protections:
- Cooldown timers between open/close attempts (scales with timeframe)
- Daily trade counter with midnight reset
- Position deduplication (max 1 position per symbol by default)

---

### `bot.py` — Main Trading Loop

```
Loop (every poll_interval seconds):
  1. Fetch account info from MT5
  2. Sync all symbol positions with MT5
  3. For each enabled symbol:
     a. Get current price
     b. Fetch historical candles (DataProvider)
     c. If new candle closed → recalculate EWMAC signal
     d. Execute ENTER / EXIT / HOLD action
  4. Update live dashboard
  5. Sleep
```

---

### `data_provider.py` — Market Data

Fetches OHLCV data from MT5 using `mt5.copy_rates_from_pos()`. Returns a `pandas.DataFrame` with a `datetime` index. Bars fetched per timeframe:

| Timeframe | Bars Fetched |
|-----------|-------------|
| M1  | 300 |
| M5  | 400 |
| M15 | 500 |
| H1  | 600 |

---

### `dashboard.py` — Live Terminal Display

Coloured terminal dashboard updated every polling cycle using `colorama`:

```
════════════════════════════════════════════════════════════════════
                          Trading Bot
════════════════════════════════════════════════════════════════════
Account: 12345 | Balance: 10,000.00 USD | Equity: 10,124.50 USD

LIVE TRADING SIGNALS
──────────────────────────────────────────────────────────────────
Symbol       Status    Mode        TF    Price          Signal    Forecast    Trend       Position
──────────────────────────────────────────────────────────────────
GOLD         ENABLED   BUY_ONLY    M15   2,345.12000    BUY       +12.45      BULLISH     LONG
BTCUSD       ENABLED   SELL_ONLY   M15   67,234.50000   NEUTRAL   -3.21       BEARISH     NONE
```

---

## Getting Started

### Prerequisites

- Python 3.9+
- MetaTrader 5 terminal installed and logged in
- A broker account accessible via MT5
- TradingView 

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/ewmac-trading-bot.git
cd ewmac-trading-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Requirements (`requirements.txt`)

```
MetaTrader5>=5.0.45
pandas>=2.0.0
numpy>=1.24.0
colorama>=0.4.6
```

### Configuration

Edit `config.py` to enable your symbols and set parameters:

```python
DEFAULT_SYMBOLS_CONFIG = {
    "GOLD": SymbolConfig(
        symbol    = "GOLD",
        mode      = TradingMode.BUY_ONLY,
        enabled   = True,          # ← set to True to activate
        lot_size  = 0.01,
        timeframe = TimeFrame.M15,
    ),
}
```

### Run

```bash
python main.py
```

---

## TradingView Indicator

The Pine Script indicator (`tradingview/ewmac_indicator.pine`) is a companion visual tool for TradingView. Add it to any chart to see:

- **Fast EWMA** on the price chart (green in bull, red in bear)
- **Slow EWMA** as the baseline trend reference
- **Capped Forecast Oscillator** in a separate pane (green above +10, red below −10)
- **Buy/Sell signal markers** at the exact threshold crossing
- **HUD table** displaying the current forecast value

To install: open TradingView → Pine Editor → paste the script → Add to chart.

---

##  Risk Disclaimer

> This software is provided for **educational and informational purposes**. Algorithmic trading involves substantial risk of financial loss. Past performance does not guarantee future results. Always test thoroughly on a **demo account** before any live deployment. The authors accept no liability for trading losses.

---

##  About

Developed and maintained by **Kabelo Junior Mosaka** at [Amare Capital Management (Pty) Ltd]() — a South African proprietary trading firm combining systematic strategies with discretionary expertise.

---

*© 2026 Amare Capital Management (Pty) Ltd. All rights reserved.*
