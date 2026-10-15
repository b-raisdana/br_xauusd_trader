from importlib import import_module
from typing import Any

import pandera.pandas as pa
import pandera.typing as pt
import plotly.graph_objects as go
import pyarrow as pya

ta: Any
__all__ = ["ta", "pa", "pt", "go", "pya"]


def __getattr__(name: str) -> Any:
    if name != "ta":
        raise AttributeError(name)
    try:
        module = import_module("pandas_ta")
    except ImportError:
        module = None
    globals()[name] = module
    return module
