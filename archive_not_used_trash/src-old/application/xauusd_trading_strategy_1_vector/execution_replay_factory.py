from __future__ import annotations

from typing import TYPE_CHECKING

from .domain.replay import ReplayConfig

if TYPE_CHECKING:
    from .vectorized_replay import VectorizedExecutionReplay


def _new_vectorized_execution_replay(config: ReplayConfig, stream_id: str) -> VectorizedExecutionReplay:
    from .vectorized_replay import VectorizedExecutionReplay

    return VectorizedExecutionReplay(config, stream_id)
