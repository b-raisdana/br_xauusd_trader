# State variable run comparison design

## Goal

Design `scripts/compare_state_variables.py` to compare the available MT5 reports with Python result artifacts using `docs/State-Variables.Glossary.csv` as the variable map. This is a design only; no comparison script is implemented here. Report capture gaps separately from value differences.

## Inputs

- MT5 journal and summary CSVs from `data/MT5/`.
- Python source tick-state Parquet, signals Parquet, windows Parquet, and provenance JSON from `data/`.
- The glossary CSV and active EA/Python source hashes.
- CLI overrides for each path, output directory, comparison start/end, timestamp timezone, and numeric tolerances.

Default paths should match the checked-in artifact names. Reject missing files, duplicate glossary names, unsupported schemas, or ambiguous timezones with a concise error. Do not load the 325 MB source Parquet fully into memory; use PyArrow column projection and row-group iteration.

## Preflight and pairing

- Inventory headers, row counts, timestamp ranges, symbol, broker, source hashes and provenance before comparing values.
- Normalize MT5 server timestamps with an explicit configured timezone; preserve the original string and normalized UTC timestamp. Python timestamps already carry timezone information.
- Require matching symbol, broker, overlapping interval and confirmed input/configuration identity for a parity result. The current files do not pass this gate: Python provenance has no tick/candle input hashes and has `configuration: null`; Python covers July 29–August 28 while the MT5 journal covers July 29–August 3. Default status must be `OVERLAP_ONLY / PAIRING_UNVERIFIED`.
- Treat the MT5 summary as an event report and the journal as event rows plus one sparse snapshot. Do not fill absent snapshot cells forward unless the comparison rule explicitly requests last-known state and labels it as carried.

## Current run screen

The artifacts support a coarse signal-count screen, not an event-by-event result comparison. MT5 journal counts are 44 `BREAKOUT_SIGNAL`, 19 `REVERSAL_SIGNAL`, 19 `PULLBACK_CYCLE_CREATED`, 14 `PULLBACK_PENETRATION_LATCHED`, 14 `PENDING_PLACED`, 33 `ORDER_FILLED` and 33 `POSITION_CLOSED` rows across July 29–August 3 server dates. Python signals contain 461 breakout, 1,238 reversal and 145 pullback rows across July 29–August 28 UTC. Restricting Python by UTC calendar date to July 29–August 3 gives 69 breakout, 194 reversal and 19 pullback rows. Python family IDs are 0=breakout, 1=reversal, 2=pullback.

These counts are not a reliable paired-run difference: the MT5 server timezone is unspecified, date ranges use different clocks, MT5 `PULLBACK_CYCLE_CREATED` is not the same event as a Python pullback signal, and input/configuration identity is unverified. They show the artifacts need alignment and provenance before declaring event matches. No per-event result comparison was performed.

## Normalized comparison model

Build long-form records with `source`, `artifact`, `event_time_utc`, `broker_day`, `event_id`, `stream_tick`, `bar_time`, `variable`, `value`, `capture_kind` and `source_row`. Preserve native IDs and raw values alongside normalized values.

- Resolve each variable with the five artifact-coverage columns in the glossary. Support scalar fields, JSON containers (`g_zones`, `g_cycles`, `g_requests`, `g_positions`, `g_raw_zones`) and documented flattened Python columns.
- Parse JSON strictly and report malformed values with file, row, field and excerpt. Keep arrays/records as structured JSON until field-level flattening.
- Map labels and enums through explicit lookup tables; never compare raw EA and Python spellings implicitly.
- Join by verified tick/event identity where available. Otherwise use event type plus normalized time and stable signal identity as a candidate key, report ambiguous/missing matches and do not silently nearest-join.
- Compare exact discrete values and IDs exactly. Compare numeric values with explicit absolute/relative tolerances derived from symbol digits or command-line settings; include raw delta and tolerance in each result. Never default to fuzzy timestamp or ticket matching.

## Outputs

Write a machine-readable comparison CSV/Parquet with one row per variable/event match and columns for MT5 value, Python value, delta, tolerance, match status, capture status, join key and provenance. Write a compact JSON/Markdown run report with input hashes, schema and row counts, date coverage, pairing status, unmatched events, missing variables by artifact, differences by variable, and first differences in time order. Keep `NOT_CAPTURED`, `NO_MATCH`, `MATCH`, `DIFFERENT`, `AMBIGUOUS` and `PAIRING_UNVERIFIED` distinct. Exit nonzero for invalid inputs or when strict verified parity mode finds differences; overlap-only mode must never print a parity pass.

## Capture improvements needed before a useful state comparison

### MT5 journal/report

- Emit a stable `run_id`, EA source hash/version, input/configuration fingerprint, tick ordinal, bar time, symbol, broker, Bid and Ask on comparable event rows.
- Add a configurable state-snapshot mode that serializes every mapped shared variable at each relevant event or a documented periodic checkpoint. Populate all rows consistently; current global/compound snapshots appear only on `MULTI_ZONE_TICK_GAP`.
- Include complete zone, pullback-cycle, request, order and position records with stable identity and timestamps. Keep request intent separate from broker order/deal/position outcomes.
- Include session, account/risk, daily PnL, lock, and configuration values when those variables participate in the comparison. Current summary output has no complete configuration or state snapshot.

### Python result dump

- Persist an MT5-shaped event/state trace keyed by `stream_tick`, event ordinal, `bar_time` and broker day, with the glossary variable name and value. Include per-event snapshots for trend, zones, cycles, request/order/position state, session and account/risk state.
- Persist the input tick and candle/bootstrap fingerprints, normalized zone input hash, all effective strategy/EA-equivalent settings, code revision/hash and timezone in provenance; current provenance omits tick/candle hashes and effective configuration.
- When execution replay is enabled, persist order/request/deal/position transitions and economics as first-class artifacts. The current signals/windows/tick artifacts do not provide those execution outcomes.

## Acceptance checks for a future implementation

- A synthetic fixture with exact matches, numeric tolerance, missing fields, malformed JSON, duplicate timestamps, ambiguous event joins and mismatched provenance produces deterministic labeled outcomes.
- Chunked Parquet reading yields the same ordered records as a small in-memory fixture.
- Every glossary variable receives an explicit artifact-coverage status; no missing field is silently treated as null/zero/false.
- Strict parity output is possible only when identity preflight passes and every required event/state comparison is matched with no unexplained difference.
