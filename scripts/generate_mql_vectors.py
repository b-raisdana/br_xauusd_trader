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
