"""Read-only checks for agent navigation and repository contracts."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AGENTS = ("claude", "agents", "devin", "copilot", "kiro", "kilo")


def skill_sync_errors(hooks: str, agents: tuple[str, ...] = DEFAULT_AGENTS) -> list[str]:
    block = re.search(r"(?ms)^  - id: sync-skill-files\n(.*?)(?=^  - id: |\Z)", hooks)
    pattern = re.search(r"^    files: (.+)$", block[1], re.MULTILINE) if block else None
    if pattern is None:
        return ["Skill-sync hook must define a files pattern"]
    try:
        matcher = re.compile(pattern[1].strip().strip("\"'"))
    except re.error as error:
        return [f"Invalid skill-sync pattern: {error}"]
    paths = (f".{agent}/skills/example/SKILL.md" for agent in agents)
    return [f"Skill-sync hook does not match: {path}" for path in paths if not matcher.search(path)]


def broken_links(root: Path, document: Path) -> list[str]:
    errors = []
    for target in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
        parsed = urlsplit(target.strip("<>"))
        if parsed.scheme or not parsed.path:
            continue
        destination = document.parent / unquote(parsed.path)
        if not destination.exists():
            errors.append(f"{document.relative_to(root)}: missing link {target}")
    return errors


def check(root: Path) -> list[str]:
    errors = []
    documents = [root / name for name in ("AGENTS.md", "README.md", "RUNBOOK.md")]
    documents += list((root / "docs").glob("*.md"))
    documents += list((root / "src").rglob("README.md"))
    documents += [root / "mt5/README.md"]
    for document in documents:
        if not document.is_file():
            errors.append(f"Missing navigation document: {document.relative_to(root)}")
        else:
            errors.extend(broken_links(root, document))

    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    agents = tuple(config.get("tool", {}).get("br_pre_commit", {}).get("sync_skills", {}).get("agents", DEFAULT_AGENTS))
    for package in config["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]:
        if not (root / package / "__init__.py").is_file():
            errors.append(f"Wheel package missing: {package}")

    canonical = root / ".agents/skills"
    for skill in canonical.glob("*/SKILL.md"):
        if "-only-" in skill.parent.name:
            continue
        expected = skill.read_text(encoding="utf-8")
        errors.extend(broken_links(root, skill))
        for agent in agents:
            mirror = root / f".{agent}/skills" / skill.parent.name / "SKILL.md"
            if not mirror.is_file() or mirror.read_text(encoding="utf-8") != expected:
                errors.append(f"Skill mirror differs or missing: {mirror.relative_to(root)}")
        if skill.parent.name == "git-commit" and config.get("tool", {}).get("br_pre_commit", {}).get(
            "sync_skills", {}
        ).get("github-git-commit", True):
            mirror = root / ".github/git-commit/SKILL.md"
            if not mirror.is_file() or mirror.read_text(encoding="utf-8") != expected:
                errors.append("Skill mirror differs or missing: .github/git-commit/SKILL.md")

    workflow = (root / ".github/workflows/ci-python.yml").read_text(encoding="utf-8")
    if 'python-version-file: "pyproject.toml"' not in workflow or "runs-on: windows-latest" not in workflow:
        errors.append("CI must derive Python from pyproject.toml and support the MetaTrader5 dependency")
    hooks = (root / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    errors.extend(skill_sync_errors(hooks, agents))
    return errors


if __name__ == "__main__":
    failures = check(ROOT)
    for failure in failures:
        print(f"FAIL: {failure}")
    print(f"Repository contracts: {'FAIL' if failures else 'PASS'} ({len(failures)} issues)")
    sys.exit(bool(failures))
