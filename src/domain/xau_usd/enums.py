from __future__ import annotations

from enum import IntEnum, auto


class AutoIntEnum(IntEnum):  # TODO: CONVERT TO AutoStrEnum
    """IntEnum whose auto-generated values start at zero."""

    def __new__(cls, *args):
        value = len(cls.__members__)
        obj = int.__new__(cls, value)
        obj._value_ = value
        return obj


class XauDirection(AutoIntEnum):
    BUY = auto()
    SELL = auto()


class XauTrend(AutoIntEnum):
    NONE = auto()
    UP = auto()
    DOWN = auto()


class XauExecutionStatus(AutoIntEnum):
    SUBMITTED = auto()
    FILLED = auto()
    REJECTED = auto()
    CLOSED = auto()
    CANCELLED = auto()


class XauExecutionEvent(AutoIntEnum):
    FILL = auto()
    REJECT = auto()
    CLOSE = auto()
    MODIFY = auto()
    MODIFY_REJECT = auto()
    CANCEL = auto()
    CANCEL_REJECT = auto()


class XauOrderType(AutoIntEnum):
    MARKET = auto()
    PENDING_STOP = auto()


class XauSignalFamily(AutoIntEnum):
    BREAKOUT = auto()
    REVERSAL = auto()
    PULLBACK = auto()


class XauEntryRejection(AutoIntEnum):
    ALLOWED = auto()
    DAILY_LOSS = auto()
    GROSS_RISK = auto()
    CONCURRENCY = auto()
    MARGIN = auto()
    INVALID_PROTECTION = auto()
    FREE_SPACE = auto()
    INITIAL_RISK = auto()


class XauTpFailureAction(AutoIntEnum):
    NONE = auto()
    RESTORE = auto()
    MARKET_CLOSE = auto()
