from pydantic import BaseModel, ConfigDict, Field


class StrategySettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enable_trading: bool = False
    emit_time_basis_probe: bool = False
    observe_native_outcomes: bool = False
    strategy_magic: int = 0
    run_current_event_loop: bool = False
    enable_tester_execution: bool = False
    strategy_capital: float = Field(default=200.0, gt=0.0)
    simulate_same_day_restart: bool = False
