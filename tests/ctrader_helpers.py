"""
Helpers for infrastructure.ctrader_client tests: wrap protobuf messages in ProtoMessage envelopes.
"""

from __future__ import annotations

from typing import Any

from ctrader_open_api import Protobuf
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import ProtoMessage


def wrap(message: Any) -> ProtoMessage:
    """Serialize *message* into a ``ProtoMessage`` envelope for ``receive``."""
    envelope = ProtoMessage()
    envelope.payloadType = message.payloadType
    envelope.payload = message.SerializeToString()
    return envelope


def make_payload(name: str, **fields: Any) -> ProtoMessage:
    """Create a protobuf message by name, set fields, and wrap it."""
    message = Protobuf.get(name, **fields)
    return wrap(message)
