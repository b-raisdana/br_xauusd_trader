from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, create_model
from pydantic_settings import JsonConfigSettingsSource, SettingsConfigDict

from config.base import BaseContextConfig

DEFAULT_CORE_VECTORS_JSON = Path(__file__).resolve().parents[2] / "config" / "mt5" / "core_vectors.json"


class CoreVectors(BaseContextConfig):
    model_config = SettingsConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )

    vec_breakout_low: float = 100
    vec_breakout_high: float = 101
    vec_breakout_close: float = 102.01

    vec_reversal_previous: float = 99.90
    vec_reversal_current: float = 100.20

    vec_risk_entry: float = 100
    vec_risk_expected_sl: float = 97
    vec_risk_expected_tp: float = 108

    vec_risk_zone_1_low: float = 90
    vec_risk_zone_1_high: float = 91
    vec_risk_zone_2_low: float = 96
    vec_risk_zone_2_high: float = 97
    vec_risk_zone_3_low: float = 104
    vec_risk_zone_3_high: float = 105
    vec_risk_zone_4_low: float = 108
    vec_risk_zone_4_high: float = 109

    vec_portfolio_capital: float = 200
    vec_portfolio_realized: float = 5
    vec_portfolio_open: float = 10
    vec_portfolio_pending: float = 7
    vec_portfolio_proposed: float = 8

    vec_trend_reference_high: float = 100
    vec_trend_reference_low: float = 90
    vec_trend_bid: float = 101

    vec_pullback_low: float = 100
    vec_pullback_high: float = 101
    vec_pullback_bid: float = 100.80

    vec_strict_current_open: float = 105
    vec_strict_current_bid: float = 106
    vec_strict_current_ask: float = 106.10

    vec_trigger_target_low: float = 110
    vec_trigger_target_high: float = 111
    vec_trigger_previous: float = 108
    vec_trigger_current: float = 110

    vec_protection_entry: float = 100
    vec_protection_rf: float = 100.25
    vec_protection_bid: float = 124.10
    vec_protection_ask: float = 124.20
    vec_protection_current_sl: float = 112

    vec_daily_capital: float = 200
    vec_daily_net_pnl: float = -40

    vec_session_now: datetime = datetime.fromisoformat("2026-09-06 20:55:00")
    vec_session_end: datetime = datetime.fromisoformat("2026-09-06 21:00:00")

    vec_merge_expected_count: int = 2

    vec_merge_zone_1_low: float = 100
    vec_merge_zone_1_high: float = 101
    vec_merge_zone_1_priority: int = 0

    vec_merge_zone_2_low: float = 102
    vec_merge_zone_2_high: float = 103
    vec_merge_zone_2_priority: int = 1

    vec_merge_zone_3_low: float = 104.4
    vec_merge_zone_3_high: float = 105
    vec_merge_zone_3_priority: int = 0

    vec_merge_zone_4_low: float = 106.5
    vec_merge_zone_4_high: float = 107
    vec_merge_zone_4_priority: int = 0

    vec_gap_zone_1_low: float = 100
    vec_gap_zone_1_high: float = 101
    vec_gap_zone_2_low: float = 103
    vec_gap_zone_2_high: float = 104
    vec_gap_previous: float = 99
    vec_gap_current: float = 104

    vec_pullback_bar_offset: int = 5
    vec_pullback_daily_fills: int = 7

    vec_tp_initial: float = 100
    vec_tp_current_bid: float = 99
    vec_tp_current_ask: float = 99.10

    vec_restart_day: str = "2026-09-06"
    vec_restart_last_day: str = "2026-09-06"

    vec_execution_status: int = 0
    vec_execution_event: int = 6
    vec_execution_order_type: int = 1
    vec_execution_expected_allowed: int = 1
    vec_execution_expected_status: int = 0

    vec_modification_direction: int = 0
    vec_modification_entry: float = 100
    vec_modification_current_sl: float = 96
    vec_modification_proposed_sl: float = 97
    vec_modification_proposed_tp: float = 110
    vec_modification_expected_valid: int = 1

    vec_causal_zone_low: float = 101
    vec_causal_zone_high: float = 102
    vec_causal_reference_high: float = 100
    vec_causal_reference_low: float = 90
    vec_causal_previous: float = 99
    vec_causal_bid: float = 101

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            JsonConfigSettingsSource(settings_cls, json_file=DEFAULT_CORE_VECTORS_JSON),
            init_settings,
        )

    @classmethod
    def from_json(cls, path: str | Path) -> "CoreVectors":
        payload_model = create_model(
            "_CoreVectorsPayload",
            __base__=BaseModel,
            __config__=ConfigDict(extra="forbid"),
            **{name: (field.annotation, field) for name, field in cls.model_fields.items()},
        )
        payload = payload_model.model_validate_json(Path(path).read_text(encoding="utf-8"))
        return cls.model_construct(**payload.model_dump())


# def load_core_vectors(path: str | Path | None = None) -> CoreVectors:
#     if path is None:
#         return CoreVectors()
#     return CoreVectors.from_json(path)


core_vectors = CoreVectors().log()
