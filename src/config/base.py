import base64
import hashlib
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings


class BaseConfig(BaseSettings):
    id: str = ""

    def get(self, key: str, default_value: Any = None) -> Any:  # type: ignore[no-any-return]
        return self.model_dump().get(key, default_value)

    def log(self, path_of_logs: Path):
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
