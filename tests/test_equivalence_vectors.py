import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from scripts.generate_mql_vectors import render_header
from xauusd.momentum import (
    PreZoneTriggerTracker,
    PullbackTpState,
    TpActionType,
    pre_zone_trigger_price,
    strict_pullback_trend,
)
from xauusd.pullback import PullbackTracker, pullback_usage_allowed, pullback_window_active
from xauusd.risk import build_initial_risk, profit_protection_stop
from xauusd.safety import (
    DailyRealizedLossGuard,
    RestartFailClosedGuard,
    evaluate_portfolio_risk,
    session_end_actions,
)
from xauusd.signals import BreakoutSignal, BreakoutTracker, ReversalTracker, TradeDirection
from xauusd.trend import Candle, DailyTrendTracker, TrendState
from xauusd.zones import RawZone, Zone, ZoneEngagementTracker, ZonePriority, build_daily_zones

VECTOR_PATH = Path(__file__).parent / "vectors" / "core_contracts.json"


def load_vectors() -> tuple[date, list[dict[str, Any]]]:
    payload = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["price_encoding"] == "decimal_string"
    return date.fromisoformat(payload["broker_day"]), payload["vectors"]


def make_zones(day: date, definitions: list[dict[str, str]]) -> tuple[Zone, ...]:
    return build_daily_zones(
        RawZone.from_values(
            broker_day=day,
            low=item["low"],
            high=item["high"],
            priority=item["priority"],
            source_row=index,
        )
        for index, item in enumerate(definitions, start=1)
    )[day]


