"""Single command interface for repository verification.

Every tool is invoked as ``sys.executable -m <tool>`` from the active
interpreter. Bare executables (``ruff``, ``mypy``, ``xenon``) are never used:
they are absent from ``PATH`` in the documented environment, which silently
breaks the ratchet hook.

Read-only commands: ``inspect``, ``test``, ``lint``, ``typecheck``, ``check``,
``benchmark``, ``build``, ``docs``.
Mutating commands: ``format``.

Commands never install packages and never touch the network.

Usage:
    python scripts/dev.py inspect
    python scripts/dev.py test tests/test_vectorized_pipeline.py
    python scripts/dev.py test --tier offline
    python scripts/dev.py lint
    python scripts/dev.py format src tests
    python scripts/dev.py typecheck
    python scripts/dev.py check --tier L2
    python scripts/dev.py benchmark --rows 20000
    python scripts/dev.py build
    python scripts/dev.py docs
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINT_PATHS = ("src", "tests", "scripts")
TYPECHECK_PATHS = ("src", "scripts", "tests")
TIERS = ("L0", "L1", "L2", "L3", "L4", "ratchet", "all")

# Marker expression per advertised tier. The classification authority is
# tests/conftest.py TIER_BY_MODULE; these are the selections, not the taxonomy.
# A tier that selects zero tests fails loudly instead of reporting a pass.
TIER_MARKERS: dict[str, str] = {
    "unit": "unit",
    "integration": "integration",
    "parity": "parity",
    "native": "native",
    "perf": "perf",
    "offline": "not native and not perf",
    "all": "not perf",
}


class DevError(RuntimeError):
    """A precondition or contract failure that is reported, not raised as a traceback."""


def run(argv: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    """Run a command with the active interpreter and preserve its exit code."""
    printable = " ".join(argv)
    print(f"$ {printable}", flush=True)
    return subprocess.run(
        argv,
        cwd=ROOT,
        check=check,
        text=True,
        capture_output=capture,
    )


def module_available(module: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(module) is not None


def require(modules: dict[str, str]) -> None:
    missing = [f"{label} (python -m {name})" for name, label in modules.items() if not module_available(name)]
    if missing:
        raise DevError(
            "Missing required tooling: " + ", ".join(missing) + ". Install with: python -m pip install -e .[dev]"
        )


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
    return result.stdout.strip()


def collected_count(args: list[str]) -> int:
    """Count the tests pytest would actually collect, so a zero selection fails loudly.

    Counting emitted node ids is used instead of parsing pytest's summary line:
    the summary differs between quiet and verbose modes and between pytest
    versions ("178/245 tests collected" vs "245 collected / 245 deselected"),
    which makes it an unreliable gate input.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *args,
            "--collect-only",
            "-q",
            "-o",
            "addopts=",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout or "") + (result.stderr or "")
    # pytest exits 0 on a successful collection and 5 when nothing was selected.
    # Anything else (for example 4 on a usage error) means the selection is invalid.
    if result.returncode not in (0, 5):
        raise DevError(f"pytest collection failed (exit {result.returncode}):\n{output.strip()[-800:]}")
    count = 0
    for line in output.splitlines():
        # Collected node ids are printed one per line as tests/<module>::<test>.
        if line.startswith("tests/") and "::" in line:
            count += 1
    return count


def cmd_test(args: argparse.Namespace) -> int:
    require({"pytest": "pytest"})
    selection: list[str] = list(args.paths)
    pytest_args: list[str] = []
    if args.tier:
        if args.tier not in TIER_MARKERS:
            raise DevError(f"Unknown tier {args.tier!r}; choose from {sorted(TIER_MARKERS)}")
        pytest_args += ["-m", TIER_MARKERS[args.tier]]
    elif args.marker:
        pytest_args += ["-m", args.marker]
    else:
        pytest_args += ["-m", TIER_MARKERS["all"]]

    if args.parallel == "auto":
        if not module_available("xdist"):
            raise DevError("--parallel auto needs pytest-xdist; use --parallel none or install .[dev]")
        pytest_args += ["-n", "auto"]
    elif args.parallel != "none":
        pytest_args += ["-n", str(args.parallel)]

    count = collected_count([*selection, *pytest_args])
    if count == 0:
        raise DevError(
            "Refusing to run: pytest would collect 0 tests for "
            f"paths={selection or ['<all>']} args={pytest_args}. A zero selection is never a passing gate."
        )
    print(f"selected {count} tests")
    return run([sys.executable, "-m", "pytest", *selection, *pytest_args]).returncode


