"""Read-only consistency validation for agent skills.

Two independent things are checked, and neither is ever auto-fixed:

1. **Name uniqueness.** A skill name may exist in exactly one canonical folder.
   `.agents/skills/` holds this project's authored workflows. The remaining
   agent folders hold the shared set mirrored from `.codex/skills/`. A name
   appearing in both sets means two agents get different instructions for the
   same trigger, which is how agents end up implementing conflicting
   conventions.

2. **Mirror agreement.** Every shared skill present in `.codex/skills/` must be
   byte-identical in the other mirror folders.

This never writes, stages or deletes. The repository's sync hook can create,
overwrite, stage and propagate deletions, so it must be run deliberately and
reviewed, not invoked blindly.

Usage:
    python scripts/check_skills_sync.py
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ".agents/skills"
SHARED_SOURCE = ".codex/skills"
MIRRORS = (".claude/skills", ".copilot/skills", ".devin/skills", ".kiro/skills", ".qoder/skills")


def skill_names(base: Path) -> set[str]:
    if not base.is_dir():
        return set()
    return {child.name for child in base.iterdir() if (child / "SKILL.md").is_file()}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def check() -> list[str]:
    problems: list[str] = []
    canonical = skill_names(ROOT / CANONICAL)
    shared = skill_names(ROOT / SHARED_SOURCE)

    for name in sorted(canonical & shared):
        problems.append(
            f"{name}: defined in both {CANONICAL}/ (canonical) and {SHARED_SOURCE}/ (shared). "
            "Agents would receive conflicting instructions for one trigger. Keep one copy."
        )

    extra = sorted(set(MIRRORS) - {SHARED_SOURCE})
    for mirror_name in extra:
        mirror_root = ROOT / mirror_name
        mirror = skill_names(mirror_root)
        for missing in sorted(shared - mirror):
            problems.append(f"{mirror_name}/{missing}: missing; shared set has it")
        for orphan in sorted(mirror - shared):
            problems.append(f"{mirror_name}/{orphan}: not in {SHARED_SOURCE}/; remove or promote it")
        for name in sorted(shared & mirror):
            source_file = ROOT / SHARED_SOURCE / name / "SKILL.md"
            mirror_file = mirror_root / name / "SKILL.md"
            if digest(source_file) != digest(mirror_file):
                problems.append(f"{mirror_name}/{name}/SKILL.md: content differs from {SHARED_SOURCE}/")

    if not extra:
        problems.append("no mirror folders configured; mirror agreement was not checked")
    return problems


def main() -> int:
    canonical = sorted(skill_names(ROOT / CANONICAL))
    shared = sorted(skill_names(ROOT / SHARED_SOURCE))
    print(f"canonical {CANONICAL}/: {len(canonical)} -> {', '.join(canonical)}")
    print(f"shared    {SHARED_SOURCE}/: {len(shared)} -> {', '.join(shared)}")
    problems = check()
    for problem in problems:
        print(f"  {problem}")
    print(f"\n{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
