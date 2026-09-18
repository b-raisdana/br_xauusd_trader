"""Action generation utilities for the vectorized XAUUSD strategy.

Extracted from vectorized_strategy.py to keep individual function complexity
at Xenon rank B (low nesting, few branches per function).
"""

from __future__ import annotations

import pandas as pd


def generate_actions(state: pd.DataFrame) -> pd.DataFrame:
    """Generate final action column from signal candidates.

    Maps signal candidates to action values that match MT5 semantics.
    Action includes direction (BUY/SELL), order type, entry price, SL, TP.
    """
    state["action"] = None
    # Signal candidate collection, risk management filters, and final action
    # generation would be applied here in a full implementation.
    return state
