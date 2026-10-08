"""Backtest runner that feeds strategy results into vectorbt for performance reporting."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
from br_py_log_n_profile import log_d, profile_it

from application.xauusd_trading_strategy_1_vector.domain.schema import VectorbtBacktestInput
from br_pre_commit import pandera_validate
from domain.xau_usd.enums import XauExecutionStatus
from helper.importer import pt
from infrastructure.result_processing.io import ResultFilesManifest

if TYPE_CHECKING:
    from vectorbt import Portfolio
else:
    # Pandera resolves annotations at import time; keep vectorbt out of startup.
    Portfolio = Any


@profile_it
def _extract_signals(
    result: pt.DataFrame[VectorbtBacktestInput],
) -> tuple[pt.Series[float], pt.Series[bool], pt.Series[bool]]:
    """Extract entry/exit signals and price series from strategy results.

    Args:
        result: DataFrame with VectorbtBacktestInput columns and MultiIndex
            (broker, symbol, datetime, date).

    Returns:
        Tuple of (close_prices, entries, exits) Series indexed by datetime.
    """
    if result.empty:
        raise ValueError("Result DataFrame is empty")

    # Use bid as the close price for the backtest
    close = result["bid"].astype(float)  # .copy()

    # Detect new position openings: position_id is not null, status is FILLED,
    # and the position_id differs from the previous tick (new position).
    position_id = result["position_id"]
    position_status = result["position_status"]

    previous_position_id = position_id.shift(1)
    is_new_position = (
        position_id.notna()
        & position_status.eq(XauExecutionStatus.FILLED)
        & (previous_position_id.isna() | position_id.ne(previous_position_id).fillna(False)).astype(bool)
    )
    entries = is_new_position.fillna(False).astype(bool)

    # Exits happen when a position is closed
    is_exit = position_status.eq(XauExecutionStatus.CLOSED)
    exits = is_exit.fillna(False).astype(bool)

    return close, entries, exits


def _extract_replay_signals(
    ticks: pd.DataFrame,
    fills: pd.DataFrame,
    closes: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Project replay fills and closes into aligned per-position Vectorbt signal matrices."""
    if ticks.empty:
        raise ValueError("Replay backtest requires market ticks")
    if fills.empty:
        raise ValueError("Replay backtest requires at least one filled position")
    if "stream_tick" not in ticks or "stream_id" not in fills or "stream_tick" not in fills:
        raise ValueError("Replay backtest requires stable stream_id and stream_tick keys")

    tick_keys = pd.DataFrame(
        {
            "stream_id": [
                f"{broker}_{symbol}"
                for broker, symbol in zip(
                    ticks.index.get_level_values("broker"),
                    ticks.index.get_level_values("symbol"),
                    strict=True,
                )
            ],
            "stream_tick": ticks["stream_tick"].to_numpy(),
            "_tick_row": range(len(ticks)),
        }
    )
    if (
        "position_id" not in fills
        or "position_direction" not in fills
        or "position_id" not in closes
        or "position_direction" not in closes
    ):
        raise ValueError("Replay fill and close artifacts must include position identity and direction")
    positions = pd.Index(fills.position_id.dropna().unique(), name="position_id")
    if len(positions) == 0:
        raise ValueError("Replay fill artifacts contain no position identifiers")
    entries = pd.DataFrame(False, index=range(len(ticks)), columns=positions)
    exits = pd.DataFrame(False, index=range(len(ticks)), columns=positions)
    short_entries = entries.copy()
    short_exits = exits.copy()
    close = pd.DataFrame(
        {position_id: ticks["bid"].astype(float).to_numpy() for position_id in positions},
        index=ticks.index,
    )

    for events, long_signals, short_signals, price_column in (
        (fills, entries, short_entries, "fill_price"),
        (closes, exits, short_exits, "close_price"),
    ):
        if events.empty:
            continue
        keyed_events = events.merge(tick_keys, on=["stream_id", "stream_tick"], how="left", validate="many_to_one")
        if keyed_events["_tick_row"].isna().any():
            raise ValueError("Replay events reference ticks absent from the report input")
        if keyed_events.duplicated(["_tick_row", "position_id"]).any():
            raise ValueError("Replay has duplicate lifecycle events for a position at one tick")
        for tick_row, position_id, direction, event_price in zip(
            keyed_events["_tick_row"],
            keyed_events["position_id"],
            keyed_events["position_direction"],
            keyed_events[price_column],
            strict=True,
        ):
            if position_id not in long_signals.columns:
                raise ValueError(f"Replay event references unknown position {position_id!r}")
            signals = long_signals if direction == XauDirection.BUY else short_signals
            signals.at[tick_row, position_id] = True
            if price_column == "close_price":
                close.iloc[tick_row, close.columns.get_loc(position_id)] = event_price

    entries.index = exits.index = short_entries.index = short_exits.index = close.index
    return close, entries, exits, short_entries, short_exits


