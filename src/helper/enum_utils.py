from enum import Enum
from typing import Any

from pydantic.alias_generators import to_snake


class AutoSnakeEnum(Enum):
    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list[Any]) -> str:  # type: ignore[explicit-any]
        return to_snake(name)
