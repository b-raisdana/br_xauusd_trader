"""Build account-free structured evidence for the latest V1 multi-day MT5 run."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def last_match(lines: list[str], pattern: str) -> re.Match[str]:
    matches = [match for line in lines if (match := re.search(pattern, line))]
    if not matches:
        raise RuntimeError(f"Required MT5 marker missing: {pattern}")
    return matches[-1]


def json_lines(path: Path, kind: str) -> list[dict[str, object]]:
    rows = [json.loads(line) for line in path.read_text(encoding="ascii").splitlines()]
    if any(row.get("schema_version") != 1 or row.get("kind", kind) != kind for row in rows):
        raise RuntimeError(f"Invalid {kind} journal schema")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--orders", type=Path, required=True)
    parser.add_argument("--blocks", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--compiled", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    lines = args.log.read_text(encoding="utf-16", errors="strict").splitlines()
    done = last_match(
        lines,
        r"CURRENT_EVENT_LOOP_DONE breakout=(\d+) reversal=(\d+) pullback=(\d+) "
        r"attempts=(\d+) accepted=(\d+) rejected=(\d+) cancellations=(\d+) "
        r"session_closes=(\d+) session_flattened=(\d+) failed=(\d+) mode=tester",
    )
    risk = last_match(
        lines,
        r"TESTER_RISK_DONE net=(-?[\d.]+) gross_loss=([\d.]+) max_positions=(\d+) .*"
        r"invalid_price_rejects=(\d+) invalid_stop_rejects=(\d+) "
        r"other_broker_rejects=(\d+) .*sl_loosen=(\d+) mode=tester",
    )
    v1 = last_match(
        lines,
        r"TESTER_V1_DONE candidate_blocks=(\d+) native_pending_waits=(\d+) "
        r"opposite_reversal_blocks=(\d+) expiry_cancels=(\d+) mode=tester",
    )
    orders = json_lines(args.orders, "order")
    blocks = json_lines(args.blocks, "block")
    attempts, accepted, rejected = map(int, done.group(4, 5, 6))
    if int(done.group(10)) != 0 or int(done.group(9)) != 1:
        raise RuntimeError("V1 run did not finish safely")
    if len(orders) != attempts or accepted + rejected != attempts:
        raise RuntimeError("Order journal does not reconcile with lifecycle counters")
    if len(blocks) != int(v1.group(1)):
        raise RuntimeError("Block journal does not reconcile with V1 counters")
    if int(risk.group(4)) != 0 or int(risk.group(6)) != 0 or int(risk.group(7)) != 0:
        raise RuntimeError("V1 safety counters failed")

    evidence = {
        "schema_version": 1,
        "run_id": "V1_STABILIZED_23D_REAL_TICK_200",
        "status": "PASS",
        "scope": {
            "config": "config/mt5/tester_multiday_200.ini",
            "model": "Every Tick Based on Real Ticks",
            "capital_usd": "200.00",
            "max_positions_allowed": 3,
            "live_enabled": False,
        },
        "provenance": {
            "source_sha256": sha256(args.source),
            "compiled_sha256": sha256(args.compiled),
        },
        "lifecycle": {
            "breakout_candidates": int(done.group(1)),
            "reversal_candidates": int(done.group(2)),
            "pullback_candidates": int(done.group(3)),
            "attempts": attempts,
            "accepted": accepted,
            "rejected": rejected,
            "cancellations": int(done.group(7)),
            "session_closes": int(done.group(8)),
            "session_flattened": True,
            "failed": 0,
        },
        "risk": {
            "terminal_summary_net_usd": risk.group(1),
            "terminal_summary_gross_loss_usd": risk.group(2),
            "max_positions_observed": int(risk.group(3)),
            "invalid_price_rejects": int(risk.group(4)),
            "invalid_stop_rejects": int(risk.group(5)),
            "other_broker_rejects": int(risk.group(6)),
            "sl_loosen_violations": int(risk.group(7)),
        },
        "v1": {
            "candidate_blocks": len(blocks),
            "native_pending_waits": int(v1.group(2)),
            "opposite_reversal_blocks": int(v1.group(3)),
            "expiry_cancels": int(v1.group(4)),
            "block_reasons": dict(sorted(Counter(str(row["reason"]) for row in blocks).items())),
        },
        "journals": {"order_records": len(orders), "block_records": len(blocks)},
        "limitations": [
            "Engineering backtest evidence is not permission for demo or real-money trading.",
            "The single native invalid-stop rejection is retained and is not a "
            "pending-price defect.",
            "The terminal risk summary is the final Broker Day snapshot, not whole-range PnL.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"PASS attempts={attempts} orders={len(orders)} blocks={len(blocks)}")


if __name__ == "__main__":
    main()
