from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> str:
    try:
        return subprocess.check_output(args, cwd=ROOT, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as exc:
        return f"UNAVAILABLE: {exc}"


print("=== Project status ===")
print(f"Root: {ROOT}")
print(f"Git branch: {run('git', 'branch', '--show-current')}")
print(f"Git status:\n{run('git', 'status', '--short') or 'clean'}")
print(f"Latest commit: {run('git', 'log', '-1', '--oneline')}")
print(f"Remote:\n{run('git', 'remote', '-v')}")
state = ROOT / "docs" / "CURRENT_STATE.md"
print(f"Current state file: {'present' if state.exists() else 'missing'}")
