"""Generate the small MQL5 core-vector header from the canonical JSON fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "tests" / "vectors" / "core_contracts.json"
TARGET = ROOT / "src" / "mt5" / "generated" / "CoreVectors.mqh"


def render_header(payload: dict[str, Any]) -> str:
    vectors = {item["id"]: item for item in payload["vectors"]}
    breakout = vectors["breakout-buy-strict"]["input"]
    reversal = vectors["reversal-sell-directional-touch"]["input"]
    risk = vectors["initial-risk-buy-skips-near-target"]
    portfolio = vectors["gross15-inclusive-boundary"]["input"]
    trend = vectors["trend-live-break-up"]["input"]
    pullback = vectors["pullback-buy-penetration-boundary"]["input"]
    strict = vectors["strict-buy-momentum"]["input"]
    trigger = vectors["pre-zone-buy-gap-cross"]["input"]
    protection = vectors["profit-protection-buy-step-four"]["input"]
    daily = vectors["daily-loss-inclusive-boundary"]["input"]
    session = vectors["session-five-minute-boundary"]["input"]
    risk_zones = risk["input"]["zones"]
    lines = [
        "// Generated from tests/vectors/core_contracts.json. Do not edit manually.",
        f"#define VEC_BREAKOUT_LOW {breakout['zone']['low']}",
        f"#define VEC_BREAKOUT_HIGH {breakout['zone']['high']}",
        f"#define VEC_BREAKOUT_CLOSE {breakout['close']}",
        f"#define VEC_REVERSAL_PREVIOUS {reversal['previous_bid']}",
        f"#define VEC_REVERSAL_CURRENT {reversal['bid']}",
        f"#define VEC_RISK_ENTRY {risk['input']['entry']}",
        f"#define VEC_RISK_EXPECTED_SL {risk['expected']['stop_loss']}",
        f"#define VEC_RISK_EXPECTED_TP {risk['expected']['take_profit']}",
    ]
    for index, zone in enumerate(risk_zones, start=1):
        lines.extend(
            (
                f"#define VEC_RISK_ZONE_{index}_LOW {zone['low']}",
                f"#define VEC_RISK_ZONE_{index}_HIGH {zone['high']}",
            )
        )
    lines.extend(
        (
            f"#define VEC_PORTFOLIO_CAPITAL {portfolio['strategy_capital']}",
            f"#define VEC_PORTFOLIO_REALIZED {portfolio['realized_gross_loss']}",
            f"#define VEC_PORTFOLIO_OPEN {portfolio['open_position_risk']}",
            f"#define VEC_PORTFOLIO_PENDING {portfolio['pending_order_risk']}",
            f"#define VEC_PORTFOLIO_PROPOSED {portfolio['proposed_order_risk']}",
            f"#define VEC_TREND_REFERENCE_HIGH {trend['reference_high']}",
            f"#define VEC_TREND_REFERENCE_LOW {trend['reference_low']}",
            f"#define VEC_TREND_BID {trend['bid']}",
            f"#define VEC_PULLBACK_LOW {pullback['zone_low']}",
            f"#define VEC_PULLBACK_HIGH {pullback['zone_high']}",
            f"#define VEC_PULLBACK_BID {pullback['bid']}",
            f"#define VEC_STRICT_CURRENT_OPEN {strict['current_open']}",
            f"#define VEC_STRICT_CURRENT_BID {strict['current_bid']}",
            f"#define VEC_STRICT_CURRENT_ASK {strict['current_ask']}",
            f"#define VEC_TRIGGER_TARGET_LOW {trigger['target_low']}",
            f"#define VEC_TRIGGER_TARGET_HIGH {trigger['target_high']}",
            f"#define VEC_TRIGGER_PREVIOUS {trigger['previous_price']}",
            f"#define VEC_TRIGGER_CURRENT {trigger['current_price']}",
            f"#define VEC_PROTECTION_ENTRY {protection['entry']}",
            f"#define VEC_PROTECTION_RF {protection['risk_free']}",
            f"#define VEC_PROTECTION_BID {protection['current_bid']}",
            f"#define VEC_PROTECTION_ASK {protection['current_ask']}",
            f"#define VEC_PROTECTION_CURRENT_SL {protection['current_stop']}",
            f"#define VEC_DAILY_CAPITAL {daily['strategy_capital']}",
            f"#define VEC_DAILY_NET_PNL {daily['net_realized_pnl']}",
            '#define VEC_SESSION_NOW "'
            + session["broker_now"].replace("-", ".").replace("T", " ")
            + '"',
            '#define VEC_SESSION_END "'
            + session["broker_session_end"].replace("-", ".").replace("T", " ")
            + '"',
        )
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render_header(json.loads(SOURCE.read_text(encoding="utf-8")))
    if args.check:
        return 0 if TARGET.read_text(encoding="utf-8") == expected else 1
    TARGET.write_text(expected, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