def test_frozen_core_vectors_match_python_contracts() -> None:
    day, vectors = load_vectors()
    assert [vector["id"] for vector in vectors] == [
        "breakout-buy-strict",
        "reversal-sell-directional-touch",
        "initial-risk-buy-skips-near-target",
        "gross15-inclusive-boundary",
        "trend-live-break-up",
        "pullback-buy-penetration-boundary",
        "strict-buy-momentum",
        "pre-zone-buy-gap-cross",
        "profit-protection-buy-step-four",
        "daily-loss-inclusive-boundary",
        "session-five-minute-boundary",
        "zone-chain-merge-strict-boundary",
        "multi-zone-gap-count",
        "pullback-high-window-t5",
        "tp-strict-failure-before-initial",
        "restart-same-day-lock",
    ]

    breakout_vector = vectors[0]
    breakout_input = breakout_vector["input"]
    breakout_zone = make_zones(day, [breakout_input["zone"]])[0]
    breakouts = BreakoutTracker()
    breakouts.begin_day(day)
    breakout = breakouts.evaluate_closed_bar(
        zone=breakout_zone,
        bar_id=breakout_input["bar_id"],
        close=breakout_input["close"],
        trend=TrendState(breakout_input["trend"]),
        buy_engaged=breakout_input["buy_engaged"],
        sell_engaged=breakout_input["sell_engaged"],
    )
    assert breakout is not None
    assert {
        "breakout_id": breakout.breakout_id,
        "direction": breakout.direction.value,
        "close": str(breakout.close),
    } == breakout_vector["expected"]

    reversal_vector = vectors[1]
    reversal_input = reversal_vector["input"]
    reversal_zone = make_zones(day, [reversal_input["zone"]])[0]
    reversals = ReversalTracker()
    reversals.begin_day(day)
    candidates = reversals.detect(
        previous_bid=reversal_input["previous_bid"],
        bid=reversal_input["bid"],
        trend=TrendState(reversal_input["trend"]),
        zones=[reversal_zone],
        bar_id=reversal_input["bar_id"],
        multi_zone_tick_gap=reversal_input["multi_zone_tick_gap"],
    )
    assert {
        "count": len(candidates),
        "direction": candidates[0].direction.value,
        "order_type": candidates[0].order_type.value,
    } == reversal_vector["expected"]

    risk_vector = vectors[2]
    risk_input = risk_vector["input"]
    risk_zones = make_zones(day, risk_input["zones"])
    initial = build_initial_risk(
        direction=TradeDirection(risk_input["direction"]),
        entry=risk_input["entry"],
        zones=risk_zones,
    )
    assert initial is not None
    assert {
        "stop_loss": str(initial.stop_loss),
        "take_profit": str(initial.take_profit),
        "stop_zone": initial.stop_zone_id.rsplit(":", 1)[1],
        "target_zone": initial.target_zone_id.rsplit(":", 1)[1],
    } == risk_vector["expected"]

    portfolio_vector = vectors[3]
    portfolio = evaluate_portfolio_risk(**portfolio_vector["input"])
    assert {
        "budget_cash": str(portfolio.budget_cash),
        "used_with_proposed": str(portfolio.used_with_proposed),
        "allowed": portfolio.allows_proposed,
    } == portfolio_vector["expected"]

    trend_vector = vectors[4]
    trend_input = trend_vector["input"]
    trends = DailyTrendTracker()
    trends.begin_day(day)
    trends.record_closed_candle(
        Candle.from_values(
            broker_day=day,
            open="95",
            high=trend_input["reference_high"],
            low=trend_input["reference_low"],
            close="99",
        )
    )
    assert {"state": trends.update(trend_input["bid"]).current.value} == trend_vector["expected"]

    pullback_vector = vectors[5]
    pullback_input = pullback_vector["input"]
    pullback_zone = make_zones(
        day,
        [
            {
                "low": pullback_input["zone_low"],
                "high": pullback_input["zone_high"],
                "priority": "normal",
            }
        ],
    )[0]
    breakout = BreakoutSignal(
        breakout_id="BO1",
        broker_day=day,
        bar_id="t",
        zone_id=pullback_zone.zone_id,
        direction=TradeDirection(pullback_input["direction"]),
        close=pullback_zone.high + 2,
    )
    pullbacks = PullbackTracker()
    pullbacks.begin_day(day)
    pullbacks.begin_bar("t")
    pullbacks.create_window(breakout, pullback_zone)
    pullbacks.begin_bar("t+1")
    pullback_candidates = pullbacks.evaluate_price(pullback_input["bid"])
    assert {
        "penetrated": bool(pullback_candidates),
        "entry": str(pullback_candidates[0].entry_price),
    } == pullback_vector["expected"]

    strict_vector = vectors[6]
    strict_input = strict_vector["input"]
    closed: list[Candle] = []
    for index, candle_direction in enumerate(strict_input["closed_directions"]):
        open_value = 100 + index
        close_value = {
            "bullish": open_value + 1,
            "bearish": open_value - 1,
            "doji": open_value,
        }[candle_direction]
        closed.append(
            Candle.from_values(
                broker_day=day,
                open=str(open_value),
                high=str(max(open_value, close_value) + 1),
                low=str(min(open_value, close_value) - 1),
                close=str(close_value),
            )
        )
    strict_valid = strict_pullback_trend(
        direction=TradeDirection(strict_input["direction"]),
        closed_after_pullback=closed,
        current_open=strict_input["current_open"],
        current_bid=strict_input["current_bid"],
        current_ask=strict_input["current_ask"],
    )
    assert {"valid": strict_valid} == strict_vector["expected"]

    trigger_vector = vectors[7]
    trigger_input = trigger_vector["input"]
    target_zone = make_zones(
        day,
        [
            {
                "low": trigger_input["target_low"],
                "high": trigger_input["target_high"],
                "priority": "normal",
            }
        ],
    )[0]
    trigger_direction = TradeDirection(trigger_input["direction"])
    triggers = PreZoneTriggerTracker()
    crossed = triggers.crossed(
        position_id="P1",
        direction=trigger_direction,
        target_zone=target_zone,
        previous_price=trigger_input["previous_price"],
        current_price=trigger_input["current_price"],
    )
    assert {
        "trigger": str(pre_zone_trigger_price(trigger_direction, target_zone)),
        "crossed": crossed,
    } == trigger_vector["expected"]

    protection_vector = vectors[8]
    protection_input = protection_vector["input"]
    protected_stop = profit_protection_stop(
        direction=TradeDirection(protection_input["direction"]),
        entry=protection_input["entry"],
        risk_free=protection_input["risk_free"],
        current_bid=protection_input["current_bid"],
        current_ask=protection_input["current_ask"],
        current_stop=protection_input["current_stop"],
    )
    assert {"modify": protected_stop is not None, "stop": str(protected_stop)} == protection_vector[
        "expected"
    ]

    daily_vector = vectors[9]
    daily_input = daily_vector["input"]
    daily = DailyRealizedLossGuard(daily_input["strategy_capital"])
    daily.begin_day(day)
    assert {"locked": daily.update(daily_input["net_realized_pnl"]).locked} == daily_vector[
        "expected"
    ]

    session_vector = vectors[10]
    session_input = session_vector["input"]
    session = session_end_actions(
        broker_now=datetime.fromisoformat(session_input["broker_now"]),
        broker_session_end=datetime.fromisoformat(session_input["broker_session_end"]),
    )
    assert {"active": session.locked} == session_vector["expected"]

    merge_vector = vectors[11]
    merged = make_zones(day, merge_vector["input"]["zones"])
    assert {
        "count": len(merged),
        "first_low": str(merged[0].low),
        "first_high": str(merged[0].high),
        "first_priority": merged[0].priority.value,
        "first_id": merged[0].zone_id,
        "second_id": merged[1].zone_id,
    } == merge_vector["expected"]

    gap_vector = vectors[12]
    gap_input = gap_vector["input"]
    gap_zones = make_zones(day, gap_input["zones"])
    engagement = ZoneEngagementTracker(gap_zones)
    crosses = engagement.count_directional_crosses(gap_input["previous_bid"], gap_input["bid"])
    assert {"crosses": crosses, "multi_zone_tick_gap": crosses > 1} == gap_vector["expected"]

    pullback_state_vector = vectors[13]
    pullback_state_input = pullback_state_vector["input"]
    assert {
        "window_active": pullback_window_active(pullback_state_input["bar_offset"]),
        "usage_allowed": pullback_usage_allowed(
            ZonePriority(pullback_state_input["priority"]),
            pullback_state_input["daily_fills"],
        ),
    } == pullback_state_vector["expected"]

    tp_vector = vectors[14]
    tp_input = tp_vector["input"]
    tp_zone = make_zones(
        day,
        [{"low": tp_input["initial_tp"], "high": "101", "priority": "normal"}],
    )[0]
    tp_state = PullbackTpState.create(
        position_id="P1",
        direction=TradeDirection(tp_input["direction"]),
        initial_target_zone=tp_zone,
    )
    tp_state.extended = tp_input["extended"]
    tp_action = tp_state.evaluate_strict_failure(
        strict_trend_valid=tp_input["strict_valid"],
        current_bid=tp_input["current_bid"],
        current_ask=tp_input["current_ask"],
    )
    assert {"action": tp_action.action.value} == tp_vector["expected"]
    assert tp_action.action is TpActionType.RESTORE

    restart_vector = vectors[15]
    restart_input = restart_vector["input"]
    restart = RestartFailClosedGuard()
    restart_state = restart.attach(
        broker_day=date.fromisoformat(restart_input["broker_day"]),
        persisted_last_activation_day=date.fromisoformat(
            restart_input["persisted_last_activation_day"]
        ),
    )
    assert {"locked": restart_state.locked} == restart_vector["expected"]


def test_generated_mql_header_matches_canonical_json() -> None:
    root = Path(__file__).parents[1]
    payload = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))
    generated = (root / "src" / "mt5" / "generated" / "CoreVectors.mqh").read_text(encoding="utf-8")
    assert generated == render_header(payload)
