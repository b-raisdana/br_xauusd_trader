import json
from datetime import date
from pathlib import Path
from typing import Any

from scripts.generate_mql_vectors import render_header
from xauusd.risk import build_initial_risk
from xauusd.safety import evaluate_portfolio_risk
from xauusd.signals import BreakoutTracker, ReversalTracker, TradeDirection
from xauusd.trend import TrendState
from xauusd.zones import RawZone, Zone, build_daily_zones

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


def test_generated_mql_header_matches_canonical_json() -> None:
    root = Path(__file__).parents[1]
    payload = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))
    generated = (root / "src" / "mt5" / "generated" / "CoreVectors.mqh").read_text(encoding="utf-8")
    assert generated == render_header(payload)
