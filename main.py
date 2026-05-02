import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
import time
from colorama import Fore, Style
from config import load_config
from bot import TradingBot

def setup_logging(log_to_file: bool = True):
    handlers = [logging.StreamHandler()]
    if log_to_file:
        handlers.append(logging.FileHandler('trading_bot.log'))
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

def print_banner():
    """Print startup banner."""
    banner = f"""
{Fore.CYAN}{'=' * 100}
{Fore.WHITE}{'Trading Bot'.center(100)}
{Fore.CYAN}{'Kabelo Junior Mosaka'.center(100)}
{Fore.CYAN}{'=' * 100}{Style.RESET_ALL}
"""
    print(banner)

def main():
    """Main entry point."""
    print_banner()
    print("\nInitializing trading system...\n")
    time.sleep(2)
    
    # Load configuration
    config = load_config()
    
    # Setup logging
    setup_logging(config.log_to_file)
    logger = logging.getLogger(__name__)
    
    logger.info("Trading Bot - BUY_ONLY & SELL_ONLY Mode")
    
    # Print configuration summary with status
    print(f"\n{Fore.CYAN}Configuration Summary:{Style.RESET_ALL}")
    enabled_count = 0
    for symbol, sym_config in config.symbols.items():
        status = "ENABLED" if sym_config.enabled else "DISABLED"
        status_color = Fore.GREEN if sym_config.enabled else Fore.RED
        print(
            f"  {symbol}: {status_color}{status}{Style.RESET_ALL}, "
            f"Mode={sym_config.mode.value}, Lot={sym_config.lot_size}, TF={sym_config.timeframe.value}"
        )
        if sym_config.enabled:
            enabled_count += 1
    
    print(f"\n{Fore.GREEN}{enabled_count} symbols ENABLED for trading{Style.RESET_ALL}")
    print()
    
    # Create and run bot
    bot = None
    try:
        bot = TradingBot(config)
        bot.run()
    except KeyboardInterrupt:
        print("\n\nShutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        if bot:
            bot.shutdown()
    
    print(f"\n{Fore.GREEN}Trading bot stopped successfully{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
    