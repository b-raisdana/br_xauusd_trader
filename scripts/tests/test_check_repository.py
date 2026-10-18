import tempfile
import unittest
from pathlib import Path

from scripts.check_repository import broken_links, check


class NavigationLinksTest(unittest.TestCase):
    def test_relative_links_and_fragments_resolve_from_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "target file.md").touch()
            document = root / "docs/index.md"
            document.write_text(
                "[local](../target%20file.md#section) [heading](#section) [web](https://example.com)",
                encoding="utf-8",
            )
            self.assertEqual(broken_links(root, document), [])

    def test_missing_link_reports_document_and_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = root / "README.md"
            document.write_text("[broken](missing.md)", encoding="utf-8")
            self.assertEqual(broken_links(root, document), ["README.md: missing link missing.md"])


class RepositoryContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for name in ("AGENTS.md", "README.md", "RUNBOOK.md", "CHATGPT_WORK.md", "mt5/README.md"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
        (self.root / "pyproject.toml").write_text(
            '[tool.hatch.build.targets.wheel]\npackages = ["src/example"]\n', encoding="utf-8"
        )
        package = self.root / "src/example"
        package.mkdir(parents=True)
        (package / "__init__.py").touch()
        workflow = self.root / ".github/workflows/ci-python.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text('runs-on: windows-latest\npython-version-file: "pyproject.toml"\n', encoding="utf-8")
        (self.root / ".pre-commit-config.yaml").write_text(r"\.agents/skills/", encoding="utf-8")

    def test_valid_minimal_repository(self) -> None:
        self.assertEqual(check(self.root), [])

    def test_missing_wheel_package_is_rejected(self) -> None:
        (self.root / "src/example/__init__.py").unlink()
        self.assertIn("Wheel package missing: src/example", check(self.root))

    def test_divergent_or_missing_skill_mirror_is_rejected(self) -> None:
        skill = self.root / ".kilo/skills/example/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("canonical", encoding="utf-8")
        self.assertEqual(sum("Skill mirror differs or missing" in error for error in check(self.root)), 5)

    def test_workflow_drift_is_rejected(self) -> None:
        (self.root / ".github/workflows/ci-python.yml").write_text("runs-on: ubuntu-latest", encoding="utf-8")
        self.assertTrue(any("CI must derive Python" in error for error in check(self.root)))
