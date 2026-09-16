from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from domain.xau_usd.models import XauNativeDealOutcome
from infrastructure.xau_usd.native import NativeBroker

from .global_state_variable import StrategyRuntimeState
from .settings import StrategySettings


class TradeTransaction(Protocol):
    deal: int
    order: int
    symbol: str


class TradeRequest(Protocol):
    action: int
    symbol: str


class TradeResult(Protocol):
    retcode: int
    deal: int
    order: int


def on_trade_transaction(
    transaction: TradeTransaction,
    request: TradeRequest,
    result: TradeResult,
    settings: StrategySettings,
    runtime: StrategyRuntimeState,
    native: NativeBroker,
    apply_outcome: Callable[[XauNativeDealOutcome], bool],
) -> bool:
    if not settings.observe_native_outcomes or runtime.market_state is None:
        return False

    outcome = native.deal_outcome(
        transaction.deal,
        transaction.order,
        transaction.symbol,
        settings.strategy_magic,
    )
    return outcome is not None and apply_outcome(outcome)


__all__ = ["on_trade_transaction"]
