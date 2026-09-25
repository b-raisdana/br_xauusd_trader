# State-Variables.Glossary

Document MT5/Python state correspondence and every explicit read/write location in [State-Variables.Glossary.csv](State-Variables.Glossary.csv). This is a source audit, not a strategy run or parity test.

## Scope and sources

- Use **Global Strategy-Level State** and **Core Algorithmic State** in [Vectorization Implementation Plan.md](Vectorization%20Implementation%20Plan.md) as the inventory guide; confirm coverage against current declarations.
- MT5: `mt5/XAUUSD_MVP.mq5` and handwritten `mt5/include/*.mqh` helpers. Include explicit accesses in embedded smoke functions; exclude generated fixtures, archives and external tests.
- Python: the selected `VectorizedXauUsdStrategy` in `../../src/application/xauusd_trading_strategy_1_vector/the_strategy.py` and its active `zone_cache.py`, `trend.py`, `engagement.py`, `signals.py` and `actions.py` collaborators. Include the `XauPullbackWindowState` defaults and `create_pullback_window` helper actually invoked from `src/domain/xau_usd/`; do not substitute other scalar state, unused modules or archived alternatives for missing vector behavior.
- Include one row per strategy global and `XauMarketCoordinator` field. Retain all nested fields of `XauTrendReferenceState`, `XauDailyZoneSignalState` and `XauPullbackWindowState`; aggregate rows do not replace field rows.
- Retain `EXECUTION_BINDINGS_FILE` and `ORDER_AUDIT_FILE` as read-only configuration entries. Exclude `Inp*` settings, transient locals and further expansion of execution/request records. Locals may be counterparts or aliases, not additional inventory rows.
- Record actual behavior, including incomplete behavior. Correspondence does not prove parity or supersede `docs/RULES.md`.

## CSV contract

Use UTF-8, comma delimiters, standard CSV quoting, one header and one row per unique MT5 name. Keep these six columns in order:

| Column | Meaning |
| --- | --- |
| MT5-Name | Exact global name or qualified `Struct.field`. |
| Py-Difference | Python column/attribute/local names when different; blank if the counterpart has the same unqualified name. Separate split representations with `; ` and explain partial mappings. Use `NOT_IMPLEMENTED` when absent. |
| MT5 Used as Input | All explicit reads, including reads through helper calls. |
| MT5 Modifies the Value | All explicit writes, initialization/reset and mutations through helper calls. |
| Py Used as Input | All explicit reads of the Python representation. |
| Py Modifies the Value | All explicit writes, initialization/reset and mutations of that representation. |

Locations use repository-relative `path:line,line; other/path:line`, with one-based line numbers, sorted paths and ascending unique lines. For multiline expressions, cite the variable-access line; for Python column selections, cite the starting line of the subscript expression. References describe the audited working tree, including uncommitted source edits.

Use `NONE` when a counterpart exists but has no explicit operation in that column. Use `NOT_IMPLEMENTED` in both Python location columns when absent. Never use ambiguous `NA` or blank location cells. Comments, docstrings and TODO descriptions are not implementation evidence.

## Classification rules

- Reads use the current value in calculations, returns, comparisons, branches, loops, orders/actions, logging or serialization. Reading array size counts. Merely naming an assignment target does not read its old value.
- Writes include assignment, reassignment, increment/decrement, arithmetic update, append/remove/insert, resize, initialization/reset and mutable-object changes. Count global declaration initialization, including implicit defaults; a struct member declaration alone is not a runtime write. Constant initialization counts even though later mutation is forbidden.
- Read-modify-write operations belong in both columns: `a = a + 1` reads and writes; `a = 0` only writes. Index expressions are read independently of writes to selected elements.
- Inspect callees before classifying reference arguments; a non-const reference alone does not prove mutation. Cite the call-site argument when a helper reads/writes it. Include helper field accesses and relevant scalar/array parameter aliases in the corresponding field row.
- Aggregate rows include explicit accesses to their members. Record whole-object helper calls on the aggregate row; field rows cite explicit field operations inside helpers, without inventing separate field occurrences at the call site.
- Python DataFrame columns count as representations even when flattened or only initialized. Record actual operations without inferring missing lifecycle updates. Generic frame copying, grouping, concatenation, returning and assignment back to a parent frame are transport operations, not additional per-column algorithmic accesses. Track explicit `self._per_tick_temp_state` and `self._per_candle_temp_state` accesses separately from column operations.
- Distinguish collections from scalar placeholders. Shared engagement columns alone are not independent per-zone state; `pullback_active` is not a collection of windows. Trace dynamic column names, local lineage dictionaries and emitted window snapshots separately. Explain partial mappings without claiming equivalent ownership, shape or reset semantics.

## Execution and acceptance

1. Read the plan, current state, source declarations and relevant working-tree diff.
2. Enumerate globals and the four state structs. Preserve declaration order within groups; require exactly one row per scoped name.
3. Trace direct accesses, aliases, member mutations and helper effects. Resolve Python mappings from executable code, including column strings; mark absent counterparts explicitly.
4. Rebuild the CSV. Verify every cited file exists, each line is in range and each location supports its classification. Review initialization, read-modify-write, helper mutation, split-array and missing-counterpart cases.
5. Parse the saved CSV again. Require the exact six-column header, six fields per row, unique names, complete inventory coverage, sorted/deduplicated references and consistent missing-value markers. Review both document diffs. No backtest, broker connection or strategy-code change is required.

## Current audit

- **DONE — 2026-09-20:** clarified scope, nested inventory, reference syntax, absent-versus-unused markers, helper effects and partial vector mappings; rebuilt the CSV against the working tree.
- Inventory: 73 rows = 41 mutable globals + 2 read-only configuration entries + 13 coordinator fields + 4 trend fields + 5 zone-state fields + 8 pullback-window fields.
- Python gaps: 43 rows have no counterpart, including operational/execution globals and per-zone usage counters. `reversal_keys`, `attempted_bars`, `pullback_penetration_latched` and `pullback_sequence` have initialization but no algorithmic reads. Window objects initialize pending state, but the active vector path does not implement pending-order updates or the complete pullback lifecycle.
- Partial mappings: `g_market_state` maps to the per-tick and per-candle temporary frames; bar time and a derived local `bar_id` approximate bar identity; trend arrays are split into columns in both frames; engagement has per-zone columns and aggregates. Breakout enumeration updates sequence state and emits pullback opening snapshots with per-zone/direction lineage columns. Cached zones and opening snapshots are not complete daily-zone/window lifecycle state. These are existing representations, not accepted parity.
- Acceptance: inventory/schema/reference checks and focused source review completed. No implementation files changed or trading execution performed. Refresh after source edits that change behavior or line numbers.
