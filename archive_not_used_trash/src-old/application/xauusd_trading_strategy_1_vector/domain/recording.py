from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, JsonValue, model_validator

from domain.xau_usd.models import XauZone

from .native import NativeDeal, NativeOperation, NativeProfitResult, NativeRecord, NativeView
from .robust import RobustInputs


class NativeMarginResult(NativeRecord):
    volume: float
    entry: float
    value: float | None


class RecordedMarketInput(NativeRecord):
    time: AwareDatetime
    day: str
    bar_time: AwareDatetime
    bar_open: float
    bid: float
    ask: float
    history: tuple[tuple[float, float, float, float], ...]
    zones: tuple[XauZone, ...]
    view: NativeView


class RecordedInit(RecordedMarketInput):
    kind: Literal["init"] = "init"
    has_ea_deal_today: bool


class RecordedTick(RecordedMarketInput):
    kind: Literal["tick"] = "tick"


class RecordedDeal(NativeRecord):
    kind: Literal["deal"] = "deal"
    deal: NativeDeal
    bid: float
    ask: float
    view: NativeView


class NativeRecording(NativeRecord):
    """UTC-normalized event tape; event array order resolves equal timestamps."""

    provenance: Literal["source-derived", "native"]
    reference_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    envelope_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    terminal_build: str | None = None
    initial_balance: float = Field(gt=0)
    inputs: RobustInputs
    minimum_stop_distance: float = Field(ge=0)
    session_windows: tuple[tuple[AwareDatetime, AwareDatetime], ...]
    profits: tuple[NativeProfitResult, ...]
    margins: tuple[NativeMarginResult, ...] = ()
    operations: tuple[NativeOperation, ...]
    events: tuple[Annotated[RecordedInit | RecordedTick | RecordedDeal, Field(discriminator="kind")], ...]

    @model_validator(mode="after")
    def validate_tape(self) -> Self:
        if not self.events or not isinstance(self.events[0], RecordedInit):
            raise ValueError("Recording requires successful initialization before ticks/callbacks")
        if self.initial_balance != self.events[0].view.balance:
            raise ValueError("Initial deposit must match the observed initialization balance")
        if any(isinstance(event, RecordedInit) for event in self.events[1:]):
            raise ValueError("Start a new recording for each EA initialization")
        if self.provenance == "native" and (not self.envelope_sha256 or not self.terminal_build):
            raise ValueError("Native provenance requires the complete EA envelope hash and terminal build")
        if any(a >= b for a, b in self.session_windows):
            raise ValueError("Session windows require start < end")
        keys = [(p.direction, p.volume, p.entry, p.exit_price) for p in self.profits]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate profit query; use view.profits when conversion results change")
        margin_keys = [(m.volume, m.entry) for m in self.margins]
        if len(margin_keys) != len(set(margin_keys)):
            raise ValueError("Duplicate margin query")
        times = [event.time if isinstance(event, RecordedMarketInput) else event.deal.time for event in self.events]
        if any(a > b for a, b in zip(times, times[1:], strict=False)):
            raise ValueError("Event callback times must be chronological; equal times retain input order")
        return self


class NativeCheckpoint(NativeRecord):
    sequence: int
    kind: Literal["init", "tick", "deal"]
    time: AwareDatetime
    state: dict[str, JsonValue]
