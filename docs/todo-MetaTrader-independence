# TODO: MetaTrader Independence

## Objective
Remove all MetaTrader 5 (MT5) dependencies from the project to make it platform-agnostic.

## Items to Remove

### Source Code
- `src/mt5/` - entire MQL5 EA directory
  - `XAUUSD_MVP.mq5`
  - `include/XauAudit.mqh`
  - `include/XauContracts.mqh`
  - `include/XauCoordinator.mqh`
  - `include/XauExecution.mqh`
  - `include/XauNative.mqh`
  - `include/XauRequests.mqh`
  - `include/XauState.mqh`
  - `include/XauTesterBroker.mqh`
  - `include/XauTesterRisk.mqh`
  - `include/XauVisual.mqh`
  - `generated/CoreVectors.mqh`
  - `generated/DailyZones.mqh`

### Configuration
- `config/mt5/` - MT5 configuration files
  - `contract_smoke.ini`
  - `tester_200.ini`
  - `tester_300.ini`
  - `tester_multiday_200.ini`
  - `tester_qa_20260729.ini`
  - `tester_restart.ini`

### Scripts
- `scripts/export_mt5_ticks.py` - exports MT5 UTC ticks
- `scripts/match_mt5_time_basis.py` - matches MQL server-time against MT5
- `scripts/generate_mql_zones.py` - generates MQL daily-zone loader
- `scripts/generate_mql_vectors.py` - generates MQL core-vector header
- `scripts/compare_signal_parity.py` - compares Python/MQL signal counts
- `scripts/presentations.py` - uses `load_mt5_tick_bars` for reports

### Python Module
- `src/xauusd/tick_data.py` - contains `load_mt5_tick_bars()` function
- Remove `load_mt5_tick_bars` import/export from `src/xauusd/__init__.py`

### Tests
- `tests/test_mt5_tick_export.py`
- `tests/test_mt5_time_basis.py`
- `tests/test_mt5_source.py`
- `tests/test_mql_zone_generation.py`
- `tests/test_equivalence_vectors.py`
- `tests/test_signal_parity_script.py`
- `tests/test_tick_data.py`
- `tests/test_final_report.py`

### Requirements
- `requirements.txt` - remove `# MetaTrader5==5.0.6180` comment

### Documentation
- `README.md` - remove MT5 references from Market line and folder structure

## Verification Steps
1. Run `python -m pytest tests/` - all tests should pass
2. Run `python -m ruff check src/ tests/` - lint should pass
3. Run `python -m mypy src/` - typecheck should pass
4. Grep for `mt5` or `MetaTrader` in `src/`, `scripts/`, `tests/` - should return no matches

## Notes
- The core domain logic in `src/xauusd/` (zones, trend, signals, risk, safety, execution, replay, audit) should remain intact
- Legacy reference implementations in `legacy_reference/` are kept for regression/audit purposes only
- This task makes the project platform-agnostic, enabling potential future use with other brokers/platforms