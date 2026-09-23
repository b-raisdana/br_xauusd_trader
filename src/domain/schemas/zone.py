from pandera import Field

from domain.schemas.common.base_dataframe import MultiTimeframeTimeseries
from helper.importer import pt


class Zone(MultiTimeframeTimeseries):
    lower: pt.Series[float]
    upper: pt.Series[float]
    priority: pt.Series[str] = Field(isin=["high", "low", "normal"])
    enabled: pt.Series[bool]
