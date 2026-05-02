import os
from datetime import datetime
from typing import Dict
from colorama import init, Fore, Style
from config import TradingMode
from symbol_state import SymbolState

init(autoreset=True)

class ProfessionalDashboard:
    def __init__(self):
        self.last_update = None

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def create_header(self, account_info) -> str:
        lines = [
            Fore.CYAN + "=" * 120,
            Fore.WHITE + "Trading Bot".center(120),
            Fore.CYAN + "=" * 120,
            (
                f"Account: {account_info.login} | "
                f"Balance: {account_info.balance:.2f} {account_info.currency} | "
                f"Equity: {account_info.equity:.2f} {account_info.currency} | "
                f"Free Margin: {account_info.margin_free:.2f} {account_info.currency}"
            ),
            Fore.CYAN + "=" * 120,
        ]
        return "\n".join(lines)

    def color_text(self, text: str, color: str, width: int, align: str = "<") -> str:
        if align == "<":
            padded = f"{text:<{width}}"
        elif align == ">":
            padded = f"{text:>{width}}"
        else:
            padded = f"{text:^{width}}"
        return f"{color}{padded}{Style.RESET_ALL}"

    def _get_status_color(self, enabled: bool) -> str:
        return Fore.GREEN if enabled else Fore.RED

    def _get_mode_color(self, mode: TradingMode) -> str:
        if mode == TradingMode.BUY_ONLY:
            return Fore.GREEN
        return Fore.RED

    def _get_signal_color(self, signal: str) -> str:
        if signal == "BUY":
            return Fore.GREEN
        elif signal == "SELL":
            return Fore.RED
        return Fore.YELLOW

    def _get_forecast_color(self, forecast: float) -> str:
        if forecast > 0:
            return Fore.GREEN
        elif forecast < 0:
            return Fore.RED
        return Fore.YELLOW

    def _get_trend_color(self, trend: str) -> str:
        if trend == "BULLISH":
            return Fore.GREEN
        elif trend == "BEARISH":
            return Fore.RED
        return Fore.YELLOW

    def _get_position_color(self, position_type) -> str:
        if position_type and str(position_type) == "LONG":
            return Fore.GREEN
        elif position_type and str(position_type) == "SHORT":
            return Fore.RED
        return Fore.YELLOW

    def _get_action_color(self, action: str) -> str:
        if action == "ENTER":
            return Fore.GREEN
        elif action == "EXIT":
            return Fore.RED
        return Fore.YELLOW

    def _total_width(self, col_widths):
        return sum(col_widths.values()) + len(col_widths) - 1

    def create_live_signals(self, symbol_states: Dict[str, SymbolState]) -> str:
        col_widths = {
            "symbol": 12,
            "status": 8,
            "mode": 10,
            "tf": 6,       
            "price": 14,
            "signal": 10,
            "forecast": 10,
            "trend": 10,
            "position": 10,
        }

        separator = Fore.CYAN + "-" * self._total_width(col_widths)

        # HEADER with Status column
        header = (
            f"{'Symbol':<{col_widths['symbol']}} "
            f"{'Status':<{col_widths['status']}} "
            f"{'Mode':<{col_widths['mode']}} "
            f"{'TF':<{col_widths['tf']}} "
            f"{'Price':>{col_widths['price']}} "
            f"{'Signal':<{col_widths['signal']}} "
            f"{'Forecast':>{col_widths['forecast']}} "
            f"{'Trend':<{col_widths['trend']}} "
            f"{'Position':<{col_widths['position']}} "
        )

        lines = [
            "\nLIVE TRADING SIGNALS",
            separator,
            header,
            separator,
        ]

        for symbol, state in symbol_states.items():
            # Status column
            status = "ENABLED" if state.config.enabled else "DISABLED"
            status_color = self._get_status_color(state.config.enabled)
            
            mode = state.config.mode
            mode_color = self._get_mode_color(mode)

            tf_str = state.config.timeframe.value

            price = state.current_price
            price_color = Fore.GREEN if state.price_change_pct >= 0 else Fore.RED

            signal = state.current_signal.value
            signal_color = self._get_signal_color(signal)

            forecast = state.current_forecast
            forecast_color = self._get_forecast_color(forecast)

            trend = state.current_trend
            trend_color = self._get_trend_color(trend)

            if state.position_state.has_position:
                position = state.position_state.position_type.value
                position_color = self._get_position_color(state.position_state.position_type)
            else:
                position = "NONE"
                position_color = Fore.YELLOW

            action = state.get_desired_action()
            action_color = self._get_action_color(action)

            line = (
                f"{symbol:<{col_widths['symbol']}} "
                f"{self.color_text(status, status_color, col_widths['status'])} "
                f"{self.color_text(mode.value, mode_color, col_widths['mode'])} "
                f"{tf_str:<{col_widths['tf']}} "
                f"{self.color_text(f'{price:.5f}', price_color, col_widths['price'], '>')} "
                f"{self.color_text(signal, signal_color, col_widths['signal'])} "
                f"{self.color_text(f'{forecast:.2f}', forecast_color, col_widths['forecast'], '>')} "
                f"{self.color_text(trend, trend_color, col_widths['trend'])} "
                f"{self.color_text(position, position_color, col_widths['position'])} "
            )

            lines.append(line)

        lines.append(separator)
        return "\n".join(lines)

    def update(self, account_info, symbol_states: Dict[str, SymbolState]):
        output = [
            self.create_header(account_info),
            self.create_live_signals(symbol_states),
            f"\nLast Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Ctrl+C to stop",
            Fore.CYAN + "=" * 120,
        ]

        self.clear_screen()
        print("\n".join(output))
        self.last_update = datetime.now()