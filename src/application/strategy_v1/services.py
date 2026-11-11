from typing import Protocol

from .contracts import OrderResult, PositionResult, SignalResult, StrategyContext, StrategySnapshot


class SignalStage(Protocol):
    def execute(self, incoming: StrategyContext | PositionResult) -> SignalResult: ...


class OrderStage(Protocol):
    def execute(self, incoming: SignalResult) -> OrderResult: ...


class PositionStage(Protocol):
    def execute(self, incoming: OrderResult) -> PositionResult: ...


class SnapshotIngress(Protocol):
    def append_snapshot(self, previous: PositionResult, snapshot: StrategySnapshot) -> PositionResult: ...
