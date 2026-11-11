"""Compiled execution replay, prepared and reconstructed with pandas/NumPy."""

from .execution_batch.adapter import BatchReplay


class VectorizedExecutionReplay(BatchReplay):
    """Causal numeric batch replay for one broker/symbol stream."""
