import pandas as pd
import pytest
import vectorbt as vbt

from application.xauusd_trading_strategy_1.global_state_variable import StrategyRuntimeState
from application.xauusd_trading_strategy_1.lifecycle import (
    OnTickResult,
    RuntimeEnvironment,
    Tick,
)
from application.xauusd_trading_strategy_1.on_tick import (
    handle_tick,
    on_tick,
    process_current_event_loop_tick,
)
from application.xauusd_trading_strategy_1.settings import StrategySettings


class _MockEventLoop:
    def __init__(self, result: bool = True, fail_on_tick: int | None = None) -> None:
        self.result = result
        self.fail_on_tick = fail_on_tick
        self.processed: list[Tick] = []
        self.call_count = 0

    def process_tick(self, tick: Tick) -> bool:
        self.processed.append(tick)
        self.call_count += 1
        if self.fail_on_tick is not None and self.call_count == self.fail_on_tick:
            raise RuntimeError("mock failure")
        return self.result


@pytest.fixture
def ohlcv_df() -> pd.DataFrame:
    df = pd.read_csv("data/random_ohlcv.zip", compression="zip", parse_dates=["Datetime"], index_col="Datetime")
    return df


@pytest.fixture
def synthetic_bars(ohlcv_df: pd.DataFrame) -> vbt.SyntheticData:
    return vbt.SyntheticData.from_data({"XAUUSD": ohlcv_df}, download_kwargs={})


@pytest.fixture
def base_settings() -> StrategySettings:
    return StrategySettings(
        run_current_event_loop=True,
        emit_time_basis_probe=True,
    )


def make_tick(index, close_val) -> Tick:
    return Tick(time=index, bid=float(close_val), ask=float(close_val))


def test_scenario_1_normal_tick_processing(
    synthetic_bars: vbt.SyntheticData,
    base_settings: StrategySettings,
) -> None:
    close = synthetic_bars.get("Close")
    runtime = StrategyRuntimeState()
    mock_loop = _MockEventLoop(result=True)
    environment = RuntimeEnvironment()

    for i in range(len(close)):
        tick = make_tick(close.index[i], close.iloc[i])
        result = on_tick(tick, base_settings, runtime, environment, mock_loop)
        assert isinstance(result, OnTickResult)
        assert result.handled is True
        if i < 5:
            assert result.time_basis_probe_emitted is True
        else:
            assert result.time_basis_probe_emitted is False
        assert result.event_loop_failed is False

    assert runtime.time_basis_probe_count == 5
    assert mock_loop.call_count == len(close)


def test_scenario_2_probe_emit_limit(
    synthetic_bars: vbt.SyntheticData,
    base_settings: StrategySettings,
) -> None:
    close = synthetic_bars.get("Close")
    runtime = StrategyRuntimeState()
    mock_loop = _MockEventLoop(result=True)
    environment = RuntimeEnvironment()

    for i in range(len(close)):
        tick = make_tick(close.index[i], close.iloc[i])
        on_tick(tick, base_settings, runtime, environment, mock_loop)

    assert runtime.time_basis_probe_count == 5


def test_scenario_3_event_loop_disabled(
    synthetic_bars: vbt.SyntheticData,
) -> None:
    close = synthetic_bars.get("Close")
    settings = StrategySettings(
        run_current_event_loop=False,
        emit_time_basis_probe=True,
    )
    runtime = StrategyRuntimeState()
    mock_loop = _MockEventLoop(result=True)
    environment = RuntimeEnvironment()

    for i in range(len(close)):
        tick = make_tick(close.index[i], close.iloc[i])
        result = on_tick(tick, settings, runtime, environment, mock_loop)
        assert result.handled is True
        assert result.event_loop_failed is False

    assert mock_loop.call_count == 0
    assert runtime.time_basis_probe_count == 5


