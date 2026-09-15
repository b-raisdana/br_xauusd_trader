# MetaTrader Independence Conversion Plan

## Objective

Remove all MetaTrader 5 (MT5) and MQL5 dependencies from the project to make it platform-agnostic, while preserving the validated Python contract parity and all reusable evidence/logic.

## Baseline State

- Python domain package `src/xauusd/` implements 19 canonical vectors (Decimal precision)
- MQL5 baseline `src/mt5/` (3,223 lines, 12 files) is hard-disabled outside Strategy Tester
- 6 MQL5 config profiles in `config/mt5/` (all `AllowLiveTrading=0`)
- 6 bridge scripts, 6 MT5-dependent test files
- 139 Python tests PASS; MetaEditor 0 errors/0 warnings

## Phase 0: Pre-flight Inventory (DONE)

- [x] `docs/todo/mapping-findings.md` written with full parity mapping

## Phase 1: Remove MT5 Live Dependencies

### 1.1 Scripts — Remove MT5 import bridge

- [ ] **`scripts/export_mt5_ticks.py`** — Delete file. Contains `import MetaTrader5`; no Python-only equivalent.
- [ ] **`scripts/match_mt5_time_basis.py`** — Delete file. Contains `import MetaTrader5`; no Python-only equivalent.
- [ ] **`scripts/compare_signal_parity.py`** — Delete file. Depends on `load_mt5_tick_bars` (MT5 tick source) + Python replay for parity comparison against MQL output.

### 1.2 Python Module — Remove MT5-specific helpers

- [ ] **`src/xauusd/tick_data.py`** — Delete file. Contains `load_mt5_tick_bars` which parses MT5-exported CSV. No Python-only replacement needed (replay already tested with synthetic ticks).
- [ ] **`src/xauusd/__init__.py`** — Remove `load_mt5_tick_bars` import (line 96) and `"load_mt5_tick_bars"` from `__all__` (line 197).
- [ ] **`scripts/presentations.py`** — Either delete (if only used for MT5 reports) or refactor to not use `load_mt5_tick_bars`.

### 1.3 Requirements

- [ ] **`requirements.txt`** — Remove `# MetaTrader5==5.0.6180` comment.

## Phase 2: Remove MQL5 Source & Config

### 2.1 Source files

- [ ] **`src/mt5/` directory** — Delete entirely (3,223 lines):
  - `XAUUSD_MVP.mq5` (1,477 lines)
  - `include/XauAudit.mqh` (80 lines)
  - `include/XauContracts.mqh` (487 lines)
  - `include/XauCoordinator.mqh` (223 lines)
  - `include/XauExecution.mqh` (330 lines)
  - `include/XauNative.mqh` (179 lines)
  - `include/XauRequests.mqh` (144 lines)
  - `include/XauState.mqh` (74 lines)
  - `include/XauTesterBroker.mqh` (208 lines)
  - `include/XauTesterRisk.mqh` (170 lines)
  - `include/XauVisual.mqh` (74 lines)
  - `generated/CoreVectors.mqh` (87 lines)
  - `generated/DailyZones.mqh` (570 lines)

### 2.2 Config files

- [ ] **`config/mt5/` directory** — Delete entirely:
  - `contract_smoke.ini`
  - `tester_200.ini`
  - `tester_300.ini`
  - `tester_multiday_200.ini`
  - `tester_restart.ini`
  - `tester_qa_20260729.ini`

### 2.3 Vector/Zone generation scripts

- [ ] **`scripts/generate_mql_vectors.py`** — Review. Generates `CoreVectors.mqh` from `tests/vectors/core_contracts.json`. If MQL5 files are deleted, this becomes dead code.
- [ ] **`scripts/generate_mql_zones.py`** — Same: generates `DailyZones.mqh` from `data/ranges.csv`. Dead code after deletion.
- Decision: Keep the scripts if vectors/zones remain useful as Python reference, or delete if only MQL5 consumers exist.

## Phase 3: Remove/Update MT5-Dependent Tests

### 3.1 Delete MT5-specific tests

- [ ] **`tests/test_mt5_tick_export.py`** — Delete (tests `export_mt5_ticks.py`)
- [ ] **`tests/test_mt5_time_basis.py`** — Delete (tests `match_mt5_time_basis.py`)
- [ ] **`tests/test_mt5_source.py`** — Delete (25 tests asserting MQL5 source strings)
- [ ] **`tests/test_mql_zone_generation.py`** — Delete (tests `generate_mql_zones.py` + `generated/DailyZones.mqh`)

### 3.2 Update remaining affected tests

- [ ] **`tests/test_equivalence_vectors.py`** — Remove line 397 test `test_generated_mql_header_matches_canonical_json` (reads `generated/CoreVectors.mqh`). Keep vector validation tests.
- [ ] **`tests/test_signal_parity_script.py`** — Delete (tests `compare_signal_parity.py` which is deleted)
- [ ] **`tests/test_tick_data.py`** — Delete (tests `load_mt5_tick_bars` which is deleted)
- [ ] **`tests/test_final_report.py`** — Review; may reference MT5 evidence structure.

## Phase 4: Update Documentation

### 4.1 README.md

- [ ] Remove MT5 references from Market line and folder structure.

### 4.2 docs

- [ ] `docs/CURRENT_STATE.md` — Update "Current MQL5 baseline" entries (lines 56-58, 72-73, 74-76, 79).
- [ ] `docs/TODO.md` — Remove completed "MetaTrader Independence" items, mark new ones.
- [ ] `docs/TEST_STATUS.md` — Update test counts (was 139 + 25 MQL5 source tests).

## Phase 5: Verification

- [ ] Run `python -m pytest tests/` — all tests pass
- [ ] Run `python -m ruff check src/ tests/` — lint clean
- [ ] Run `python -m mypy src/` — typecheck clean
- [ ] Grep `mt5|MetaTrader|Mql|MQL` in `src/`, `scripts/`, `tests/` — no matches
- [ ] Git checkpoint

## Execution Log

(Progress will be recorded here as work proceeds)
