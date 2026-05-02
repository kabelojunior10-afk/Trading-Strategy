import time
import logging
from typing import Dict
from datetime import datetime
from config import SystemConfig, SymbolConfig, TradingMode, TimeFrame, TIMEFRAME_META
from ewmac import EWMACStrategy
from order_manager import OrderManager
from data_provider import DataProvider
from dashboard import ProfessionalDashboard
from signal import SignalType, PositionType
from symbol_state import SymbolState
from models import PositionState, SignalData

logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self, config: SystemConfig):
        self.config = config
        self.strategy = EWMACStrategy(config.strategy)
        self.order_manager = OrderManager(config)
        self.data_provider = DataProvider()
        self.dashboard = ProfessionalDashboard() if config.enable_dashboard else None
        
        self.symbol_states: Dict[str, SymbolState] = {}
        
        enabled_symbols = {k: v for k, v in config.symbols.items() if v.enabled}
        for symbol, symbol_config in enabled_symbols.items():
            self.symbol_states[symbol] = SymbolState(symbol_config)
        
        # Connect to MT5
        if not self.order_manager.initialize():
            raise ConnectionError("Failed to initialize trading system")
        
        logger.info(f"Trading bot initialized with {len(enabled_symbols)} ENABLED symbols: {list(enabled_symbols.keys())}")
    
    def run(self):
        logger.info("Starting trading bot main loop")
        while True:
            try:
                loop_start = time.time()
                
                account_info = self.order_manager.get_account_info()
                if not account_info:
                    logger.warning("Failed to get account info")
                    time.sleep(5)
                    continue
                
                self._process_all_symbols()
                
                if self.dashboard and account_info:
            
                    all_states = {}
                    for symbol, config in self.config.symbols.items():
                        if symbol in self.symbol_states:
                            all_states[symbol] = self.symbol_states[symbol]
                        else:
                        
                            dummy_state = SymbolState(config)
                            dummy_state.current_price = self.order_manager.get_current_price(symbol)
                            all_states[symbol] = dummy_state
                    self.dashboard.update(account_info, all_states)
                
                elapsed = time.time() - loop_start
                sleep_time = max(1, self.config.poll_interval - elapsed)
                time.sleep(sleep_time)
                
            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                break
            except Exception as e:
                logger.error(f"Main loop error: {e}", exc_info=True)
                time.sleep(5)
        
        self.shutdown()
    
    def _process_all_symbols(self):
        enabled_symbols = list(self.symbol_states.keys())
        
        self.order_manager.sync_positions(enabled_symbols)
        
        for symbol in enabled_symbols:
            state = self.symbol_states[symbol]
            trade = self.order_manager.open_positions.get(symbol)
            if trade:
                state.position_state = PositionState(
                    has_position=True,
                    position_type=trade.position_type,
                    ticket=trade.ticket,
                    entry_price=trade.entry_price,
                    volume=trade.volume,
                )
            else:
                state.position_state = PositionState.empty()
        
        for symbol in enabled_symbols:
            state = self.symbol_states[symbol]
            self._process_symbol(symbol, state)
    
    def _process_symbol(self, symbol: str, state: SymbolState):
        price = self.order_manager.get_current_price(symbol)
        if price == 0:
            logger.warning(f"No price data for {symbol}")
            return
        
        state.current_price = price
        if state.last_price > 0:
            state.price_change_pct = ((price - state.last_price) / state.last_price) * 100
        state.last_price = price
        
        bars_needed = TIMEFRAME_META[state.config.timeframe]["bars"]
        df = self.data_provider.get_historical_data(
            symbol,
            state.config.timeframe,
            bars_needed
        )
        
        if df.empty:
            logger.warning(f"No historical data for {symbol}")
            return
        
        current_candle_time = df.index[-1]
        is_new_candle = current_candle_time != state.last_candle_time
        
        if is_new_candle:
            state.last_candle_time = current_candle_time
            
            df_ewmac = self.strategy.calculate(df)
            
            ewmac_signal, ewmac_forecast = self.strategy.get_signal(df_ewmac)
            
            ewmac_trend = self.strategy.get_trend(ewmac_forecast)
            
            signal_data = SignalData(
                signal=ewmac_signal,
                forecast=ewmac_forecast,
                trend=ewmac_trend,
                timestamp=datetime.now()
            )
            state.update_signal(signal_data)
            
            logger.debug(
                f"{symbol} | Signal: {ewmac_signal.value} | "
                f"Forecast: {ewmac_forecast:.2f} | Trend: {ewmac_trend}"
            )
            
            self._execute_trading_actions(symbol, state)
    
    def _execute_trading_actions(self, symbol: str, state: SymbolState):
        action = state.get_desired_action()
        
        if action == "EXIT":
            if state.can_close_position():
                state.last_close_attempt = time.time()
                logger.info(f"{symbol}: EXIT - Closing {state.position_state.position_type.value}")
                self.order_manager.close_position(symbol)
                
        elif action == "ENTER":
            if state.can_open_position(state.config):
                state.last_open_attempt = time.time()
                logger.info(f"{symbol}: ENTER - {state.current_signal.value} (Forecast: {state.current_forecast:.2f})")
                self._open_position(symbol, state)
        else:  # HOLD
            pass
    
    def _open_position(self, symbol: str, state: SymbolState):
        signal = state.current_signal
        if signal == SignalType.NEUTRAL:
            return
        
        lot_size = state.config.lot_size
        ticket = self.order_manager.place_order(
            symbol,
            signal,
            lot_size,
            self.strategy.get_strategy_name()
        )
        
        if ticket:
            state.daily_trades += 1
            logger.info(f"{symbol}: Position opened successfully - Ticket: {ticket}")
        else:
            logger.error(f"{symbol}: Failed to open position")
    
    def shutdown(self):
        """Gracefully shutdown the bot."""
        logger.info("Shutting down trading bot...")
        self.order_manager.shutdown()
        logger.info("Trading bot shutdown complete")