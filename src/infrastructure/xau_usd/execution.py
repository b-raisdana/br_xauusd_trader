from __future__ import annotations

from pathlib import Path

# from archive_not_used_trash.xauusd_trading_strategy_1 import (
#     XauExecutionBinding,
#     XauExecutionProjection,
#     execution_transition,
#     protection_modification_valid,
# )

DEFAULT_STORAGE_ROOT = Path(__file__).resolve().parents[3] / "data" / "mt5"


def execution_request_id_valid(request_id: str) -> bool:
    return bool(request_id) and not any(character in request_id for character in "\t\r\n")


# def bind_execution_order(
#     bindings: list[XauExecutionBinding],
#     request_id: str,
#     order_ticket: int,
# ) -> bool:
#     if not execution_request_id_valid(request_id) or order_ticket <= 0:
#         return False
#
#     for binding in bindings:
#         if binding.request_id == request_id:
#             return binding.order_ticket == order_ticket
#         if binding.order_ticket == order_ticket:
#             return False
#
#     bindings.append(XauExecutionBinding(request_id=request_id, order_ticket=order_ticket))
#     return True


# def bind_execution_position(
#     bindings: list[XauExecutionBinding],
#     order_ticket: int,
#     position_id: int,
# ) -> bool:
#     if order_ticket <= 0 or position_id <= 0:
#         return False
#
#     matching_index = -1
#     for index, binding in enumerate(bindings):
#         if binding.position_id == position_id and binding.order_ticket != order_ticket:
#             return False
#         if binding.order_ticket == order_ticket:
#             matching_index = index
#
#     if matching_index < 0:
#         return False
#
#     binding = bindings[matching_index]
#     if binding.position_id not in {0, position_id}:
#         return False
#
#     binding.position_id = position_id
#     return True


# def resolve_execution_request(
#     bindings: list[XauExecutionBinding],
#     event_kind: XauExecutionEvent,
#     order_ticket: int,
#     position_id: int,
# ) -> str | None:
#     for binding in bindings:
#         order_match = event_kind == XauExecutionEvent.FILL and order_ticket > 0 and
# binding.order_ticket == order_ticket
#         position_match = (
#             event_kind == XauExecutionEvent.CLOSE and position_id > 0 and binding.position_id == position_id
#         )
#         if order_match or position_match:
#             return binding.request_id
#     return None


# def resolve_execution_order_ticket(
#     bindings: list[XauExecutionBinding],
#     order_ticket: int,
# ) -> str | None:
#     if order_ticket <= 0:
#         return None
#     for binding in bindings:
#         if binding.order_ticket == order_ticket:
#             return binding.request_id or None
#     return None


# def same_execution_bindings(left: list[XauExecutionBinding], right: list[XauExecutionBinding]) -> bool:
#     return left == right


# def copy_execution_bindings(bindings: list[XauExecutionBinding]) -> list[XauExecutionBinding]:
#     return [
#         XauExecutionBinding(
#             request_id=binding.request_id,
#             order_ticket=binding.order_ticket,
#             position_id=binding.position_id,
#         )
#         for binding in bindings
#     ]


# def copy_execution_projections(
#     projections: list[XauExecutionProjection],
# ) -> list[XauExecutionProjection]:
#     return [
#         XauExecutionProjection(
#             request_id=projection.request_id,
#             status=projection.status,
#             order_type=projection.order_type,
#             direction=projection.direction,
#             order_entry=projection.order_entry,
#             fill_price=projection.fill_price,
#             stop_loss=projection.stop_loss,
#             take_profit=projection.take_profit,
#             close_price=projection.close_price,
#             transition_time=projection.transition_time,
#         )
#         for projection in projections
#     ]


# def _storage_path(path: str | Path) -> Path | None:
#     candidate = Path(path)
#     if ".." in candidate.parts:
#         return None
#     return candidate if candidate.is_absolute() else DEFAULT_STORAGE_ROOT / candidate


# def load_execution_bindings(path: str | Path) -> list[XauExecutionBinding] | None:
#     storage_path = _storage_path(path)
#     if storage_path is None or not storage_path.exists():
#         return None
#
#     bindings: list[XauExecutionBinding] = []
#     lines = storage_path.read_text(encoding="utf-8").splitlines()
#     if not lines or lines[0] != "XAU_EXECUTION_BINDINGS\t1":
#         return None
#
#     for line in lines[1:]:
#         if not line:
#             continue
#         fields = line.split("\t")
#         if len(fields) != 3 or not execution_request_id_valid(fields[0]):
#             return None
#         try:
#             order_ticket = int(fields[1])
#             position_id = int(fields[2])
#         except ValueError:
#             return None
#         if order_ticket <= 0 or position_id < 0:
#             return None
#         if not bind_execution_order(bindings, fields[0], order_ticket):
#             return None
#         if position_id > 0 and not bind_execution_position(bindings, order_ticket, position_id):
#             return None
#
#     return bindings


