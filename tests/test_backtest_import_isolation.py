import os
import subprocess
import sys
from pathlib import Path


def test_strategy_startup_does_not_load_plotting_dependencies():
    repo = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(repo / "src")}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from typing import get_type_hints
import application.xauusd_trading_strategy_1_vector as strategy
import application.xauusd_trading_strategy_1_vector.__main__ as entrypoint
from application.xauusd_trading_strategy_1_vector import backtest
assert get_type_hints(backtest.run_vectorbt_backtest)["result"] is backtest.VectorbtBacktestInput
assert not ({"vectorbt", "matplotlib", "matplotlib.pyplot"} & sys.modules.keys())
""",
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
