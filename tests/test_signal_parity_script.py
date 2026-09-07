from pathlib import Path


def test_signal_parity_script_uses_shared_replay_and_requires_all_families() -> None:
    source = (Path(__file__).parents[1] / "scripts" / "compare_signal_parity.py").read_text(
        encoding="utf-8"
    )
    assert "load_mt5_tick_bars" in source
    assert "build_replay_days" in source
    assert "ReplayRunner" in source
    for family in ("breakout", "reversal", "pullback"):
        assert family in source