# def save_execution_bindings_atomically(
#     path: str | Path,
#     bindings: list[XauExecutionBinding],
# ) -> bool:
#     storage_path = _storage_path(path)
#     if storage_path is None:
#         return False
#
#     lines = ["XAU_EXECUTION_BINDINGS\t1"]
#     for binding in bindings:
#         if not execution_request_id_valid(binding.request_id) or binding.order_ticket <= 0:
#             return False
#         lines.append(f"{binding.request_id}\t{binding.order_ticket}\t{binding.position_id}")
#
#     try:
#         storage_path.parent.mkdir(parents=True, exist_ok=True)
#         temporary_path = storage_path.with_name(storage_path.name + ".tmp")
#         temporary_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
#         recovered = load_execution_bindings(temporary_path)
#         if recovered is None or not same_execution_bindings(recovered, bindings):
#             temporary_path.unlink(missing_ok=True)
#             return False
#         temporary_path.replace(storage_path)
#         return True
#     except OSError:
#         temporary_path.unlink(missing_ok=True)
#         return False


# def initialize_execution_projection(
#     request_id: str,
#     order_type,
#     direction,
#     order_entry: float,
#     stop_loss: float,
#     take_profit: float,
#     submitted_at: datetime,
# ) -> XauExecutionProjection | None:
#     if (
#         not execution_request_id_valid(request_id)
#         or order_entry <= 0.0
#         or submitted_at is None
#         or not protection_modification_valid(direction, order_entry, stop_loss, stop_loss, take_profit)
#     ):
#         return None
#
#     return XauExecutionProjection(
#         request_id=request_id,
#         order_type=order_type,
#         direction=direction,
#         order_entry=order_entry,
#         stop_loss=stop_loss,
#         take_profit=take_profit,
#         transition_time=submitted_at,
#     )


# def project_execution_outcome(
#     projection: XauExecutionProjection,
#     event_kind: XauExecutionEvent,
#     outcome_time: datetime,
#     outcome_price: float = 0.0,
#     proposed_stop: float = 0.0,
#     proposed_tp: float = 0.0,
# ) -> bool:
#     if projection.request_id == "" or projection.transition_time is None or outcome_time < projection.transition_time:
#         return False
#
#     allowed, next_status = execution_transition(projection.status, event_kind, projection.order_type)
#     if not allowed or next_status is None:
#         return False
#
#     if event_kind in {XauExecutionEvent.FILL, XauExecutionEvent.CLOSE} and outcome_price <= 0.0:
#         return False
#
#     if event_kind in {XauExecutionEvent.MODIFY, XauExecutionEvent.MODIFY_REJECT}
# and not protection_modification_valid(
#         projection.direction,
#         projection.order_entry,
#         projection.stop_loss,
#         proposed_stop,
#         proposed_tp,
#     ):
#         return False
#
#     if event_kind == XauExecutionEvent.FILL:
#         projection.fill_price = outcome_price
#     elif event_kind == XauExecutionEvent.CLOSE:
#         projection.close_price = outcome_price
#     elif event_kind == XauExecutionEvent.MODIFY:
#         projection.stop_loss = proposed_stop
#         projection.take_profit = proposed_tp
#
#     projection.status = next_status
#     projection.transition_time = outcome_time
#     return True
#
#
# def find_execution_projection(
#     projections: list[XauExecutionProjection],
#     request_id: str,
# ) -> int:
#     matches = [index for index, projection in enumerate(projections) if projection.request_id == request_id]
#     return matches[0] if len(matches) == 1 else -1
#
#
# def project_correlated_native_outcome(
#     projections: list[XauExecutionProjection],
#     bindings: list[XauExecutionBinding],
#     event_kind: XauExecutionEvent,
#     order_ticket: int,
#     position_id: int,
#     broker_time: datetime,
#     price: float,
# ) -> bool:
#     if event_kind not in {XauExecutionEvent.FILL, XauExecutionEvent.CLOSE}:
#         return False
#
#     request_id = resolve_execution_request(bindings, event_kind, order_ticket, position_id)
#     if request_id is None:
#         return False
#
#     index = find_execution_projection(projections, request_id)
#     if index < 0:
#         return False
#
#     projected = copy_execution_projections([projections[index]])[0]
#     if not project_execution_outcome(projected, event_kind, broker_time, price):
#         return False
#
#     if event_kind == XauExecutionEvent.FILL and not bind_execution_position(bindings, order_ticket, position_id):
#         return False
#
#     projections[index] = projected
#     return True
#
#
# def persist_then_publish_correlated_native_outcome(
#     projections: list[XauExecutionProjection],
#     bindings: list[XauExecutionBinding],
#     event_kind: XauExecutionEvent,
#     order_ticket: int,
#     position_id: int,
#     broker_time: datetime,
#     price: float,
#     bindings_file: str | Path,
# ) -> bool:
#     candidate_projections = copy_execution_projections(projections)
#     candidate_bindings = copy_execution_bindings(bindings)
#     if not project_correlated_native_outcome(
#         candidate_projections,
#         candidate_bindings,
#         event_kind,
#         order_ticket,
#         position_id,
#         broker_time,
#         price,
#     ) or not save_execution_bindings_atomically(bindings_file, candidate_bindings):
#         return False
#
#     projections[:] = candidate_projections
#     bindings[:] = candidate_bindings
#     return True
