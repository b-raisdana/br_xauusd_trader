from datetime import UTC, datetime, timedelta

from br_pre_commit import pandera_validate
from domain.schemas.common.ohlcv import MultiTimeframeTicksSpreadOHLC
from domain.schemas.tick import Tick
from helper.importer import pt
from infrastructure.mt5.ohlcv import get_ohlcv
from infrastructure.mt5.tick import get_ticks


class Mt5MarketDataAdapter:
    @pandera_validate
    async def get_ticks(self, symbol: str, start: datetime, end: datetime) -> pt.DataFrame[Tick]:
        time_range = self._time_range(start, end)
        ticks = await get_ticks(time_range, symbol=symbol)
        precise_time = ticks.index.get_level_values("precise_time")
        in_range = (precise_time >= start) & (precise_time <= end)
        return ticks.loc[in_range]

    @pandera_validate
    async def get_candles(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str,
    ) -> pt.DataFrame[MultiTimeframeTicksSpreadOHLC]:
        time_range = self._time_range(start, end)
        return await get_ohlcv(symbol, time_range, timeframe)

    @staticmethod
    def _time_range(start: datetime, end: datetime) -> str:
        if start.tzinfo is None or end.tzinfo is None or start.utcoffset() != UTC.utcoffset(start):
            raise ValueError("MT5 data boundaries must be UTC-aware")
        if end.utcoffset() != UTC.utcoffset(end) or end <= start:
            raise ValueError("MT5 end must be after start and UTC-aware")
        rounded_start = start.replace(second=0, microsecond=0)
        rounded_end = end.replace(second=0, microsecond=0)
        if end.second or end.microsecond:
            rounded_end += timedelta(minutes=1)
        return f"{rounded_start:%y-%m-%d.%H-%M}T{rounded_end:%y-%m-%d.%H-%M}"
