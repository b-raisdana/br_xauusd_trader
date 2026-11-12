from math import isfinite
from typing import Literal

import MetaTrader5 as mt5

from application.strategy_v1.risk_models import Mt5RiskSnapshot


class Mt5RiskCalculator:
    def get_risk_snapshot(self, symbol: str) -> Mt5RiskSnapshot:
        account = mt5.account_info()
        symbol_info = mt5.symbol_info(symbol)
        if account is None:
            raise RuntimeError(f"MT5 account snapshot unavailable: {mt5.last_error()}")
        if symbol_info is None:
            raise RuntimeError(f"MT5 symbol snapshot unavailable for {symbol}: {mt5.last_error()}")
        account_currency = str(account.currency)
        if account_currency != "USD":
            raise ValueError(f"strategy risk budgets require USD account currency, got {account_currency}")

        return Mt5RiskSnapshot(
            symbol=symbol,
            account_currency=account_currency,
            equity_usd=float(account.equity),
            free_margin_usd=float(account.margin_free),
            point_size=float(symbol_info.point),
            tick_size=float(symbol_info.trade_tick_size),
            tick_value_usd=float(symbol_info.trade_tick_value),
            contract_size=float(symbol_info.trade_contract_size),
            volume_min_lots=float(symbol_info.volume_min),
            volume_max_lots=float(symbol_info.volume_max),
            volume_step_lots=float(symbol_info.volume_step),
            swap_long=float(symbol_info.swap_long),
            swap_short=float(symbol_info.swap_short),
            swap_mode=int(symbol_info.swap_mode),
        )

    def profit_at_stop_per_lot(
        self,
        symbol: str,
        direction: Literal["buy", "sell"],
        entry: float,
        stop: float,
    ) -> float:
        order_type = mt5.ORDER_TYPE_BUY if direction == "buy" else mt5.ORDER_TYPE_SELL
        result = mt5.order_calc_profit(order_type, symbol, 1.0, entry, stop)
        if result is None or not isfinite(float(result)):
            raise RuntimeError(f"MT5 profit calculation failed for {symbol}: {mt5.last_error()}")
        return float(result)

    def margin_per_lot(self, symbol: str, direction: Literal["buy", "sell"], entry: float) -> float:
        order_type = mt5.ORDER_TYPE_BUY if direction == "buy" else mt5.ORDER_TYPE_SELL
        result = mt5.order_calc_margin(order_type, symbol, 1.0, entry)
        if result is None or not isfinite(float(result)) or float(result) <= 0.0:
            raise RuntimeError(f"MT5 margin calculation failed for {symbol}: {mt5.last_error()}")
        return float(result)
