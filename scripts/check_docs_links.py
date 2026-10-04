"""Validate local Markdown links and anchors.

Reports ``path:line -> target`` for every relative link whose file or anchor
does not resolve, so a fresh session can trust repository navigation.

Scope: authoritative documents only (root README, AGENTS.md files, docs/ and the
canonical .agents/skills). Generated agent mirrors are excluded because they are
synchronized copies.

Usage:
    python scripts/check_docs_links.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INCLUDE_ROOTS = ("README.md", "AGENTS.md", "CHATGPT_WORK.md")
INCLUDE_DIRS = ("docs", ".agents/skills", ".codex/skills", "src", "mt5", "config")
# The other agent folders are byte-identical mirrors of .codex/skills. Checking
# one is enough for links; mirror agreement is a separate check
# (scripts/check_skills_sync.py).
EXCLUDE_PARTS = {"node_modules", "worktrees", "__pycache__", "legacy_reference", "archive_not_used_trash", ".git"}

LINK_RE = re.compile(r"(?<!\!)\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE_RE = re.compile(r"^\s*```")


def markdown_files() -> list[Path]:
    files: list[Path] = []
    for name in INCLUDE_ROOTS:
        candidate = ROOT / name
        if candidate.is_file():
            files.append(candidate)
    for directory in INCLUDE_DIRS:
        base = ROOT / directory
        if not base.is_dir():
            continue
        for candidate in base.rglob("*.md"):
            if not EXCLUDE_PARTS & set(candidate.parts):
                files.append(candidate)
    return sorted(files)


def slugify(heading: str) -> str:
    slug = heading.strip().lower()
    slug = re.sub(r"[^\w\- ]+", "", slug)
    return slug.replace(" ", "-")


def anchors_of(path: Path) -> set[str]:
    found: set[str] = set()
    in_fence = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
        if match:
            found.add(slugify(match.group(1)))
    return found


def resolve(source: Path, target: str) -> tuple[Path | None, str]:
    """Return (resolved file, anchor). target may be 'file#anchor'."""
    if "#" in target:
        path_part, _, anchor = target.partition("#")
    else:
        path_part, anchor = target, ""
    if not path_part:
        return source, anchor
    candidate = (source.parent / path_part).resolve()
    if candidate.is_dir():
        candidate = candidate / "README.md"
    return candidate, anchor


def check() -> list[str]:
    problems: list[str] = []
    files = markdown_files()
    for source in files:
        in_fence = False
        for number, line in enumerate(source.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for _label, target in LINK_RE.findall(line):
                if target.startswith(("http://", "https://", "mailto:", "<")):
                    continue
                resolved, anchor = resolve(source, target)
                relative = source.relative_to(ROOT)
                if resolved is None or not resolved.exists():
                    problems.append(f"{relative}:{number} -> {target}  (missing file)")
                    continue
                if anchor and resolved.suffix.lower() == ".md":
                    if slugify(anchor) not in anchors_of(resolved):
                        problems.append(f"{relative}:{number} -> {target}  (missing anchor)")
    return problems


def main() -> int:
    problems = check()
    for problem in problems:
        print(problem)
    total = len(markdown_files())
    print(f"\nchecked {total} markdown files: {len(problems)} broken local link(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
