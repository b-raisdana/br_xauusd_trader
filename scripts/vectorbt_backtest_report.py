import sys
from pathlib import Path

import pandas as pd
import typer
import vectorbt as vbt

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "src"))

from application.xauusd_trading_strategy_1.global_state_variable import (  # noqa: E402
    StrategyRuntimeState,
)
from application.xauusd_trading_strategy_1.lifecycle import (  # noqa: E402
    RuntimeEnvironment,
    Tick,
)
from application.xauusd_trading_strategy_1.on_tick import on_tick  # noqa: E402
from application.xauusd_trading_strategy_1.settings import (  # noqa: E402
    StrategySettings,
)
from config.config import app_config  # noqa: E402

app = typer.Typer()


@app.command()
def generate_backtest_report(
    csv_path: str = typer.Option(
        "data/random_ohlcv.csv",
        "--csv-path",
        help="Path to OHLCV CSV data file",
    ),
    output_path: str = typer.Option(
        "docs/todo/on_tick_vectorbt_report.csv",
        "--output-path",
        help="Path to save the backtest report CSV",
    ),
) -> pd.DataFrame:
    csv_path = str(app_config.root_path / csv_path)
    output_path = str(app_config.root_path / output_path)

    df = pd.read_csv(csv_path, parse_dates=["Datetime"], index_col="Datetime")
    sd = vbt.SyntheticData.from_data({"XAUUSD": df}, download_kwargs={})
    close = sd.get("Close")
    open_ = sd.get("Open")
    high = sd.get("High")
    low = sd.get("Low")

    settings = StrategySettings(
        run_current_event_loop=True,
        emit_time_basis_probe=True,
    )
    runtime = StrategyRuntimeState()
    environment = RuntimeEnvironment()

    entries = pd.Series(False, index=close.index)
    exits = pd.Series(False, index=close.index)
    handled_flags = pd.Series(False, index=close.index)

    for i in range(len(close)):
        tick = Tick(time=close.index[i], bid=float(close.iloc[i]), ask=float(close.iloc[i]))
        result = on_tick(tick, settings, runtime, environment, None)
        handled_flags.iloc[i] = result.handled
        if result.handled:
            entries.iloc[i] = True
        else:
            exits.iloc[i] = True

    entries.iloc[0] = True

    port = vbt.Portfolio.from_signals(
        close=close,
        entries=entries,
        exits=exits,
        init_cash=app_config.initial_cash,
        fees=0.0002,
        slippage=0.0002,
        freq="15min",
    )

    report = pd.DataFrame(
        {
            "Datetime": close.index,
            "Open": open_.values,
            "High": high.values,
            "Low": low.values,
            "Close": close.values,
            "Entry": entries.values,
            "Exit": exits.values,
            "OnTick_Handled": handled_flags.values,
            "Portfolio_Value": port.value(),
            "Returns": port.returns(),
        }
    )
    report.to_csv(output_path, index=False)

    typer.echo(f"Report saved to {output_path}")
    typer.echo(f"Rows: {len(report)}")
    typer.echo(f"Entries: {report['Entry'].sum()}")
    typer.echo(f"Exits: {report['Exit'].sum()}")
    typer.echo(f"Final Portfolio Value: {float(report['Portfolio_Value'].iloc[-1]):.4f}")

    return report


def main() -> None:
    app()


if __name__ == "__main__":
    main()