def cmd_lint(_args: argparse.Namespace) -> int:
    require({"ruff": "ruff"})
    read_only = [path for path in LINT_PATHS if (ROOT / path).exists()]
    first = run([sys.executable, "-m", "ruff", "check", *read_only], check=False)
    second = run([sys.executable, "-m", "ruff", "format", "--check", *read_only], check=False)
    return first.returncode or second.returncode


def cmd_format(args: argparse.Namespace) -> int:
    require({"ruff": "ruff"})
    targets = [str(path) for path in args.paths] or list(LINT_PATHS)
    return (
        run([sys.executable, "-m", "ruff", "check", "--fix", *targets], check=False).returncode
        or run([sys.executable, "-m", "ruff", "format", *targets], check=False).returncode
    )


def cmd_typecheck(args: argparse.Namespace) -> int:
    require({"mypy": "mypy"})
    targets = [str(path) for path in args.paths] or list(TYPECHECK_PATHS)
    return run([sys.executable, "-m", "mypy", *targets], check=False).returncode


def cmd_inspect(_args: argparse.Namespace) -> int:
    """Read-only environment and repository report. Never prints secret values."""
    tools = {
        "pytest": "pytest",
        "ruff": "ruff",
        "mypy": "mypy",
        "radon": "radon (ratchet)",
        "xdist": "pytest-xdist",
        "pandas": "pandas",
        "numpy": "numpy",
        "pandera": "pandera",
        "MetaTrader5": "MetaTrader5 (native, Windows)",
        "vectorbt": "vectorbt (report)",
    }
    bare = sorted(name for name in ("ruff", "mypy", "xenon", "pytest") if shutil.which(name) is None)
    submodule = git("submodule", "status")
    report = {
        "python": {"version": sys.version.split()[0], "executable": sys.executable},
        "supported_requires": ">=3.12",
        "module_availability": {label: module_available(name) for name, label in tools.items()},
        "bare_executables_missing": bare,
        "note": "ratchet invokes bare ruff/mypy/xenon and fails unless these are on PATH",
        "submodule": submodule or "(none)",
        "submodule_initialized": "yes" if submodule and not submodule.startswith("-") else "no",
        "git": {
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty_files": len([line for line in git("status", "--porcelain").splitlines() if line.strip()]),
        },
        "tests_collected": collected_count(["-m", TIER_MARKERS["all"]]),
        "env": {
            "DLF_ENVIRONMENT": os.environ.get("DLF_ENVIRONMENT", "(unset -> development)"),
            "ENVIRONMENT": os.environ.get("ENVIRONMENT", "(unset -> development)"),
        },
    }
    print(json.dumps(report, indent=2))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    tiers = list(TIERS) if args.tier == "all" else [args.tier]
    unknown = [tier for tier in tiers if tier not in TIERS]
    if unknown:
        raise DevError(f"Unknown tier(s) {unknown}; choose from {TIERS}")
    results: list[tuple[str, int]] = []
    for tier in tiers:
        if tier == "L0":
            results.append(("L0 preflight", cmd_inspect(argparse.Namespace())))
        elif tier == "L1":
            results.append(
                (
                    "L1 unit tests (serial)",
                    cmd_test(argparse.Namespace(paths=[], tier="unit", marker=None, parallel="none")),
                )
            )
        elif tier in ("L2", "L3", "L4"):
            if tier == "L2":
                results.append(
                    (
                        "L2 offline suite",
                        cmd_test(argparse.Namespace(paths=[], tier="offline", marker=None, parallel="auto")),
                    )
                )
                results.append(("L2 lint", cmd_lint(argparse.Namespace())))
            elif tier == "L3":
                results.append(
                    (
                        "L3 integration",
                        cmd_test(argparse.Namespace(paths=[], tier="integration", marker=None, parallel="none")),
                    )
                )
                results.append(
                    (
                        "L3 parity comparison",
                        cmd_test(argparse.Namespace(paths=[], tier="parity", marker=None, parallel="none")),
                    )
                )
            else:
                results.append(
                    (
                        "L4 full selection",
                        cmd_test(argparse.Namespace(paths=[], tier="all", marker=None, parallel="auto")),
                    )
                )
                results.append(("L4 typecheck", cmd_typecheck(argparse.Namespace(paths=[]))))
                results.append(("L4 docs", cmd_docs(argparse.Namespace(skills=True))))
        elif tier == "ratchet":
            results.append(("ratchet", cmd_ratchet(argparse.Namespace())))
    print("\n=== gate summary ===")
    for name, code in results:
        print(f"{'PASS' if code == 0 else 'FAIL'}  {name} (exit {code})")
    return 0 if all(code == 0 for _, code in results) else 1


