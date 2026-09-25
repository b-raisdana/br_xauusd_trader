from __future__ import annotations

from typing import Literal, Protocol, TypedDict

from application.xauusd_trading_strategy_1.domain.models import XauPreparedEntry, XauTesterSubmission
from domain.xau_usd.enums import XauDirection, XauEntryRejection, XauOrderType


class EntryTradeRequest(TypedDict):
    action: Literal["DEAL", "PENDING"]
    symbol: str
    magic: int
    volume: float
    sl: float
    tp: float
    direction: Literal["BUY", "SELL"]
    price: float


class ProtectionTradeRequest(TypedDict):
    action: Literal["SLTP"]
    symbol: str
    magic: int
    position: int
    sl: float
    tp: float


class CloseTradeRequest(TypedDict):
    action: Literal["DEAL"]
    symbol: str
    magic: int
    position: int
    volume: float
    direction: Literal["BUY", "SELL"]
    price: float


TradeRequest = EntryTradeRequest | ProtectionTradeRequest | CloseTradeRequest


class TradeRequestSender(Protocol):
    def send(self, request: TradeRequest) -> tuple[int, int, int]: ...


def tester_execution_allowed(enabled: bool, is_tester: bool, magic: int, symbol: str) -> bool:
    return enabled and is_tester and magic > 0 and bool(symbol)


def tester_retcode_accepted(retcode: int) -> bool:
    return retcode in {0, 1, 2}


def native_filling_policy(flags: int) -> Literal["FOK", "IOC", "RETURN"]:
    if flags & 1:
        return "FOK"
    if flags & 2:
        return "IOC"
    return "RETURN"


class Mt5TesterBroker:
    def __init__(self, sender: TradeRequestSender) -> None:
        self.sender = sender

    def submit_prepared_entry(
        self,
        enabled: bool,
        is_tester: bool,
        magic: int,
        symbol: str,
        prepared: XauPreparedEntry,
        tick_bid: float,
        tick_ask: float,
    ) -> XauTesterSubmission:
        submission = XauTesterSubmission()
        if (
            not tester_execution_allowed(enabled, is_tester, magic, symbol)
            or prepared.decision != XauEntryRejection.ALLOWED
        ):
            return submission

        direction: Literal["BUY", "SELL"] = "BUY" if prepared.candidate.direction == XauDirection.BUY else "SELL"
        request: EntryTradeRequest = {
            "action": "DEAL" if prepared.candidate.order_type == XauOrderType.MARKET else "PENDING",
            "symbol": symbol,
            "magic": magic,
            "volume": prepared.volume_lots,
            "sl": prepared.stop_loss,
            "tp": prepared.take_profit,
            "direction": direction,
        }
        if prepared.candidate.order_type == XauOrderType.MARKET:
            request["price"] = tick_ask if direction == "BUY" else tick_bid
        else:
            request["price"] = prepared.candidate.entry_price

        submission.attempted = True
        retcode, order_ticket, deal_ticket = self.sender.send(request)
        submission.retcode = retcode
        submission.order_ticket = order_ticket
        submission.deal_ticket = deal_ticket
        submission.accepted = tester_retcode_accepted(retcode)
        return submission

    def modify_protection(
        self,
        enabled: bool,
        is_tester: bool,
        magic: int,
        symbol: str,
        position_ticket: int,
        stop_loss: float,
        take_profit: float,
    ) -> tuple[bool, int]:
        if (
            not tester_execution_allowed(enabled, is_tester, magic, symbol)
            or position_ticket <= 0
            or stop_loss <= 0.0
            or take_profit <= 0.0
        ):
            return False, 0
        retcode, _, _ = self.sender.send(
            {
                "action": "SLTP",
                "symbol": symbol,
                "magic": magic,
                "position": position_ticket,
                "sl": stop_loss,
                "tp": take_profit,
            }
        )
        return tester_retcode_accepted(retcode), retcode

    def close_position(
        self,
        enabled: bool,
        is_tester: bool,
        magic: int,
        symbol: str,
        position_ticket: int,
        volume: float,
        position_type: Literal["BUY", "SELL"],
        tick_bid: float,
        tick_ask: float,
    ) -> XauTesterSubmission:
        submission = XauTesterSubmission()
        if not tester_execution_allowed(enabled, is_tester, magic, symbol) or position_ticket <= 0:
            return submission

        direction = "SELL" if position_type == "BUY" else "BUY"
        submission.attempted = True
        retcode, order_ticket, deal_ticket = self.sender.send(
            {
                "action": "DEAL",
                "symbol": symbol,
                "magic": magic,
                "position": position_ticket,
                "volume": volume,
                "direction": direction,
                "price": tick_bid if position_type == "BUY" else tick_ask,
            }
        )
        submission.retcode = retcode
        submission.order_ticket = order_ticket
        submission.deal_ticket = deal_ticket
        submission.accepted = tester_retcode_accepted(retcode)
        return submission
