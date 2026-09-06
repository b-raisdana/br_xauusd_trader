# Data

## Canonical migrated input

- `ranges.csv`: daily XAUUSD Zones supplied for the historical research period.
- Columns: `date,lower,upper,priority,enabled,note`.
- SHA-256: `d146fe4650ea52da64b585a7a0ee15d874e68801f12764481e9ef8c773c9f4f3`.
- The uploaded file is byte-identical to the `data/ranges.csv` and `reference/ranges.csv` copies inside the historical technical bundle.

Large market datasets normally remain local/outside Git.

Recommended:
- `data/raw/` — immutable source snapshots (ignored by Git)
- `data/cache/` — reproducible caches (ignored)
- small deterministic test fixtures may live under `tests/fixtures/`

For every important experiment, record source/range/version/hash or other reproducibility identifier in `docs/EXPERIMENTS.md`.
