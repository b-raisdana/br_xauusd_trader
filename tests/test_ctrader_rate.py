"""Unit tests for infrastructure.ctrader_client.rate."""

from __future__ import annotations

import pytest

from infrastructure.ctrader_client.rate import decode_price, pip_size, point


class TestDecodePrice:
    def test_eurusd_five_digits(self) -> None:
        assert decode_price(108543, 5) == 1.08543

    def test_xauusd_five_digits(self) -> None:
        assert decode_price(260340000, 5) == 2603.4

    def test_zero(self) -> None:
        assert decode_price(0, 5) == 0.0

    def test_zero_digits(self) -> None:
        assert decode_price(123, 0) == 123.0

    def test_negative_raw(self) -> None:
        assert decode_price(-100000, 5) == -1.0

    def test_negative_digits_raises(self) -> None:
        with pytest.raises(ValueError, match="digits must be non-negative"):
            decode_price(100, -1)


class TestPipSize:
    def test_four_decimal(self) -> None:
        assert pip_size(4) == 0.0001

    def test_five_decimal(self) -> None:
        assert pip_size(5) == 0.00001

    def test_zero_position(self) -> None:
        assert pip_size(0) == 1.0

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="pip_position must be non-negative"):
            pip_size(-1)


class TestPoint:
    def test_five_digits(self) -> None:
        assert point(5) == 0.00001

    def test_four_digits(self) -> None:
        assert point(4) == 0.0001

    def test_zero_digits(self) -> None:
        assert point(0) == 1.0

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="digits must be non-negative"):
            point(-1)
