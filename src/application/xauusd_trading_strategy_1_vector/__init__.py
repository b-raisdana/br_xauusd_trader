from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .the_strategy import VectorizedXauUsdStrategy
    from .zone_cache import ZoneCache

__all__ = ["VectorizedXauUsdStrategy", "ZoneCache"]


def __getattr__(name: str) -> type[VectorizedXauUsdStrategy] | type[ZoneCache]:
    if name == "VectorizedXauUsdStrategy":
        from .the_strategy import VectorizedXauUsdStrategy

        return VectorizedXauUsdStrategy
    if name == "ZoneCache":
        from .zone_cache import ZoneCache

        return ZoneCache
    raise AttributeError(name)
