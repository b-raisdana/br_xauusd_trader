import csv
import hashlib
from pathlib import Path


def test_core_project_documents_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    required = [
        "AGENTS.md",
        "CHATGPT_WORK.md",
        "docs/PROJECT_BRIEF.md",
        "docs/RULES.md",
        "docs/CURRENT_STATE.md",
        "docs/TODO.md",
    ]
    assert all((root / relative).exists() for relative in required)


def test_canonical_ranges_are_intact_and_well_formed() -> None:
    root = Path(__file__).resolve().parents[1]
    ranges_path = root / "data" / "ranges.csv"

    assert hashlib.sha256(ranges_path.read_bytes()).hexdigest() == (
        "d146fe4650ea52da64b585a7a0ee15d874e68801f12764481e9ef8c773c9f4f3"
    )

    with ranges_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 444
    assert len({row["date"] for row in rows}) == 23
    assert all(float(row["lower"]) <= float(row["upper"]) for row in rows)
    assert {row["priority"].lower() for row in rows} <= {"normal", "high"}
    assert {row["enabled"].lower() for row in rows} <= {"true", "false"}


def test_legacy_core_manifest_is_intact() -> None:
    root = Path(__file__).resolve().parents[1]
    bundle = root / "legacy_reference" / "PREVIOUS_TECHNICAL_BUNDLE"
    manifest = bundle / "SHA256_KIT.txt"

    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split(maxsplit=1)
        actual = hashlib.sha256((bundle / relative).read_bytes()).hexdigest()
        assert actual.casefold() == expected.casefold(), relative