def test_scenario_4_event_loop_absent(
    synthetic_bars: vbt.SyntheticData,
    base_settings: StrategySettings,
) -> None:
    close = synthetic_bars.get("Close")
    runtime = StrategyRuntimeState()
    environment = RuntimeEnvironment()

    tick = make_tick(close.index[0], close.iloc[0])
    result = on_tick(tick, base_settings, runtime, environment, None)
    assert result.handled is False
    assert result.event_loop_failed is True

    assert runtime.event_loop_failure_reported is True

    second_result = on_tick(tick, base_settings, runtime, environment, None)
    assert second_result.event_loop_failed is True


def test_scenario_5_event_loop_exception(
    synthetic_bars: vbt.SyntheticData,
    base_settings: StrategySettings,
) -> None:
    close = synthetic_bars.get("Close")
    runtime = StrategyRuntimeState()
    mock_loop = _MockEventLoop(result=True, fail_on_tick=25)
    environment = RuntimeEnvironment()

    fail_result = None
    for i in range(len(close)):
        tick = make_tick(close.index[i], close.iloc[i])
        result = on_tick(tick, base_settings, runtime, environment, mock_loop)
        if i == 24:
            fail_result = result
            assert result.handled is False
            assert result.event_loop_failed is True

    assert fail_result is not None
    assert mock_loop.call_count == len(close)
    assert runtime.event_loop_failure_reported is True


def test_scenario_6_invalid_ticks(
    synthetic_bars: vbt.SyntheticData,
    base_settings: StrategySettings,
) -> None:
    close = synthetic_bars.get("Close")
    runtime = StrategyRuntimeState()
    mock_loop = _MockEventLoop(result=True)
    environment = RuntimeEnvironment()

    nan_tick = Tick(time=close.index[0], bid=float("nan"), ask=float("nan"))
    result = on_tick(nan_tick, base_settings, runtime, environment, mock_loop)
    assert isinstance(result, OnTickResult)
    assert result.time_basis_probe_emitted is False

    zero_tick = Tick(time=close.index[1], bid=0.0, ask=0.0)
    result = on_tick(zero_tick, base_settings, runtime, environment, mock_loop)
    assert isinstance(result, OnTickResult)
    assert result.time_basis_probe_emitted is False

    assert runtime.time_basis_probe_count == 0


def test_scenario_7_vectorbt_integration_loop(
    synthetic_bars: vbt.SyntheticData,
    base_settings: StrategySettings,
) -> None:
    close = synthetic_bars.get("Close")
    runtime = StrategyRuntimeState()
    mock_loop = _MockEventLoop(result=True)
    environment = RuntimeEnvironment()

    results = []
    for i in range(len(close)):
        tick = make_tick(close.index[i], close.iloc[i])
        result = on_tick(tick, base_settings, runtime, environment, mock_loop)
        results.append(result)

    assert len(results) == len(close)
    assert all(isinstance(r, OnTickResult) for r in results)
    assert all(r.handled is True for r in results)
    assert runtime.time_basis_probe_count == 5


def test_scenario_8_handle_tick_alias(
    synthetic_bars: vbt.SyntheticData,
    base_settings: StrategySettings,
) -> None:
    assert handle_tick is on_tick

    close = synthetic_bars.get("Close")
    runtime = StrategyRuntimeState()
    mock_loop = _MockEventLoop(result=True)
    environment = RuntimeEnvironment()

    tick = make_tick(close.index[0], close.iloc[0])
    result = handle_tick(tick, base_settings, runtime, environment, mock_loop)
    assert isinstance(result, OnTickResult)
    assert result.handled is True


def test_process_current_event_loop_tick_delegation(
    synthetic_bars: vbt.SyntheticData,
) -> None:
    close = synthetic_bars.get("Close")
    mock_loop = _MockEventLoop(result=True)

    tick = make_tick(close.index[0], close.iloc[0])
    result = process_current_event_loop_tick(tick, mock_loop)
    assert result is True
    assert mock_loop.call_count == 1


def test_process_current_event_loop_tick_failure(
    synthetic_bars: vbt.SyntheticData,
) -> None:
    close = synthetic_bars.get("Close")
    mock_loop = _MockEventLoop(result=False)

    tick = make_tick(close.index[0], close.iloc[0])
    result = process_current_event_loop_tick(tick, mock_loop)
    assert result is False
