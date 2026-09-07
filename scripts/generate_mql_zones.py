"""Generate the deterministic MQL daily-zone loader from canonical ranges.csv."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def render(source: Path) -> str:
    days: dict[str, list[tuple[str, str, int]]] = {}
    with source.open(newline="", encoding="utf-8-sig") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            enabled = row["enabled"].strip().lower()
            if enabled not in {"true", "false"}:
                raise ValueError(f"Invalid enabled value at row {row_number}")
            if enabled == "false":
                continue
            day = row["date"].strip()
            priority = row["priority"].strip().lower()
            if priority not in {"normal", "high"}:
                raise ValueError(f"Invalid priority at row {row_number}")
            raw_low, raw_high = sorted((float(row["lower"]), float(row["upper"])))
            days.setdefault(day, []).append(
                (format(raw_low, ".15g"), format(raw_high, ".15g"), priority == "high")
            )

    lines = [
        "// Generated from data/ranges.csv; do not edit by hand.",
        "#ifndef XAUUSD_MVP_DAILY_ZONES_MQH",
        "#define XAUUSD_MVP_DAILY_ZONES_MQH",
        "",
        "bool LoadGeneratedRawZones(const string broker_day,XauZone &raw[])",
        "  {",
        "   ArrayResize(raw,0);",
    ]
    for day, zones in days.items():
        lines.extend(
            (f'   if(broker_day == "{day}")', "     {", f"      ArrayResize(raw,{len(zones)});")
        )
        for index, (rendered_low, rendered_high, is_high) in enumerate(zones):
            lines.append(
                f'      raw[{index}].id=""; raw[{index}].low={rendered_low}; '
                f"raw[{index}].high={rendered_high}; "
                f"raw[{index}].priority={int(is_high)};"
            )
        lines.extend(("      return true;", "     }"))
    lines.extend(("   return false;", "  }", "", "#endif", ""))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).parents[1]
    target = root / "src" / "mt5" / "generated" / "DailyZones.mqh"
    expected = render(root / "data" / "ranges.csv")
    if args.check:
        return 0 if target.read_text(encoding="utf-8") == expected else 1
    target.write_text(expected, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
