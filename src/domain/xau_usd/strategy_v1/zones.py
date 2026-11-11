import pandas as pd

from br_pre_commit import pandera_validate
from domain.schemas.xau_usd.zones import StrategyZoneRows
from helper.importer import pt


@pandera_validate
def unique_zone_membership(prices: pd.Series, zones: pt.DataFrame[StrategyZoneRows]) -> pd.Series:
    if prices.isna().any() or not pd.api.types.is_numeric_dtype(prices.dtype):
        raise ValueError("prices must contain numeric, non-null values")
    lower_boundaries = pd.Index(zones["lower"])
    upper_boundaries = pd.Index(zones["upper"].sort_values(kind="stable"))
    candidate_positions = pd.Series(
        lower_boundaries.searchsorted(prices, side="right") - 1,
        index=prices.index,
    )
    covering_count = candidate_positions.add(1).sub(upper_boundaries.searchsorted(prices, side="left"))
    unique_match = candidate_positions.ge(0) & covering_count.eq(1)
    candidate_zone_ids = pd.Series(zones.index.get_level_values("zone_id")).reindex(pd.Index(candidate_positions))
    candidate_zone_ids.index = prices.index
    return candidate_zone_ids.where(unique_match)
