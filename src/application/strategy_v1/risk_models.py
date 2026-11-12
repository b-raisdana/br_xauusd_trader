from pydantic import BaseModel, ConfigDict, Field


class Mt5RiskSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    symbol: str = Field(min_length=1)
    account_currency: str = Field(min_length=1)
    equity_usd: float = Field(gt=0.0)
    free_margin_usd: float = Field(ge=0.0)
    point_size: float = Field(gt=0.0)
    tick_size: float = Field(gt=0.0)
    tick_value_usd: float = Field(gt=0.0)
    contract_size: float = Field(gt=0.0)
    volume_min_lots: float = Field(gt=0.0)
    volume_max_lots: float = Field(gt=0.0)
    volume_step_lots: float = Field(gt=0.0)
    swap_long: float
    swap_short: float
    swap_mode: int