def cmd_ratchet(_args: argparse.Namespace) -> int:
    """Run the incremental ratchet. Requires bare ruff/mypy/xenon on PATH."""
    missing = sorted(name for name in ("ruff", "mypy", "xenon") if shutil.which(name) is None)
    if missing:
        raise DevError(
            f"ratchet needs bare executables on PATH: {missing}. The pinned submodule invokes them by name, "
            "so it cannot run through `python -m`. Add the interpreter's Scripts directory to PATH."
        )
    return run([sys.executable, "-m", "br_pre_commit.src.ratchet"], check=False).returncode


def cmd_benchmark(args: argparse.Namespace) -> int:
    return run(
        [
            sys.executable,
            str(ROOT / "scripts" / "benchmark_tick_stages.py"),
            "--rows",
            str(args.rows),
            "--repeat",
            str(args.repeat),
        ],
        check=False,
    ).returncode


def cmd_build(args: argparse.Namespace) -> int:
    require({"hatchling": "hatchling"})
    out = ROOT / "dist"
    if out.exists():
        shutil.rmtree(out)
    built = run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "-w", str(out), "."], check=False
    )
    if built.returncode:
        return built.returncode
    wheels = sorted(out.glob("*.whl"))
    if not wheels:
        raise DevError("pip wheel produced no artifact")
    print(f"built {wheels[-1].name}")
    if args.smoke:
        probe = ROOT / "scripts" / "_wheel_smoke.py"
        return run([sys.executable, str(probe), str(wheels[-1])], check=False).returncode
    return 0


def cmd_docs(args: argparse.Namespace) -> int:
    codes = [run([sys.executable, str(ROOT / "scripts" / "check_docs_links.py")], check=False).returncode]
    if args.skills:
        codes.append(run([sys.executable, str(ROOT / "scripts" / "check_skills_sync.py")], check=False).returncode)
    return codes[0] or (codes[1] if len(codes) > 1 else 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dev.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("inspect", help="read-only environment and repository report").set_defaults(func=cmd_inspect)

    test_parser = sub.add_parser("test", help="run pytest; refuses a zero-test selection")
    test_parser.add_argument("paths", nargs="*", help="test files, directories or node ids")
    test_parser.add_argument("--tier", choices=sorted(TIER_MARKERS), help="classified marker selection")
    test_parser.add_argument("--marker", help="explicit pytest -m expression")
    test_parser.add_argument("--parallel", default="none", help="'none' (default), 'auto' or a worker count")
    test_parser.set_defaults(func=cmd_test)

    sub.add_parser("lint", help="read-only ruff check and format check").set_defaults(func=cmd_lint)

    format_parser = sub.add_parser("format", help="MUTATING: ruff --fix and format")
    format_parser.add_argument("paths", nargs="*", help="paths to fix and format")
    format_parser.set_defaults(func=cmd_format)

    typecheck_parser = sub.add_parser("typecheck", help="run mypy")
    typecheck_parser.add_argument("paths", nargs="*", help="paths; defaults to src scripts tests")
    typecheck_parser.set_defaults(func=cmd_typecheck)

    check_parser = sub.add_parser("check", help="compose gates, preserving nonzero exits")
    check_parser.add_argument("--tier", default="L2", choices=TIERS)
    check_parser.set_defaults(func=cmd_check)

    benchmark_parser = sub.add_parser("benchmark", help="time the active controller path")
    benchmark_parser.add_argument("--rows", type=int, default=20_000)
    benchmark_parser.add_argument("--repeat", type=int, default=5)
    benchmark_parser.set_defaults(func=cmd_benchmark)

    build_parser = sub.add_parser("build", help="build the wheel and optionally smoke-test an install")
    build_parser.add_argument(
        "--smoke", action="store_true", help="install the wheel outside the checkout and import it"
    )
    build_parser.set_defaults(func=cmd_build)

    docs_parser = sub.add_parser("docs", help="validate local documentation links and anchors")
    docs_parser.add_argument(
        "--skills", action="store_true", help="also require canonical/shared skill names and mirrors to agree"
    )
    docs_parser.set_defaults(func=cmd_docs)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except DevError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
