from __future__ import annotations

from .global_state_variable import StrategyRuntimeState
from .lifecycle import EventLoop, OnTickResult, RuntimeEnvironment, Tick
from .settings import StrategySettings


def process_current_event_loop_tick(
    tick: Tick,
    event_loop: EventLoop,
) -> bool:
    return event_loop.process_tick(tick)


def on_tick(
    tick: Tick,
    settings: StrategySettings,
    strategy_runtime: StrategyRuntimeState,
    environment: RuntimeEnvironment | None = None,
    event_loop: EventLoop | None = None,
) -> OnTickResult:
    if environment is None:
        environment = RuntimeEnvironment()
    probe_emitted = False
    if settings.emit_time_basis_probe and strategy_runtime.time_basis_probe_count < 5 and tick.is_valid:
        strategy_runtime.time_basis_probe_count += 1
        probe_emitted = True

    if not settings.run_current_event_loop:
        return OnTickResult(handled=True, time_basis_probe_emitted=probe_emitted)

    if event_loop is None:
        if not strategy_runtime.event_loop_failure_reported:
            strategy_runtime.event_loop_failure_reported = True
        return OnTickResult(
            handled=False,
            time_basis_probe_emitted=probe_emitted,
            event_loop_failed=True,
        )

    try:
        handled = process_current_event_loop_tick(tick, event_loop)
    except Exception:
        handled = False
    if not handled and not strategy_runtime.event_loop_failure_reported:
        strategy_runtime.event_loop_failure_reported = True

    return OnTickResult(
        handled=handled,
        time_basis_probe_emitted=probe_emitted,
        event_loop_failed=not handled,
    )


handle_tick = on_tick

__all__ = ["handle_tick", "on_tick", "process_current_event_loop_tick"]
