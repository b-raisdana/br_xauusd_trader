"""Explicit terminal observations; no inferred fills or account-currency conversions."""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from domain.xau_usd.enums import XauDirection

EA_MAGIC = 260911125


class NativeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class NativePosition(NativeRecord):
    identifier: int = Field(ge=0)
    ticket: int = Field(gt=0)
    magic: int
    symbol: str
    buy: bool
    volume: float = Field(gt=0)
    entry: float = Field(gt=0)
    sl: float
    tp: float
    opened: AwareDatetime
    comment: str


class NativePending(NativeRecord):
    ticket: int = Field(gt=0)
    magic: int
    buy: bool
    volume: float = Field(gt=0)
    entry: float = Field(gt=0)
    sl: float


class NativeHistoryDeal(NativeRecord):
    ticket: int = Field(gt=0)
    position_id: int = Field(ge=0)
    magic: int
    profit: float
    commission: float
    swap: float
    fee: float


class NativeProfitResult(NativeRecord):
    direction: XauDirection
    volume: float
    entry: float
    exit_price: float
    value: float | None


class NativeView(NativeRecord):
    balance: float
    free_margin: float
    positions: tuple[NativePosition, ...] = ()
    pending: tuple[NativePending, ...] = ()
    history: tuple[NativeHistoryDeal, ...] = ()
    profits: tuple[NativeProfitResult, ...] = ()


class NativeDeal(NativeRecord):
    time: AwareDatetime
    ticket: int = Field(ge=0)
    position_id: int = Field(ge=0)
    magic: int
    symbol: str
    entry: Literal["IN", "OUT", "OUT_BY", "INOUT"]
    price: float = Field(gt=0)
    volume: float = Field(gt=0)
    comment: str = ""
    order_comment: str = ""
    order_ticket: int = Field(default=0, ge=0)
    history_selected: bool = True
    deal_add: bool = True


class NativeOperation(NativeRecord):
    operation: Literal["SUBMIT", "CANCEL", "MODIFY", "CLOSE"]
    target: str
    time: AwareDatetime
    accepted: bool
    order_ticket: int = Field(default=0, ge=0)
    after: NativeView
    price: float | None = None
    sl: float | None = None
    tp: float | None = None
    volume: float | None = None

    @model_validator(mode="after")
    def command_parameters(self) -> Self:
        if self.operation == "SUBMIT" and any(v is None for v in (self.price, self.sl, self.tp, self.volume)):
            raise ValueError("SUBMIT requires recorded price, SL, TP and volume")
        if self.operation == "MODIFY" and (self.sl is None or self.tp is None):
            raise ValueError("MODIFY requires recorded SL and TP")
        return self


class NativeCalculationFailure(ValueError):
    pass


@dataclass
class RecordedEconomics:
    """Exact lookup table for native calculations and ordered operation responses.

    Missing records raise; None represents an observed failed native calculation.
    Operation targets are replay request IDs, explicitly mapped when preparing a tape.
    """

    minimum_stop_distance: float
    session_windows: tuple[tuple[datetime, datetime], ...]
    profits: dict[tuple[XauDirection, float, float, float], float | None]
    margins: dict[tuple[float, float], float | None]
    operations: deque[NativeOperation]
    view: NativeView
    last_operation: NativeOperation | None = field(default=None, init=False)

    def profit(self, direction: XauDirection, volume: float, entry: float, exit_price: float) -> float:
        key = (direction, volume, entry, exit_price)
        observed = next((p for p in self.view.profits if (p.direction, p.volume, p.entry, p.exit_price) == key), None)
        value = observed.value if observed is not None else self.profits[key]
        if value is None:
            raise NativeCalculationFailure(f"OrderCalcProfit failed for {key}")
        return value

    def margin(self, volume: float, entry: float) -> float:
        value = self.margins[(volume, entry)]
        if value is None:
            raise NativeCalculationFailure("OrderCalcMargin failed")
        return value

    def cost(self, volume: float, time: datetime, opening: bool) -> float:
        raise ValueError("Recorded costs must come from deal history")

    def session_window(self, time: datetime) -> tuple[datetime, datetime] | None:
        return next(((a, b) for a, b in self.session_windows if a <= time < b), None)

    def session_end(self, time: datetime) -> datetime:
        window = self.session_window(time)
        if window is None:
            raise ValueError("No native session contains this time")
        return window[1]

    def accepts(self, operation: str, request_id: str, time: datetime) -> bool:
        return self.execute(operation, request_id, time)

    def execute(
        self,
        operation: str,
        target: str,
        time: datetime,
        *,
        price: float | None = None,
        sl: float | None = None,
        tp: float | None = None,
        volume: float | None = None,
    ) -> bool:
        if not self.operations:
            raise ValueError(f"Missing recorded operation: {operation} {target} at {time}")
        result = self.operations[0]
        if (result.operation, result.target, result.time, result.price, result.sl, result.tp, result.volume) != (
            operation,
            target,
            time,
            price,
            sl,
            tp,
            volume,
        ):
            raise ValueError(
                f"Recorded operation mismatch: expected {result.operation} {result.target} at {result.time} "
                f"with parameters {(result.price, result.sl, result.tp, result.volume)}; "
                f"got {operation} {target} at {time} with parameters {(price, sl, tp, volume)}"
            )
        self.operations.popleft()
        self.last_operation = result
        self.view = result.after
        return result.accepted

    def assert_consumed(self) -> None:
        if self.operations:
            raise ValueError(f"{len(self.operations)} recorded operations were not consumed")
