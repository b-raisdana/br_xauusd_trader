from dataclasses import dataclass

__all__ = ["global_state"]


@dataclass
class GlobalState:
    from dataclasses import dataclass, field
    from typing import Any

    # MQL5:
    # int g_time_basis_probe_count = 0;
    g_time_basis_probe_count: int = 0

    # MQL5:
    # XauExecutionProjection g_execution_projections[];
    g_execution_projections: list[Any] = []

    # MQL5:
    # XauExecutionBinding g_execution_bindings[];
    g_execution_bindings: list[Any] = []

    # MQL5:
    # const string EXECUTION_BINDINGS_FILE = "XAUUSD_Current\\bindings.tsv";
    EXECUTION_BINDINGS_FILE: str = r"XAUUSD_Current\bindings.tsv"

    # MQL5:
    # const string ORDER_AUDIT_FILE = "XAUUSD_Current\\orders.jsonl";
    ORDER_AUDIT_FILE: str = r"XAUUSD_Current\orders.jsonl"

    # MQL5:
    # XauMarketCoordinator g_market_state;
    g_market_state: Any = None

    # MQL5:
    # datetime g_current_bar_time = 0;
    g_current_bar_time: int = 0

    # MQL5:
    # bool g_event_loop_ready = false;
    g_event_loop_ready: bool = False

    g_event_loop_failure_reported: bool = False

    g_breakout_candidate_count: int = 0
    g_reversal_candidate_count: int = 0
    g_pullback_candidate_count: int = 0

    g_tester_attempt_count: int = 0
    g_tester_accept_count: int = 0
    g_tester_reject_count: int = 0

    g_request_sequence: int = 0
    g_event_sequence: int = 0

    g_daily_loss_locked: bool = False
    g_operational_lock: bool = False

    g_session_cancel_count: int = 0
    g_session_close_count: int = 0
    g_session_zero_exposure: bool = False
    g_restart_lock: bool = False

    g_max_open_positions: int = 0

    g_gate_rejections: list[int] = [0] * 8

    g_final_net_realized: float = 0.0
    g_final_gross_loss: float = 0.0

    g_invalid_price_rejections: int = 0
    g_other_broker_rejections: int = 0

    g_protection_modifies: int = 0
    g_protection_modify_rejects: int = 0

    g_sl_loosen_violations: int = 0

    g_tp_extensions: int = 0
    g_tp_restores: int = 0
    g_tp_market_closes: int = 0

    g_tp_modify_rejects: int = 0
    g_tp_close_rejects: int = 0

    g_breakout_conflict_closes: int = 0

    g_symbol_spec_emitted: bool = False

    g_attribution_attempts: list[int] = [0] * 6
    g_attribution_accepts: list[int] = [0] * 6
    g_attribution_rejects: list[int] = [0] * 6


global_state = GlobalState()
