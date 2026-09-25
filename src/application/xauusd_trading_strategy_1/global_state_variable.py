from dataclasses import dataclass, field

from application.xauusd_trading_strategy_1.domain.models import (
    XauExecutionBinding,
    XauExecutionProjection,
    XauMarketCoordinator,
    XauRuntimeRequest,
)

__all__ = ["StrategyRuntimeState"]


@dataclass(slots=True)
class StrategyRuntimeState:
    time_basis_probe_count: int = 0
    execution_projections: list[XauExecutionProjection] = field(default_factory=list)
    execution_bindings: list[XauExecutionBinding] = field(default_factory=list)
    runtime_requests: list[XauRuntimeRequest] = field(default_factory=list)
    execution_bindings_file: str = r"XAUUSD_Current\bindings.tsv"
    order_audit_file: str = r"XAUUSD_Current\orders.jsonl"
    market_state: XauMarketCoordinator = field(default_factory=XauMarketCoordinator)
    current_bar_time: int = 0
    event_loop_ready: bool = False
    event_loop_failure_reported: bool = False
    breakout_candidate_count: int = 0
    reversal_candidate_count: int = 0
    pullback_candidate_count: int = 0
    tester_attempt_count: int = 0
    tester_accept_count: int = 0
    tester_reject_count: int = 0
    request_sequence: int = 0
    event_sequence: int = 0
    daily_loss_locked: bool = False
    operational_lock: bool = False
    session_cancel_count: int = 0
    session_close_count: int = 0
    session_zero_exposure: bool = False
    restart_lock: bool = False
    max_open_positions: int = 0
    gate_rejections: list[int] = field(default_factory=lambda: [0] * 8)
    final_net_realized: float = 0.0
    final_gross_loss: float = 0.0
    invalid_price_rejections: int = 0
    other_broker_rejections: int = 0
    protection_modifies: int = 0
    protection_modify_rejects: int = 0
    sl_loosen_violations: int = 0
    tp_extensions: int = 0
    tp_restores: int = 0
    tp_market_closes: int = 0
    tp_modify_rejects: int = 0
    tp_close_rejects: int = 0
    breakout_conflict_closes: int = 0
    symbol_spec_emitted: bool = False
    attribution_attempts: list[int] = field(default_factory=lambda: [0] * 6)
    attribution_accepts: list[int] = field(default_factory=lambda: [0] * 6)
    attribution_rejects: list[int] = field(default_factory=lambda: [0] * 6)
