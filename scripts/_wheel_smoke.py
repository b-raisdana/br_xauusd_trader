"""Import an installed wheel from outside the checkout.

Run as: python scripts/_wheel_smoke.py dist/<name>.whl

Creates a throwaway virtual environment, installs only the wheel, then imports
the advertised public surfaces with the repository directory absent from
sys.path. A failure here means the packaging metadata does not describe the
product; it is not a test-suite problem.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

PROBE = """
import importlib
import sys

# The checkout must not be importable for this check to mean anything.
sys.path = [entry for entry in sys.path if "xauusd" not in entry.lower() or "site-packages" in entry]

targets = [
    "application.xauusd_trading_strategy_1_vector",
    "config",
    "domain",
    "helper",
    "infrastructure",
    "presentation",
]
failures = []
for target in targets:
    try:
        importlib.import_module(target)
    except Exception as error:
        failures.append(f"{target}: {type(error).__name__}: {error}")

from importlib.metadata import entry_points

# A retired surface (for example ctrader-cli) must not survive as an installed
# console script.
stale = sorted(
    name
    for name, entry in ((e.name, e) for e in entry_points(group="console_scripts"))
    if "ctrader" in name.lower() or "ctrader" in entry.value.lower()
)
if stale:
    failures.append(f"retired console scripts still installed: {stale}")

if failures:
    print("WHEEL SMOKE FAILED")
    for failure in failures:
        print("  " + failure)
    raise SystemExit(1)
print(f"WHEEL SMOKE OK ({len(targets)} top-level packages importable outside the checkout)")
"""


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    wheel = Path(argv[1]).resolve()
    if not wheel.is_file():
        print(f"wheel not found: {wheel}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="wheel-smoke-") as tmp:
        env_dir = Path(tmp) / "venv"
        created = subprocess.run([sys.executable, "-m", "venv", str(env_dir)], check=False)
        if created.returncode:
            print("failed to create smoke venv", file=sys.stderr)
            return created.returncode
        if sys.platform == "win32":
            python = env_dir / "Scripts" / "python.exe"
        else:
            python = env_dir / "bin" / "python"
        for arguments in (
            [str(python), "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
            [str(python), "-m", "pip", "install", "--quiet", str(wheel)],
        ):
            step = subprocess.run(arguments, check=False)
            if step.returncode:
                print(f"pip step failed: {' '.join(arguments[3:])}", file=sys.stderr)
                return step.returncode
        probe = Path(tmp) / "probe.py"
        probe.write_text(PROBE, encoding="utf-8")
        # cwd is the temp dir, so the repository is not on sys.path via ''.
        return subprocess.run([str(python), str(probe)], cwd=tmp, check=False).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv))