@profile_it
@pandera_validate
def run_vectorbt_backtest(
    manifest: ResultFilesManifest,
    *,
    initial_cash: float = 100_000.0,
    fees: float = 0.0002,
    slippage: float = 0.0002,
    freq: str = "1min",
) -> Portfolio:
    """Run a vectorbt backtest on strategy results.

    Extracts entry/exit signals from position tracking columns and runs
    a vectorbt Portfolio simulation.

    Args:
        result: DataFrame with VectorbtBacktestInput columns and MultiIndex
            (broker, symbol, datetime, date).
        initial_cash: Starting cash for the backtest.
        fees: Fee rate as a fraction of trade value.
        slippage: Slippage rate as a fraction of trade value.
        freq: Frequency of the data (e.g. '1min', '15min').

    Returns:
        vectorbt Portfolio object with backtest results.
    """
    # log_w(NOT_TESTED)
    position_days = manifest.successful_days("positions")
    if not position_days:
        raise ValueError(
            "Vectorbt backtest requires position artifacts, but the native signals-only run produced none. "
            "Run an execution replay first."
        )
    ticks = pd.concat([manifest.read_daily_ticks(day) for day in manifest.successful_days("ticks")])
    signal_states = pd.concat(
        [manifest.read_daily_signal_state(day) for day in manifest.successful_days("signal_state")]
    )
    if not ticks.index.equals(signal_states.index):
        raise ValueError("Replay report ticks and native stream state must have identical indexes")
    report_ticks = ticks.copy()
    report_ticks["stream_tick"] = signal_states["stream_tick"].to_numpy()
    stream_ids = pd.Series(
        [
            f"{broker}_{symbol}"
            for broker, symbol in zip(
                ticks.index.get_level_values("broker"), ticks.index.get_level_values("symbol"), strict=True
            )
        ],
        index=ticks.index,
    )
    keyed_ticks = report_ticks.copy()
    keyed_ticks["stream_id"] = stream_ids
    fills = pd.concat(
        [manifest.read_daily_execution_artifact("fills", day) for day in manifest.successful_days("fills")],
        ignore_index=True,
    )
    closes = pd.concat(
        [manifest.read_daily_execution_artifact("closes", day) for day in manifest.successful_days("closes")],
        ignore_index=True,
    )
    close, entries, exits, short_entries, short_exits = _extract_replay_signals(keyed_ticks, fills, closes)

    import inspect
    import os

    log_d(f"MPLBACKEND ={os.environ.get('MPLBACKEND')}")
    os.environ.setdefault("MPLBACKEND", "Agg")
    log_d(f"after defaulting MPLBACKEND ={os.environ.get('MPLBACKEND')}")

    # import matplotlib
    # log_d("matplotlib backend =", matplotlib.get_backend())
    # log_d("matplotlib config =", matplotlib.matplotlib_fname())

    log_d("Now we try to import vectorbt as vbt")

    import vectorbt as vbt

    log_d(f"inspect.signature(vbt.Portfolio.from_signals):{inspect.signature(vbt.Portfolio.from_signals)}")
    log_d(f"inspect.signature(vbt.Portfolio.from_order_func):{inspect.signature(vbt.Portfolio.from_order_func)}")

    logging.getLogger("numba").setLevel(logging.WARNING)
    portfolio = vbt.Portfolio.from_signals(
        close=close.to_numpy(),
        entries=entries.to_numpy(),
        exits=exits.to_numpy(),
        short_entries=short_entries.to_numpy(),
        short_exits=short_exits.to_numpy(),
        init_cash=initial_cash,
        fees=fees,
        slippage=slippage,
        freq=freq,
        cash_sharing=True,
    )

    return portfolio


