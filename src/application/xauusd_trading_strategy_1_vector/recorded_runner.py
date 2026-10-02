"""Run an ordered native event tape and compare every shared-state checkpoint."""

import argparse
import hashlib
import json
from collections import deque
from collections.abc import Iterator
from pathlib import Path

from .domain.native import RecordedEconomics
from .domain.recording import NativeCheckpoint, NativeRecording, RecordedInit, RecordedTick
from .domain.replay import ReplayConfig
from .market import MarketState
from .native_replay import RecordedExecutionReplay
from .trace import first_difference, shared_trace, timestamp


def replay_recording(recording: NativeRecording) -> Iterator[NativeCheckpoint]:
    economics = RecordedEconomics(
        recording.minimum_stop_distance,
        recording.session_windows,
        {(p.direction, p.volume, p.entry, p.exit_price): p.value for p in recording.profits},
        {(m.volume, m.entry): m.value for m in recording.margins},
        deque(recording.operations),
        recording.events[0].view,
    )
    execution = RecordedExecutionReplay(
        ReplayConfig(economics, initial_balance=recording.initial_balance, inputs=recording.inputs), "recorded"
    )
    market = MarketState(recording.inputs, execution)
    for sequence, event in enumerate(recording.events):
        if isinstance(event, RecordedInit):
            initialize_market(market, execution, event)
            time = event.time
        elif isinstance(event, RecordedTick):
            execution.update_view(event.view)
            market.step(
                event.time,
                event.day,
                event.bar_time,
                event.bar_open,
                event.bid,
                event.ask,
                list(event.history),
                list(event.zones),
            )
            time = event.time
        else:
            execution.on_deal(event.deal, event.view, event.bid, event.ask)
            time = event.deal.time
        state = shared_trace(market.state, execution)
        state.update(
            {
                "g_bar_time": timestamp(market.bar),
                "g_prev_bid": market.previous_bid,
                "g_trend": int(market.trend),
                "g_ref_high": max(c[1] for c in market.history[-3:]),
                "g_ref_low": min(c[2] for c in market.history[-3:]),
            }
        )
        yield NativeCheckpoint(sequence=sequence, kind=event.kind, time=time, state=state)
    economics.assert_consumed()


def initialize_market(market: MarketState, execution: RecordedExecutionReplay, event: RecordedInit) -> None:
    if len(event.history) < 3:
        raise ValueError("MT5 initialization requires at least three native closed candles")
    execution._begin_tick(event.bid, event.ask)
    execution.update_view(event.view)
    market._change_day(event.day, list(event.zones), event.time)
    market.bar = execution.bar = event.bar_time
    market.history = execution.closed_bars = list(event.history)
    market.previous_bid = execution.previous_bid = event.bid
    execution.previous_ask = event.ask
    market.state.bar_open = execution.bar_open = event.bar_open
    for state in market.state.zones:
        state.buy_engaged = state.sell_engaged = state.zone.low <= event.bar_open <= state.zone.high
    execution.detect_restart(event.time, event.has_ea_deal_today, event.bid, event.ask)


def compare_checkpoints(expected: list[NativeCheckpoint], actual: list[NativeCheckpoint]) -> str | None:
    for index, (left, right) in enumerate(zip(expected, actual, strict=False)):
        difference = first_difference(left.model_dump(mode="json"), right.model_dump(mode="json"))
        if difference:
            return f"event {index} ({left.time.isoformat()} {left.kind}): {difference}"
    if len(expected) != len(actual):
        return f"event count: {len(actual)} != {len(expected)}"
    if not expected:
        return "No checkpoints: empty evidence cannot establish parity"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("--reference", type=Path, required=True, help="Matching MQ5 source for hash validation")
    parser.add_argument("--expected", type=Path, help="Normalized native checkpoint JSONL")
    parser.add_argument("--output", type=Path, required=True, help="Python checkpoint JSONL")
    args = parser.parse_args()
    source = args.recording.read_bytes()
    recording = NativeRecording.model_validate_json(source)
    if hashlib.sha256(args.reference.read_bytes()).hexdigest() != recording.reference_sha256:
        raise ValueError("MQ5 reference hash does not match recording")
    actual = list(replay_recording(recording))
    difference = None
    if args.expected is not None:
        expected = [
            NativeCheckpoint.model_validate_json(line)
            for line in args.expected.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        difference = compare_checkpoints(expected, actual)
    args.output.write_text("\n".join(c.model_dump_json() for c in actual) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "recording_sha256": hashlib.sha256(source).hexdigest(),
                "provenance": recording.provenance,
                "checkpoints": len(actual),
                "compared": args.expected is not None,
                "difference": difference,
            }
        )
    )
    return 1 if difference else 0


if __name__ == "__main__":
    raise SystemExit(main())
