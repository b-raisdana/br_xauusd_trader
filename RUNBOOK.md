# Development runbook

Run commands from the repository root in PowerShell. Use Windows Python ≥3.12: dependencies include MetaTrader5. `py -0p` lists installed interpreters; the Windows Store `python` alias may be unusable. Activate the selected environment before hooks/tests.

## Setup

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
git submodule update --init br_pre_commit
```

Python 3.14 is the locally detected tool environment; dependency resolution for a fresh environment must still succeed. Dependencies are authoritative in `pyproject.toml`; no lockfile guarantees reproduction. Keep secrets in ignored local environment files; path defaults and overrides live in `src/config/config.py`. Initialization may write local logs/caches.

## Discover and validate

```powershell
rg --files src tests
rg -n 'ReplayConfig' src/application tests
python scripts/check_repository.py
python -m pytest -m unit
python -m pytest tests/test_batch_execution_replay.py
python -m pytest
python -m ruff check src scripts tests
python -m ruff format --check src scripts tests
python -m mypy src scripts tests
python -m pre_commit run --files <changed-files>
```

Replace `<changed-files>` with explicit paths. For shared-configuration changes run `python -m pre_commit run --all-files`; inspect automatic fixes and preserve unrelated work. Hooks may need to fetch pinned environments. The incremental ratchet uses staged changes and its baseline; do not regenerate the baseline to conceal regressions. Protected-branch commits require existing Git policy.

Pytest markers and xdist defaults are in `pyproject.toml`. Unmarked tests default to unit; compiled Numba/Vectorbt or end-to-end tests use integration and slow markers. `-n 0` overrides xdist for diagnosis or constrained hosts. Unit selection still imports `tests/conftest.py` and needs application dependencies. Full strategy tests are unnecessary for documentation-only changes; report checks actually executed.

The repository checker uses only the standard library, checks navigation links, package paths, skill mirrors and workflow alignment, and does not initialize MT5. Its isolated regression tests run with `python -m unittest discover -s scripts/tests`.

## Execution boundaries

```powershell
python -m application.xauusd_trading_strategy_1_vector --help
```

Use an editable installation or set `PYTHONPATH` to `src` for module discovery. The CLI acquires broker data unless both `--ticks-input` and `--candles-input` are supplied; inspect options before running. Signals-only is default; `--execution-config` supplies explicit offline replay economics. `--no-backtest` skips reporting. Never invoke live enablement as validation. Native compilation requires MetaEditor and the platform Trade include; Python checks do not establish native compilation.

## Search and skills

`.ignore` narrows default ripgrep discovery around archives, mirrored skills and machine state; it does not change Git ownership or test collection. Search retained references explicitly, e.g. `rg -n 'ExecutionReplay' archive_not_used_trash`. IDE indexes may need local exclusions; no global/editor settings are changed.

Shared skill authoring starts in `.kilo/skills/`. Other agent directories are discovery mirrors, retained for compatibility. Stage canonical skill changes only when authorized; the sync hook propagates staged intent and refuses conflicting edits. Without staging, update matching mirrors together and run the read-only repository checker. Do not invoke sync mutation merely to inspect consistency.
