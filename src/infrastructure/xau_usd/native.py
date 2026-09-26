from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol

from archive_not_used_trash.xauusd_trading_strategy_1 import XauNativeDealOutcome, XauNativeSymbol

from domain.xau_usd.enums import XauExecutionEvent


class NativeBroker(Protocol):
    def symbol_info(self, symbol: str) -> XauNativeSymbol | None: ...
    def deal_outcome(
        self, deal_ticket: int, order_ticket: int, symbol: str, magic: int
    ) -> XauNativeDealOutcome | None: ...
    def cash_risk(self, order_type: str, symbol: str, volume: float, entry: float, stop: float) -> float | None: ...
    def required_margin(self, order_type: str, symbol: str, volume: float, entry: float) -> float | None: ...
    def containing_trade_session(self, symbol: str, broker_now: datetime) -> tuple[datetime, datetime] | None: ...


def classify_native_deal_entry(entry: int | str) -> XauExecutionEvent | None:
    if isinstance(entry, str):
        normalized = entry.upper()
        if normalized == "IN":
            return XauExecutionEvent.FILL
        if normalized in {"OUT", "OUT_BY"}:
            return XauExecutionEvent.CLOSE
        return None

    if entry == 0:
        return XauExecutionEvent.FILL
    if entry in {1, 2}:
        return XauExecutionEvent.CLOSE
    return None


def native_seconds_of_day(value: datetime) -> int:
    return value.hour * 3600 + value.minute * 60 + value.second


def native_containing_trade_session(
    broker_now: datetime,
    sessions: dict[str, list[tuple[datetime, datetime]]],
) -> tuple[datetime, datetime] | None:
    day_start = broker_now.replace(hour=0, minute=0, second=0)
    for day_offset in (-1, 0):
        day_key = (day_start + timedelta(days=day_offset)).date().isoformat()
        for session_from, session_to in sessions.get(day_key, []):
            if session_from <= broker_now < session_to:
                return session_from, session_to
    return None


class Mt5NativeAdapter:
    def symbol_info(self, symbol: str) -> XauNativeSymbol | None:
        try:
            import MetaTrader5 as mt5
        except ImportError:
            return None

        digits = mt5.SymbolInfoInteger(symbol, mt5.SYMBOL_DIGITS)
        point = mt5.SymbolInfoDouble(symbol, mt5.SYMBOL_POINT)
        volume_min = mt5.SymbolInfoDouble(symbol, mt5.SYMBOL_VOLUME_MIN)
        volume_max = mt5.SymbolInfoDouble(symbol, mt5.SYMBOL_VOLUME_MAX)
        volume_step = mt5.SymbolInfoDouble(symbol, mt5.SYMBOL_VOLUME_STEP)
        if digits < 0 or point <= 0.0 or volume_min <= 0.0 or volume_max < volume_min or volume_step <= 0.0:
            return None
        return XauNativeSymbol(
            digits=int(digits),
            point=float(point),
            volume_min=float(volume_min),
            volume_max=float(volume_max),
            volume_step=float(volume_step),
        )

    def deal_outcome(self, deal_ticket: int, order_ticket: int, symbol: str, magic: int) -> XauNativeDealOutcome | None:
        try:
            import MetaTrader5 as mt5
        except ImportError:
            return None

        if deal_ticket <= 0 or magic <= 0 or not mt5.HistoryDealSelect(0, 2**63 - 1):
            return None
        selected_ticket = -1
        for index in range(mt5.HistoryDealsTotal()):
            candidate = mt5.HistoryDealGetTicket(index)
            if candidate == deal_ticket:
                selected_ticket = candidate
                break
        if selected_ticket != deal_ticket:
            return None
        if (
            mt5.HistoryDealGetString(selected_ticket, mt5.DEAL_SYMBOL) != symbol
            or mt5.HistoryDealGetInteger(selected_ticket, mt5.DEAL_MAGIC) != magic
        ):
            return None

        event_kind = classify_native_deal_entry(mt5.HistoryDealGetInteger(selected_ticket, mt5.DEAL_ENTRY))
        price = float(mt5.HistoryDealGetDouble(selected_ticket, mt5.DEAL_PRICE))
        broker_time = datetime.fromtimestamp(
            int(mt5.HistoryDealGetInteger(selected_ticket, mt5.DEAL_TIME)),
            tz=timezone.utc,
        )
        position_id = int(mt5.HistoryDealGetInteger(selected_ticket, mt5.DEAL_POSITION_ID))
        if event_kind is None or price <= 0.0 or broker_time.timestamp() <= 0 or position_id <= 0:
            return None

        return XauNativeDealOutcome(
            deal_ticket=deal_ticket,
            order_ticket=order_ticket,
            position_id=position_id,
            event_kind=event_kind,
            price=price,
            broker_time=broker_time,
        )

    def cash_risk(self, order_type: str, symbol: str, volume: float, entry: float, stop: float) -> float | None:
        try:
            import MetaTrader5 as mt5
        except ImportError:
            return None

        if volume <= 0.0 or entry <= 0.0 or stop <= 0.0:
            return None
        mt5_type = getattr(mt5, f"ORDER_TYPE_{order_type.upper()}")
        profit = mt5.OrderCalcProfit(mt5_type, symbol, volume, entry, stop)
        return abs(float(profit)) if profit else None

    def required_margin(self, order_type: str, symbol: str, volume: float, entry: float) -> float | None:
        try:
            import MetaTrader5 as mt5
        except ImportError:
            return None

        if volume <= 0.0 or entry <= 0.0:
            return None
        mt5_type = getattr(mt5, f"ORDER_TYPE_{order_type.upper()}")
        margin = mt5.OrderCalcMargin(mt5_type, symbol, volume, entry)
        return float(margin) if margin is not None else None

    def containing_trade_session(self, symbol: str, broker_now: datetime) -> tuple[datetime, datetime] | None:
        try:
            import MetaTrader5 as mt5
        except ImportError:
            return None

        day_start = datetime.combine(broker_now.date(), datetime.min.time())
        for day_offset in (-1, 0):
            current_day = day_start + timedelta(days=day_offset)
            weekday = current_day.weekday()
            for index in range(32):
                result = mt5.SymbolInfoSessionTrade(symbol, weekday, index)
                if result is None:
                    break

                if isinstance(result, tuple) and len(result) == 3:
                    available, session_from, session_to = result
                    if not available:
                        break
                elif isinstance(result, tuple) and len(result) == 2:
                    session_from, session_to = result
                else:
                    continue

                absolute_from = datetime.utcfromtimestamp(float(session_from))
                absolute_to = datetime.utcfromtimestamp(float(session_to))
                if broker_now >= absolute_from and broker_now < absolute_to:
                    return absolute_from, absolute_to
        return None
