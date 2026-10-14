"""Report acceptance: leverage, original time, streams, empty/open trades and exports."""

import numpy as np
import pandas as pd
import pytest
from pandera.errors import SchemaError, SchemaErrors

from application.xauusd_trading_strategy_1_vector.backtest import save_backtest_report, save_backtest_trades
from application.xauusd_trading_strategy_1_vector.domain.execution_schema import StreamEvents
from application.xauusd_trading_strategy_1_vector.replay_portfolio import _portfolio_arrays, report_from_events


def _make_stream_events(rows):
    df = pd.DataFrame(rows)
    df["stream_id"] = df.broker.astype(str) + "_" + df.symbol.astype(str)
    df["broker_day"] = df.precise_time.dt.strftime("%Y-%m-%d")
    df["bar_time"] = df.precise_time.dt.floor("15min")
    df["bar_open"] = df.bid
    return StreamEvents.validate(df[StreamEvents.to_schema().columns.keys()]).reset_index(drop=True)


def inputs(stream_count=2, same_tick=False, open_trade=False):
    times = pd.DatetimeIndex(["2026-07-29 09:00", "2026-07-29 11:00"], tz="UTC").as_unit("ns")
    rows, fills, closes = [], [], []
    for number in range(stream_count):
        broker = f"broker{number}"
        stream_id = f"{broker}_XAUUSD"
        base = 2500.0 + number * 100
        for tick, time in enumerate(times):
            rows.append(
                {
                    "broker": broker,
                    "symbol": "XAUUSD",
                    "date": time.normalize(),
                    "precise_time": time,
                    "stream_tick": tick,
                    "bid": base + tick,
                    "ask": base + tick + 0.2,
                }
            )
        fills.append(
            {
                "stream_id": stream_id,
                "stream_tick": 0,
                "event_ordinal": 1,
                "position_id": "P1",
                "position_direction": number % 2,
                "request_id": f"R{number}",
                "fill_time": times[0],
                "fill_price": base + 0.2 if number % 2 == 0 else base,
                "fill_side": "ask" if number % 2 == 0 else "bid",
                "volume": 0.01,
                "vectorbt_size": 1.0,
                "cost": 0.3,
            }
        )
        close_tick = 0 if same_tick else 1
        close_price = base + close_tick if number % 2 == 0 else base + close_tick + 0.2
        gross = (close_price - fills[-1]["fill_price"]) * (1 if number % 2 == 0 else -1)
        closes.append(
            {
                "stream_id": stream_id,
                "stream_tick": close_tick,
                "event_ordinal": 2,
                "position_id": "P1",
                "position_direction": number % 2,
                "request_id": f"R{number}",
                "close_time": times[close_tick],
                "close_price": close_price,
                "close_reason": "TP",
                "exit_cost": 0.4,
                "realized_pnl": gross - 0.7,
            }
        )
    ticks = _make_stream_events(rows)
    closes = pd.DataFrame(closes)
    return ticks, pd.DataFrame(fills), closes.iloc[:0] if open_trade else closes


@pytest.mark.parametrize("streams", [1, 2])
@pytest.mark.parametrize("same_tick", [False, True])
@pytest.mark.integration
@pytest.mark.slow
def test_leveraged_report_preserves_fills_costs_streams_and_real_time(streams, same_tick, tmp_path):
    ticks, fills, closes = inputs(streams, same_tick)
    portfolio = report_from_events(ticks, fills, closes, 200.0)
    records = portfolio.trades.records
    assert len(records) == streams
    assert portfolio.orders.records["size"].tolist() == [1.0] * (2 * streams)
    assert records["pnl"].tolist() == pytest.approx(closes.realized_pnl.tolist())
    assert records.position_id.tolist() == ["P1"] * streams
    assert records.duration.tolist() == [pd.Timedelta(0 if same_tick else "2h")] * streams
    final = portfolio.value().iloc[-1]
    expected = 200.0 + closes.realized_pnl.to_numpy()
    assert np.asarray(final) == pytest.approx(expected if streams > 1 else expected[0])
    stats = portfolio.stats()
    assert "Start" in stats.columns
    report, trades = tmp_path / "report.parquet", tmp_path / "trades.parquet"
    save_backtest_report(portfolio, str(report))
    save_backtest_trades(portfolio, str(trades))
    assert report.stat().st_size > 0 and trades.stat().st_size > 0
    saved = pd.read_parquet(trades)
    assert saved.pnl.tolist() == pytest.approx(closes.realized_pnl.tolist())


def test_zero_fill_report_returns_flat_equity_without_vectorbt():
    ticks, fills, closes = inputs(1)
    empty = report_from_events(ticks, fills.iloc[:0], closes.iloc[:0], 200.0)
    assert empty.trades.records.empty
    assert empty.value().tolist() == [200.0, 200.0]
    assert empty.total_return() == 0


def test_open_position_mark_uses_executable_quote_side():
    ticks, fills, closes = inputs(1, open_trade=True)
    market = ticks.reset_index()
    trades = fills.merge(closes, on=["stream_id", "position_id"], how="left", suffixes=("_entry", "_exit"))
    prices, fees, closed, long, sizes = _portfolio_arrays(trades, market)
    assert prices[:, 0].tolist() == [2500.2, 2501.0]
    assert fees[:, 0].tolist() == [0.3, 0.0]
    assert not closed[0]
    assert long[0]
    assert sizes.tolist() == [1.0]


def test_report_rejects_wrong_economics_or_event_identity():
    ticks, fills, closes = inputs(1)
    with pytest.raises(ValueError, match="PnL"):
        report_from_events(ticks, fills, closes.assign(realized_pnl=100.0), 200.0)
    with pytest.raises(ValueError, match="time/tick"):
        report_from_events(ticks, fills.assign(stream_tick=1), closes, 200.0)
    with pytest.raises(ValueError, match="follow"):
        report_from_events(
            ticks, fills, closes.assign(stream_tick=0, close_time=fills.fill_time, event_ordinal=0), 200.0
        )
    with pytest.raises((SchemaError, SchemaErrors), match="vectorbt_size"):
        report_from_events(ticks, fills.assign(vectorbt_size=np.nan), closes, 200.0)
