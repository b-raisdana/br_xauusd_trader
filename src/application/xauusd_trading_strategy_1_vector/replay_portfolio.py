"""Replay-funded reporting over genuine Vectorbt trade records and real tick equity.

Vectorbt receives already-accepted quantities with unlimited simulation funding.
Its artificial cash account is never used for replay returns or risk statistics;
those use replay cashflows, executable quote sides and original UTC timestamps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from br_pre_commit import pandera_validate
from domain.schemas.common.base_dataframe import EquityTimeseries, StatsDataFrame
from helper.importer import pt

from .domain.execution_schema import CloseEvents, FillEvents, StreamEvents

if TYPE_CHECKING:
    from vectorbt import Portfolio


from types import SimpleNamespace


class ReplayPortfolio:
    def __init__(
        self,
        portfolio: Portfolio | None,
        equity: pt.DataFrame[EquityTimeseries],
        initial_cash: float,
        fills: pt.DataFrame[FillEvents],
        closes: pt.DataFrame[CloseEvents],
    ) -> None:
        self._portfolio = portfolio
        self._equity = equity
        self._initial_cash = float(initial_cash)
        self.orders = portfolio.orders if portfolio is not None else SimpleNamespace(records=pd.DataFrame())
        if portfolio is None:
            records = pd.DataFrame(columns=["col", "size", "entry_price", "exit_price", "pnl", "status"])
        else:
            records = portfolio.trades.records.copy()
            position_keys = fills[["stream_id", "position_id"]].drop_duplicates()
            metadata = position_keys.merge(fills, on=["stream_id", "position_id"], validate="one_to_one")
            metadata = metadata.merge(
                closes[["stream_id", "position_id", "close_time"]],
                on=["stream_id", "position_id"],
                how="left",
                validate="one_to_one",
            )
            col = records["col"].to_numpy(dtype=int)
            records["stream_id"] = metadata.stream_id.to_numpy()[col]
            records["position_id"] = metadata.position_id.to_numpy()[col]
            records["entry_time"] = metadata.fill_time.to_numpy()[col]
            records["exit_time"] = metadata.close_time.to_numpy()[col]
            records["duration"] = pd.to_datetime(records.exit_time, utc=True) - pd.to_datetime(
                records.entry_time, utc=True
            )
        self.trades = SimpleNamespace(records=records)

    @property
    def init_cash(self) -> float | pd.Series:
        if len(self._equity.columns) == 1:
            return self._initial_cash
        return pd.Series(self._initial_cash, index=self._equity.columns)

    def _scalar(self, values: pd.Series) -> float | pd.Series:
        return float(values.iloc[0]) if len(values) == 1 else values

    @pandera_validate
    def value(self) -> pd.Series | pt.DataFrame[EquityTimeseries]:
        return self._equity.iloc[:, 0] if len(self._equity.columns) == 1 else self._equity

    def total_return(self) -> float | pd.Series:
        return self._scalar(self._equity.iloc[-1] / self._initial_cash - 1)

    def annualized_return(self) -> float | pd.Series:
        seconds = (self._equity.index[-1] - self._equity.index[0]).total_seconds()
        if seconds <= 0:
            return self._scalar(pd.Series(np.nan, index=self._equity.columns))
        years = seconds / (365.25 * 86400)
        ratio = self._equity.iloc[-1] / self._initial_cash
        # Negative equity has no defined geometric annualization.
        return self._scalar(ratio.where(ratio.gt(0)).pow(1 / years) - 1)

    def max_drawdown(self) -> float | pd.Series:
        peak = self._equity.cummax().clip(lower=self._initial_cash)
        return self._scalar((self._equity / peak - 1).min())

    def sharpe_ratio(self) -> float | pd.Series:
        daily = self._equity.resample("1D").last().ffill()
        returns = daily.pct_change().dropna()
        value = returns.mean() / returns.std(ddof=1) * np.sqrt(365.25)
        return self._scalar(value)

    def calmar_ratio(self) -> float | pd.Series:
        annual = self.annualized_return()
        drawdown = self.max_drawdown()
        if isinstance(drawdown, pd.Series):
            return annual / -drawdown.replace(0, np.nan)
        return annual / -drawdown if drawdown < 0 else np.nan

    @pandera_validate
    def stats(self) -> pt.DataFrame[StatsDataFrame]:
        stats = pd.DataFrame(index=self._equity.columns)
        stats["Start"] = self._equity.index[0]
        stats["End"] = self._equity.index[-1]
        stats["Initial_cash"] = self._initial_cash
        stats["Final_value"] = self._equity.iloc[-1]
        stats["Total_return_pct"] = (self._equity.iloc[-1] / self._initial_cash - 1) * 100
        stats["Max_drawdown_pct"] = -pd.Series(self.max_drawdown(), index=stats.index) * 100
        stats["Annualized_return_pct"] = pd.Series(self.annualized_return(), index=stats.index) * 100
        stats["Sharpe_ratio"] = pd.Series(self.sharpe_ratio(), index=stats.index)
        records = self.trades.records
        if len(records):
            by = records.groupby("stream_id", sort=False)
            stats["Trades"] = by.size().reindex(stats.index, fill_value=0)
            stats["Recorded_trade_PnL"] = by.pnl.sum().reindex(stats.index, fill_value=0)
        else:
            stats["Trades"] = 0
            stats["Recorded_trade_PnL"] = 0.0
        return stats


@pandera_validate
def report_from_events(
    ticks: pt.DataFrame[StreamEvents],
    fills: pt.DataFrame[FillEvents],
    closes: pt.DataFrame[CloseEvents],
    initial_cash: float,
) -> ReplayPortfolio:
    """O(ticks + trades) storage; no dense ticks-by-all-positions expansion."""
    import logging
    import os

    os.environ.setdefault("MPLBACKEND", "Agg")
    import vectorbt as vbt

    logging.getLogger("numba").setLevel(logging.WARNING)

    market = ticks.reset_index()
    if "broker" in market.columns and "symbol" in market.columns:
        market["stream_id"] = market.broker.astype(str) + "_" + market.symbol.astype(str)
    keys = ["stream_id", "stream_tick"]
    if market.duplicated(keys).any():
        raise ValueError("Report market tick identity must be unique")
    market = market.sort_values(["precise_time", "stream_id", "stream_tick"], kind="stable")
    times = pd.DatetimeIndex(market.precise_time.unique()).sort_values()
    streams = pd.Index(market.stream_id.unique(), name="stream_id")
    equity = pd.DataFrame(initial_cash, index=times, columns=streams, dtype=float)
    required_fills = {
        "stream_id",
        "stream_tick",
        "event_ordinal",
        "position_id",
        "position_direction",
        "fill_time",
        "fill_price",
        "volume",
        "vectorbt_size",
        "cost",
    }
    required_closes = {
        "stream_id",
        "stream_tick",
        "event_ordinal",
        "position_id",
        "position_direction",
        "close_time",
        "close_price",
        "exit_cost",
    }
    if not required_fills.issubset(fills.columns) or not required_closes.issubset(closes.columns):
        raise ValueError("Replay report requires complete identity, execution price, size and cost artifacts")
    if fills.duplicated(["stream_id", "position_id"]).any() or closes.duplicated(["stream_id", "position_id"]).any():
        raise ValueError("Replay positions must have one fill and at most one close")
    if fills.empty:
        return ReplayPortfolio(None, equity, initial_cash, fills, closes)
    if (
        not np.isfinite(fills[["fill_price", "vectorbt_size", "cost"]].to_numpy(dtype=float)).all()
        or fills.vectorbt_size.le(0).any()
    ):
        raise ValueError("Replay report requires finite prices, costs and positive economics-aligned sizes")
    if fills.cost.lt(0).any() or (
        len(closes)
        and (
            closes.exit_cost.lt(0).any()
            or not np.isfinite(closes[["close_price", "exit_cost"]].to_numpy(dtype=float)).all()
        )
    ):
        raise ValueError("Replay recorded prices/costs must be finite and costs nonnegative")
    absent = closes.merge(
        fills[["stream_id", "position_id"]], how="left", on=["stream_id", "position_id"], indicator=True
    )
    if absent._merge.eq("left_only").any():
        raise ValueError("Replay close references a position without a fill")
    trades = fills.merge(
        closes, on=["stream_id", "position_id"], how="left", suffixes=("_entry", "_exit"), validate="one_to_one"
    )
    for events, time_column in ((fills, "fill_time"), (closes, "close_time")):
        linked = events.merge(market[keys + ["precise_time"]], on=keys, how="left", validate="many_to_one")
        if linked.precise_time.isna().any() or not pd.to_datetime(linked[time_column], utc=True).equals(
            pd.to_datetime(linked.precise_time, utc=True)
        ):
            raise ValueError("Replay report event time/tick identity differs from market data")
    if len(closes):
        invalid = trades.close_time.notna() & (
            (trades.stream_tick_exit < trades.stream_tick_entry)
            | (
                (trades.stream_tick_exit == trades.stream_tick_entry)
                & (trades.event_ordinal_exit <= trades.event_ordinal_entry)
            )
        )
        if invalid.any():
            raise ValueError("Replay close must follow its fill in original event order")
        mismatch = trades.close_time.notna() & trades.position_direction_entry.ne(trades.position_direction_exit)
        if mismatch.any():
            raise ValueError("Replay position direction changed between fill and close")
    prices = np.empty((2, len(trades)), dtype=float)
    prices[0] = trades.fill_price
    sizes = trades.vectorbt_size.to_numpy(dtype=float)
    fees = np.zeros((2, len(trades)))
    fees[0] = trades.cost
    closed = trades.close_time.notna().to_numpy()
    fees[1, closed] = trades.loc[closed, "exit_cost"]
    last_quotes = market.groupby("stream_id", sort=False).last()
    long = trades.position_direction_entry.eq(0).to_numpy()
    marks = np.where(long, trades.stream_id.map(last_quotes.bid), trades.stream_id.map(last_quotes.ask))
    prices[1] = trades.close_price.where(trades.close_time.notna(), pd.Series(marks, index=trades.index))
    entry = np.vstack([np.ones(len(trades), dtype=bool), np.zeros(len(trades), dtype=bool)])
    exit_mask = np.vstack([np.zeros(len(trades), dtype=bool), closed])
    columns = pd.MultiIndex.from_frame(trades[["stream_id", "position_id"]])
    portfolio = vbt.Portfolio.from_signals(
        close=pd.DataFrame(prices, columns=columns),
        entries=entry & long,
        exits=exit_mask & long,
        short_entries=entry & ~long,
        short_exits=exit_mask & ~long,
        size=np.broadcast_to(sizes, (2, len(trades))),
        size_type="amount",
        fixed_fees=fees,
        fees=0.0,
        slippage=0.0,
        init_cash=np.inf,
        cash_sharing=True,
        group_by=columns.get_level_values("stream_id"),
        freq=None,
        allow_partial=False,
    )
    actual = portfolio.orders.records
    expected = np.sort(np.concatenate([sizes, sizes[closed]]))
    if len(actual) != len(expected) or not np.allclose(np.sort(actual["size"]), expected, atol=1e-12, rtol=1e-12):
        raise ValueError("Vectorbt changed replay execution quantities")
    # One vector slice per trade interval, not one Python iteration per tick.
    for stream_id, stream in market.groupby("stream_id", sort=False):
        stream = stream.sort_values("stream_tick", kind="stable").reset_index(drop=True)
        amounts = np.zeros(len(stream), dtype=float)
        ordinals = stream.stream_tick.to_numpy()
        selected = trades.loc[trades.stream_id.eq(stream_id)]
        for row in selected.itertuples(index=False):
            start = np.searchsorted(ordinals, row.stream_tick_entry)
            end = np.searchsorted(ordinals, row.stream_tick_exit) if pd.notna(row.close_time) else len(stream)
            sign = 1.0 if row.position_direction_entry == 0 else -1.0
            quotes = stream.bid.to_numpy() if sign == 1 else stream.ask.to_numpy()
            amounts[start:end] += sign * (quotes[start:end] - row.fill_price) * row.vectorbt_size - row.cost
            if end < len(stream):
                pnl = sign * (row.close_price - row.fill_price) * row.vectorbt_size - row.cost - row.exit_cost
                amounts[end:] += pnl
                if hasattr(row, "realized_pnl") and not np.isclose(row.realized_pnl, pnl, atol=1e-9, rtol=1e-10):
                    raise ValueError("Replay realized PnL differs from recorded execution economics")
        marked = pd.Series(initial_cash + amounts, index=pd.DatetimeIndex(stream.precise_time))
        equity[stream_id] = marked.groupby(level=0, sort=False).last().reindex(times).ffill().fillna(initial_cash)
    return ReplayPortfolio(portfolio, equity, initial_cash, fills, closes)