@profile_it
@pandera_validate
def print_backtest_report(
    manifest: ResultFilesManifest,
    *,
    report_file: str | None = None,
    trades_file: str | None = None,
) -> None:
    """Print a comprehensive backtest report from strategy results.

    Runs the vectorbt backtest and prints performance metrics including
    returns, drawdowns, trade statistics, and risk-adjusted measures.

    Args:
        result: DataFrame with strategy results (VectorbtBacktestInput schema).
    """
    # log_w(NOT_TESTED)
    portfolio = run_vectorbt_backtest(manifest)

    print("\n=== Vectorbt Backtest Report ===")

    # Basic portfolio stats
    print(f"Initial cash: {portfolio.init_cash:,.2f}")
    final_value = float(portfolio.value().iloc[-1])
    print(f"Final value: {final_value:,.2f}")
    print(f"Total return: {portfolio.total_return():.2%}")

    # Risk metrics
    try:
        print(f"Annualized return: {portfolio.annualized_return():.2%}")
    except Exception:
        print("Annualized return: N/A")
    try:
        print(f"Sharpe ratio: {portfolio.sharpe_ratio():.4f}")
    except Exception:
        print("Sharpe ratio: N/A")
    try:
        print(f"Max drawdown: {portfolio.max_drawdown():.2%}")
    except Exception:
        print("Max drawdown: N/A")
    try:
        print(f"Calmar ratio: {portfolio.calmar_ratio():.4f}")
    except Exception:
        print("Calmar ratio: N/A")

    # Trade statistics
    trades_df = portfolio.trades.records
    if not trades_df.empty:
        print(f"\nTotal trades: {len(trades_df)}")
        winning = trades_df["pnl"].gt(0).sum()
        losing = trades_df["pnl"].lt(0).sum()
        print(f"Winning trades: {winning}")
        print(f"Losing trades: {losing}")
        if len(trades_df) > 0:
            print(f"Win rate: {trades_df['pnl'].gt(0).mean():.2%}")
        print(f"Average trade PnL: {trades_df['pnl'].mean():,.2f}")
        print(f"Best trade: {trades_df['pnl'].max():,.2f}")
        print(f"Worst trade: {trades_df['pnl'].min():,.2f}")

    if report_file is not None:
        save_backtest_report(portfolio, report_file)
    if trades_file is not None:
        save_backtest_trades(portfolio, trades_file)

    print("=== End Backtest Report ===\n")


@profile_it
def save_backtest_report(
    portfolio: Portfolio,
    output_file: str,
) -> None:
    """Save backtest report statistics to a file.

    Args:
        portfolio: vectorbt Portfolio object.
        output_file: Path to output file (.parquet or .csv).
    """
    # log_w(NOT_TESTED)
    stats = portfolio.stats()
    stats_df = stats.to_frame("value")
    stats_df.index.name = "metric"

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    output_path = Path(output_file)
    if output_path.suffix.lower() == ".csv":
        stats_df.to_csv(output_file)
    else:
        # Parquet cannot serialize mixed object types (lists/tuples in some stats).
        stats_df["value"] = stats_df["value"].astype(str)
        stats_df.to_parquet(output_file)
    print(f"Backtest report saved to {output_file}")


@profile_it
def save_backtest_trades(
    portfolio: Portfolio,
    output_file: str,
) -> None:
    """Save backtest trade records to a file.

    Args:
        portfolio: vectorbt Portfolio object.
        output_file: Path to output file (.parquet or .csv).
    """
    # log_w(NOT_TESTED)
    trades = portfolio.trades.records

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    output_path = Path(output_file)
    if output_path.suffix.lower() == ".csv":
        pd.DataFrame(trades).to_csv(output_file, index=False)
    else:
        pd.DataFrame(trades).to_parquet(output_file, index=False)
    print(f"Backtest trades saved to {output_file}")
