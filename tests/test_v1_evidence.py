from __future__ import annotations

import importlib.util
from pathlib import Path


def test_v1_evidence_builder_is_account_free_and_fail_closed() -> None:
    path = Path(__file__).parents[1] / "scripts" / "build_v1_evidence.py"
    text = path.read_text(encoding="utf-8")
    assert "ACCOUNT_LOGIN" not in text and "ACCOUNT_NAME" not in text
    assert "len(orders) != attempts" in text
    assert "len(blocks) != int(v1.group(1))" in text
    assert '"live_enabled": False' in text
    spec = importlib.util.spec_from_file_location("build_v1_evidence", path)
    assert spec is not None and spec.loader is not None
