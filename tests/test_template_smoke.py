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
