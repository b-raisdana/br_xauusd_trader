import base64
import hashlib
from _contextvars import ContextVar
from contextlib import contextmanager
from pathlib import Path
from typing import Any, ClassVar, Iterator, Self

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class BaseConfig(BaseSettings):
    id: str = ""

    def get(self, key: str, default_value: Any = None) -> Any:  # type: ignore[no-any-return]
        return self.model_dump().get(key, default_value)

    def log(self, path_of_logs: Path | None = None):
        if path_of_logs is None:
            path_of_logs = Path(__file__).resolve().parent.parent.parent / "logs"

        config_as_json = self.model_dump_json()

        config_digest = str.translate(
            base64.b64encode(hashlib.md5(config_as_json.encode("utf-8")).digest()).decode("ascii"),
            {
                ord("+"): "",
                ord("/"): "",
                ord("="): "",
            },
        )

        config_log_dir = path_of_logs / "config"
        config_log_dir.mkdir(parents=True, exist_ok=True)

        dump_filename = config_log_dir / f"{self.__class__.__name__}.{config_digest}.json"

        if not dump_filename.exists():
            dump_filename.write_text(config_as_json, encoding="utf-8")

        self.id = config_digest
        return self


class BaseContextConfig(BaseConfig):
    """Config classes that need per-thread/per-process 'current instance' binding."""

    model_config = ConfigDict(frozen=True)

    _context: ClassVar[ContextVar["BaseContextConfig"]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._context = ContextVar(f"{cls.__qualname__}_context")  # fresh slot per concrete subclass

    @classmethod
    def current(cls) -> Self:
        try:
            return cls._context.get()  # type: ignore[return-value]
        except LookupError as e:
            raise RuntimeError(f"No {cls.__name__} bound in this context — call .use() first") from e

    @contextmanager
    def use(self) -> Iterator[Self]:
        token = type(self)._context.set(self)
        try:
            yield self
        finally:
            type(self)._context.reset(token)
