from __future__ import annotations

from application.xauusd_trading_strategy_1_vector.domain.entry import (
    concurrency_allows_entry,
    evaluate_protected_entry,
    has_minimum_free_space,
    initial_stop,
    initial_target,
    native_margin_allows_entry,
    portfolio_risk_allows,
)
from application.xauusd_trading_strategy_1_vector.domain.state import (
    find_daily_zone_state,
    record_entry_attempt,
    record_pullback_attempt,
)
from domain.xau_usd.enums import XauEntryRejection, XauSignalFamily
from domain.xau_usd.models import (
    XauMarketCoordinator,
    XauOrderAuditEvent,
    XauPreparedEntry,
    XauSignalCandidate,
    XauZone,
)


def entry_bar_available(attempted_bars: list[str], bar_id: str) -> bool:
    return bool(bar_id) and bar_id not in attempted_bars


def candidate_attempt_available(state: XauMarketCoordinator, candidate: XauSignalCandidate) -> bool:
    if not entry_bar_available(state.attempted_bars, candidate.bar_id):
        return False

    zone_index = find_daily_zone_state(state.zones, candidate.zone_id)
    if zone_index < 0:
        return False

    zone_state = state.zones[zone_index]
    if candidate.family == XauSignalFamily.BREAKOUT:
        return True

    if candidate.family == XauSignalFamily.REVERSAL:
        limit = 2 if zone_state.zone.priority == 1 else 1
        return zone_state.reversal_usage < limit

    if candidate.family == XauSignalFamily.PULLBACK:
        window_index = next(
            (
                index
                for index, window in enumerate(state.pullbacks)
                if window.zone.id == candidate.zone_id and window.direction == candidate.direction
            ),
            -1,
        )
        return (
            window_index >= 0
            and state.pullbacks[window_index].active
            and not state.pullbacks[window_index].pending_active
            and zone_state.pullback_fills >= 0
            and (zone_state.zone.priority == 1 or zone_state.pullback_fills < 1)
        )

    return False


def prepare_candidate_entry(
    candidate: XauSignalCandidate,
    zones: list[XauZone],
    daily_locked: bool,
    strategy_capital: float,
    realized_gross_loss: float,
    open_risk: float,
    pending_risk: float,
    open_positions: int,
    native_cash_risk: float,
    required_margin: float,
    free_margin: float,
    prepared: XauPreparedEntry,
) -> bool:
    prepared.candidate = candidate
    prepared.volume_lots = 0.01
    prepared.stop_loss = 0.0
    prepared.take_profit = 0.0
    prepared.stop_zone_id = ""
    prepared.target_zone_id = ""

    if candidate.family not in {
        XauSignalFamily.BREAKOUT,
        XauSignalFamily.REVERSAL,
        XauSignalFamily.PULLBACK,
    }:
        prepared.decision = XauEntryRejection.INITIAL_RISK
        return False

    if not has_minimum_free_space(candidate.zone_id, candidate.direction, zones):
        prepared.decision = XauEntryRejection.FREE_SPACE
        return True

    stop_found, stop_loss, stop_zone_id = initial_stop(candidate.direction, candidate.entry_price, zones)
    target_found, take_profit, target_zone_id = initial_target(candidate.direction, candidate.entry_price, zones)
    if not stop_found or not target_found or stop_loss is None or take_profit is None:
        prepared.decision = XauEntryRejection.INITIAL_RISK
        return True

    prepared.stop_loss = stop_loss
    prepared.take_profit = take_profit
    prepared.stop_zone_id = stop_zone_id or ""
    prepared.target_zone_id = target_zone_id or ""

    portfolio_allowed = portfolio_risk_allows(
        strategy_capital,
        realized_gross_loss,
        open_risk,
        pending_risk,
        native_cash_risk,
    )
    prepared.decision = evaluate_protected_entry(
        daily_locked,
        portfolio_allowed,
        concurrency_allows_entry(strategy_capital, open_positions),
        native_margin_allows_entry(required_margin, free_margin),
        candidate.direction,
        candidate.entry_price,
        prepared.stop_loss,
        prepared.take_profit,
        prepared.volume_lots,
    )
    return True


def build_prepared_order_audit(
    prepared: XauPreparedEntry,
    event_id: str,
    request_id: str,
) -> XauOrderAuditEvent | None:
    if prepared.decision != XauEntryRejection.ALLOWED or not event_id or not request_id:
        return None

    if prepared.candidate.family == XauSignalFamily.BREAKOUT:
        rule_ids = "BREAKOUT_VALIDATION,ZONE_ENGAGEMENT"
    elif prepared.candidate.family == XauSignalFamily.REVERSAL:
        rule_ids = "REVERSAL_DIRECTIONAL_TOUCH"
    else:
        rule_ids = "PULLBACK_CONSERVATIVE"

    return XauOrderAuditEvent(
        event_id=event_id,
        request_id=request_id,
        zone_id=prepared.candidate.zone_id,
        rule_ids=rule_ids,
        direction=prepared.candidate.direction,
        order_type=prepared.candidate.order_type,
        broker_time=prepared.candidate.signal_time,
        entry=prepared.candidate.entry_price,
        stop_loss=prepared.stop_loss,
        take_profit=prepared.take_profit,
    )


def commit_prepared_entry_attempt(
    state: XauMarketCoordinator,
    prepared: XauPreparedEntry,
    broker_accepted: bool,
) -> bool:
    if prepared.decision != XauEntryRejection.ALLOWED:
        return False

    zone_index = find_daily_zone_state(state.zones, prepared.candidate.zone_id)
    if zone_index < 0:
        return False

    zone_state = state.zones[zone_index]
    if prepared.candidate.family == XauSignalFamily.BREAKOUT:
        return record_entry_attempt(state.attempted_bars, prepared.candidate.bar_id)

    if prepared.candidate.family == XauSignalFamily.REVERSAL:
        limit = 2 if zone_state.zone.priority == 1 else 1
        if zone_state.reversal_usage >= limit:
            return False
        if not record_entry_attempt(state.attempted_bars, prepared.candidate.bar_id):
            return False
        zone_state.reversal_usage += 1
        return True

    if prepared.candidate.family == XauSignalFamily.PULLBACK:
        window_index = next(
            (
                index
                for index, window in enumerate(state.pullbacks)
                if window.zone.id == prepared.candidate.zone_id and window.direction == prepared.candidate.direction
            ),
            -1,
        )
        if window_index < 0:
            return False
        return record_pullback_attempt(
            state.pullbacks[window_index],
            state.attempted_bars,
            prepared.candidate.bar_id,
            broker_accepted,
        )

    return False
