""" Order execution and position management. """
import time
from typing import Optional, Dict, List
import MetaTrader5 as mt5
from datetime import datetime
import logging
from models import Trade
from signal import SignalType, PositionType
from config import SystemConfig

logger = logging.getLogger(__name__)

class OrderManager:
    """ Manages all order execution activities including entries, exits, position tracking, and retry logic. """
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.open_positions: Dict[str, Trade] = {}
        self.trade_history: List[Trade] = []
    
    def initialize(self) -> bool:
        """Initialize MT5 connection."""
        if not mt5.initialize():
            logger.error("Failed to initialize MT5")
            return False
        logger.info("MT5 initialized successfully")
        return True
    
    def shutdown(self) -> None:
        """Shutdown MT5 connection."""
        mt5.shutdown()
        logger.info("MT5 connection closed")
    
    def get_account_info(self):
        """Get current account information."""
        return mt5.account_info()
    
    def get_current_price(self, symbol: str) -> float:
        """ Get current mid price for symbol. """
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            logger.warning(f"No tick data for {symbol}")
            return 0.0
        return (tick.bid + tick.ask) / 2
    
    def place_order(
        self,
        symbol: str,
        signal_type: SignalType,
        volume: float,
        strategy_name: str,
    ) -> Optional[int]:
        """ Place a market order. """
        # Ensure symbol is available
        if not mt5.symbol_info(symbol) or not mt5.symbol_info(symbol).visible:
            if not mt5.symbol_select(symbol, True):
                logger.error(f"Cannot select symbol {symbol}")
                return None
        
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            logger.error(f"No tick data for {symbol}")
            return None
        
        is_buy = signal_type == SignalType.BUY
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
            "price": tick.ask if is_buy else tick.bid,
            "deviation": 10,
            "magic": self.config.magic_number,
            "comment": f"{strategy_name} | {self.config.magic_number}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        
        # Retry logic
        for attempt in range(self.config.max_retries):
            result = mt5.order_send(request)
            if result is None:
                logger.error(f"order_send returned None for {symbol}")
                time.sleep(self.config.retry_delay)
                continue
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                trade = Trade(
                    ticket=result.order,
                    symbol=symbol,
                    signal_type=signal_type,
                    position_type=PositionType.LONG if is_buy else PositionType.SHORT,
                    entry_price=request['price'],
                    entry_time=datetime.now(),
                    volume=volume,
                    strategy=strategy_name,
                )
                self.trade_history.append(trade)
                self.open_positions[symbol] = trade
                logger.info(
                    f"OPEN POSITION | {signal_type.value} {volume} {symbol} "
                    f"@ {request['price']:.5f} | Ticket: {result.order}"
                )
                return result.order
            
            logger.warning(
                f"Order attempt {attempt + 1}/{self.config.max_retries} "
                f"failed for {symbol}: {result.comment} (retcode={result.retcode})"
            )
            time.sleep(self.config.retry_delay)
        
        logger.error(f"Order failed after {self.config.max_retries} attempts for {symbol}")
        return None
    
    def close_position(self, symbol: str) -> bool:
        """ Close all positions for a symbol. """
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            self.open_positions[symbol] = None
            return True
        
        for pos in positions:
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                logger.error(f"No tick data for {symbol} on close")
                return False
            
            is_long = pos.type == 0  # 0 = BUY, 1 = SELL
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": pos.volume,
                "type": mt5.ORDER_TYPE_SELL if is_long else mt5.ORDER_TYPE_BUY,
                "position": pos.ticket,
                "price": tick.bid if is_long else tick.ask,
                "deviation": 10,
                "magic": self.config.magic_number,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
            
            # Retry logic for close
            for attempt in range(self.config.max_retries):
                result = mt5.order_send(request)
                if result is None:
                    logger.error(f"close_order_send returned None for {symbol}")
                    time.sleep(self.config.retry_delay)
                    continue
                
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    logger.warning(
                        f"Close attempt {attempt + 1} failed for {symbol}: "
                        f"{result.comment} (retcode={result.retcode})"
                    )
                    time.sleep(self.config.retry_delay)
                    continue
                
                # Update trade record
                trade = self.open_positions.get(symbol)
                if trade:
                    trade.exit_price = request['price']
                    trade.exit_time = datetime.now()
                    # Calculate profit (simplified P&L)
                    if trade.position_type == PositionType.LONG:
                        trade.profit = (trade.exit_price - trade.entry_price) * trade.volume * 100000
                    else:
                        trade.profit = (trade.entry_price - trade.exit_price) * trade.volume * 100000
                
                self.open_positions[symbol] = None
                logger.info(
                    f"CLOSE POSITION | {symbol} @ {request['price']:.5f} "
                    f"| Ticket: {pos.ticket}"
                )
                return True
        
        logger.error(f"Failed to close position for {symbol} after {self.config.max_retries} attempts")
        return False
    
    def sync_positions(self, symbols: List[str]) -> None:
        """ Synchronize tracked positions with actual MT5 positions. """
        for symbol in symbols:
            positions = mt5.positions_get(symbol=symbol)
            if not positions:
                if self.open_positions.get(symbol) is not None:
                    logger.info(f"Sync: {symbol} closed externally")
                    self.open_positions[symbol] = None
            else:
                if self.open_positions.get(symbol) is None:
                    pos = positions[0]
                    trade = Trade(
                        ticket=pos.ticket,
                        symbol=symbol,
                        signal_type=SignalType.BUY if pos.type == 0 else SignalType.SELL,
                        position_type=PositionType.LONG if pos.type == 0 else PositionType.SHORT,
                        entry_price=pos.price_open,
                        entry_time=datetime.fromtimestamp(pos.time),
                        volume=pos.volume,
                        strategy="Unknown",
                    )
                    self.open_positions[symbol] = trade
                    logger.info(f"Sync: Adopted untracked {symbol} position")
    
    def validate_reversal(self, symbol: str) -> bool:
        """ Validate if a reversal is justified to avoid excessive losses. """
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return True
        
        pos = positions[0]
        floating_pnl = pos.profit
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return False
        
        spread_cost = (tick.ask - tick.bid) * pos.volume * 100000
        min_acceptable_loss = -2.0 * spread_cost
        is_justified = floating_pnl >= min_acceptable_loss
        
        if not is_justified:
            logger.info(
                f"{symbol}: Reversal blocked - PnL={floating_pnl:.2f}, "
                f"spread_cost={spread_cost:.2f}, min_acceptable={min_acceptable_loss:.2f}"
            )
        
        return is_justified