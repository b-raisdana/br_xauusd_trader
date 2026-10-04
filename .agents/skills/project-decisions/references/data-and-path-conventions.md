# Data, path and logging conventions

## Timestamps and timeframes

- Timestamp columns and index levels carry explicit units and timezone. Prefer
  `pd.Timestamp` with `tz=` at construction and `.as_unit("ns")` for persisted
  frames, so round trips do not silently change precision.
- Timeframe identity travels with the data (an index level or an explicit
  column), never as an implicit assumption of the caller.
- Use `pd.Timedelta`/offset aliases from the configured timeframe registry
  rather than hard-coded strings such as `"15min"` scattered across modules.

## Config, paths and CLI

- One authoritative config path per concern. Bind with the project's
  `BaseContextConfig.use()` context mechanism; do not mutate module-level config
  objects implicitly.
- Environment overrides use the `DLF_` prefix for the application config and
  bare names for `br_pre_commit` tooling. These are independent: setting
  `ENVIRONMENT=production` does **not** disable application assertions, and
  setting `DLF_ENVIRONMENT=production` **does** turn off
  `Config.check_assertions`. Correctness gates must leave `DLF_ENVIRONMENT` at
  `development`.
- CLI entry points use Typer. Derive repository roots from `__file__`; never
  require developer-specific absolute paths.
- Prefer a thin CLI layer over business logic, so the same code path is
  reachable from tests and from `scripts/dev.py`.

## Helper imports

`helper.importer` re-exports heavy third-party symbols (`pt`, `pa`, `pya`) so
that import cost is paid once. Import from it rather than importing pandas,
pandera or pyarrow directly in feature modules. Optional symbols are imported
defensively; if a symbol is always `None`, either install it or remove it from
the re-export instead of leaving a silently missing dependency.

## DRY

Merge duplicated logic only after confirming the two sites must stay in sync.
Duplication is preferable to a wrong abstraction when the variants diverge.

## No no-op calls

Remove calls that do nothing in the current configuration rather than leaving
them as dead configuration switches. If a switch must stay, make it observable
in the output or remove it.

## Logging and exceptions

Diagnostics are owned by the boundary that can explain the failure. Prefer
boundary-owned diagnostics and exception chaining over logging before every
`raise`. Avoid duplicate logs for the same event, and never dump sensitive
values, credentials or full market payloads into logs. For a failing stage,
report stream, day, category and the violated invariant, then re-raise with
context.

## Comments

Comments state intent that the code cannot express: the reason, the invariant,
the ordering requirement. They do not restate the next line. Keep them brief.