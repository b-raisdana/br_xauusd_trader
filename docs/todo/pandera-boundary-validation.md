# Replay Pandera boundary fix

Verified on October 9, 2026.

The five reported functions in execution_batch/adapter.py, structure.py,
economics.py and projection.py now use @pandera_validate with explicit
Pandera input and output types. No allow_pandas_dataframe override is used.
domain/batch_schema.py defines UTC stream timestamps, completed candles,
replay window openings and the six output table types. Existing explicit
output schema validation remains in projection.py because nested tuple
members require individual validation.

Completed candles accept bar_time as a column or named index level. A
columnless empty window frame remains valid; nonempty windows require all
fields consumed by the replay scan. Runtime imports resolve decorator
annotations, including the previously unresolved BatchReplay in zones.py.

Validation:

- check_pandera_decorator: passed for all affected implementation files.
- Ruff lint and formatting: passed for execution_batch, batch_schema.py and
  test_batch_schema_validation.py.
- Structural and batch replay tests: 44 passed.
- New schema boundary and existing vectorized replay integration tests:
  10 passed.
- Report acceptance tests could not collect due to the existing
  replay_portfolio.py import of application.domain.execution_schema;
  this separate import defect was left outside the decorator fix.
