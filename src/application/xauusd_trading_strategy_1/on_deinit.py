from __future__ import annotations

from dataclasses import dataclass

from .global_state_variable import StrategyRuntimeState
from .settings import StrategySettings


@dataclass(frozen=True, slots=True)
class OnDeinitResult:
    mode: str
    breakout_candidates: int
    reversal_candidates: int
    pullback_candidates: int
    attempts: int
    accepts: int
    rejects: int
    cancellations: int
    session_closes: int
    session_flattened: bool
    failed: bool


def on_deinit(
    reason: int,
    settings: StrategySettings,
    runtime: StrategyRuntimeState,
) -> OnDeinitResult:
    return OnDeinitResult(
        mode="tester" if settings.enable_tester_execution else "inert",
        breakout_candidates=runtime.breakout_candidate_count,
        reversal_candidates=runtime.reversal_candidate_count,
        pullback_candidates=runtime.pullback_candidate_count,
        attempts=runtime.tester_attempt_count,
        accepts=runtime.tester_accept_count,
        rejects=runtime.tester_reject_count,
        cancellations=runtime.session_cancel_count,
        session_closes=runtime.session_close_count,
        session_flattened=runtime.session_zero_exposure,
        failed=runtime.event_loop_failure_reported,
    )


__all__ = ["OnDeinitResult", "on_deinit"]
