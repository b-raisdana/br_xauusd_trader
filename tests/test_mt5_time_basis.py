from datetime import datetime, timezone

import pytest

from scripts.match_mt5_time_basis import contains_bid_sequence, server_to_utc


def test_server_time_converts_with_explicit_candidate_offset() -> None:
    server = datetime(2026, 8, 28, 1)
    assert server_to_utc(server, 180) == datetime(2026, 8, 27, 22, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="naive"):
        server_to_utc(server.replace(tzinfo=timezone.utc), 180)


def test_bid_sequence_requires_order_and_duplicates() -> None:
    actual = [100.0, 101.0, 101.0, 102.0]
    assert contains_bid_sequence(actual, (101.0, 101.0, 102.0))
    assert not contains_bid_sequence(actual, (101.0, 102.0, 102.0))
