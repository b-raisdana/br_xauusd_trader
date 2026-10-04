# MT5 journal and Python comparison guide

## Evidence and scope

Inspected `07-30TO08-25_journal.csv` and current source on 2026-10-04. The CSV has **1,936 rows, 41 event types and 25 columns**, covering **2026-07-29 23:59:59.426 through 2026-08-03 23:59:58.692 in server time**. Its filename does not establish coverage through August 25. The Leader intentionally limits both Python and MT5 periods for faster testing/troubleshooting and owns subsequent period adjustments; the short sample is not a defect. There are 19 reversal signals, 44 breakout signals, 14 pending placements, 33 fills and 33 position closures. A signal count is not a trade count.

`EA_INITIALIZED` records `EXPLICIT_ROBUST`, `ALL_FLAT`, five-minute preclose, high-zone reversal maximum 2, high-zone SL multiplier 1.50, maximum live positions 3, volume 0.01, initial deposit 10000, `GROSS_DAILY` portfolio risk and risk percentage 30. These are observed settings, not a complete tester configuration: preserve the tester `.set`, symbol specification, zones, ticks, sessions and compiled-EA provenance too. Current source explains the records but does not prove which binary generated them.

This guide describes current behavior; it does not change trading rules or establish native execution parity.

## Produce Python output with `@pandera_validate(dump_output=True)`

The decorator validates the returned object and dumps it; it does **not** convert Python state into the EA's 25-column journal. Dumps are diagnostics for comparing calculations, signals and replay state.

The active path is `__main__.main → run_vectorized_strategy → process_tick_data → process_native_stream → MarketState.step`, with optional `ExecutionReplay`. The older standalone signal/trend helpers are not the active stream's independent comparison target.

### Existing dump points

| Function | Return | Useful output |
| --- | --- | --- |
| `runner.run_vectorized_strategy` | `ResultFilesManifest` | JSON representation of the manifest; not its referenced DataFrames |
| `VectorizedXauUsdStrategy.process_tick_data` | `ResultFilesManifest` | Same limitation; persisted artifacts remain authoritative |
| `VectorizedXauUsdStrategy.process_native_stream` | Tuple of per-tick and per-candle DataFrames | Two Parquet dumps plus a JSON descriptor; tuple components are numbered `1` and `2` |

All three already use `@pandera_validate(dump_output=True)`. Do not add the decorator to asynchronous `main`, which returns `None`, expecting it to capture internal frames. It dumps return values, not local variables or inputs.

1. Use the project's installed Python environment from the repository root. Set `$env:ENVIRONMENT = 'development'` **before importing** the decorator; its own `BrPanderaConfig` bypasses validation and dumping in `production`.
2. Use identical zone rows, symbol (`XAUUSD!` here), broker ticks including Bid/Ask and ordering, broker timezone, M15 boundaries and historical bars. Include at least three closed M15 candles at startup; use sufficient preceding history for structural trailing, which scans up to 100 shifts.
3. Supply explicit replay configuration if comparing fills, positions, costs or risk. Without `--execution-config`, the strategy runs signals only. Match every EA input, capital basis, balance, sessions, native stop constraints and economics; Python defaults are not proof of matching settings.
4. Run the command below for a **single-day diagnostic**. The current CLI intentionally keeps only the first zone day. Compare the same short interval and initialization in MT5. If testing multiple days, call `run_vectorized_strategy` with prepared frames covering the selected broker days in one chronological run; preserve the same `MarketState` per broker/symbol across days. Separate fresh processes per day lose trend/account/carry state and cannot prove cross-day equivalence. No period expansion is required for this tracing plan.
5. Inspect dump warnings and the JSON descriptor's `output_dump_reference.parquet` fields. Dumps are best-effort: failed serialization is logged and swallowed, so a successful strategy run does not prove every dump was written.

```powershell
$env:ENVIRONMENT = 'development'
python -m application.xauusd_trading_strategy_1_vector --symbol 'XAUUSD!' --zones 'mt5/MQL5/Files/ranges.csv' --output 'logs/comparison/python-results.parquet' --execution-config 'logs/comparison/replay-config.json'
```

The zones and replay-config paths must point to your verified inputs; the command does not create either file. Use `.parquet`: although the CLI accepts `.csv`, current `save_results_to_file` always calls `to_parquet`, even for a CSV suffix.

Default dumps go to `<repository>/logs/output_dump`. To select a run-specific folder, call this in the **same Python process**, before invoking the strategy:

```python
from br_pre_commit.src.br_pandera.dump_folder import configure_pandera_dump_folder

configure_pandera_dump_folder("logs/comparison/mt5-jul30-aug03")
```

For a new typed DataFrame-producing comparison boundary, the supported syntax is:

```python
from br_pre_commit import pandera_validate

@pandera_validate(dump_output=True)
def comparison_frame(...) -> pt.DataFrame[ComparisonSchema]:
    ...
```

This last snippet is a pattern, not runnable code: define the schema and function first. Existing stream dumps need no new decorator. Names include source namespace, `VectorizedXauUsdStrategy=process_native_stream`, component number and content hash. Hashes identify content, not chronological call order; identical outputs can reuse the same path. DataFrame indexes normally become columns. Composite returns produce a descriptor and separate frame files; a manifest object falls back to its representation rather than recursively loading its files. Check the implementation rather than the submodule README's obsolete `pandera.dump_folder` import example.

### Read and compare the artifacts

```python
import json
from pathlib import Path
import pandas as pd

folder = Path("logs/output_dump")  # or the configured folder
for descriptor in folder.glob("*VectorizedXauUsdStrategy=process_native_stream.*.json"):
    refs = json.loads(descriptor.read_text(encoding="utf-8"))
    tick_path = refs[0]["output_dump_reference"]["parquet"]
    if tick_path is None:
        raise RuntimeError(f"Missing tick dump: {descriptor}")
    ticks = pd.read_parquet(descriptor.parent / tick_path)
    print(descriptor.name, len(ticks), ticks.columns.tolist())

journal = pd.read_csv(
    "mt5/MQL5/Files/07-30TO08-25_journal.csv",
    dtype=str, keep_default_na=False,
)
```

Keep tickets as strings or exact integers; never convert them through floating point. With `keep_default_na=False`, literal `N/A` remains distinguishable from blank fields.

| Comparison layer | Python evidence | MT5 evidence and alignment |
| --- | --- | --- |
| Market/trend | `reference_high`, `reference_low`, `trend`, per-candle extrema, `mt5_state` | Reference/state events; use three **closed** bars and actual callback time |
| Engagement/signals | `breakout_signals`, `reversal_signals`, `pullback_signals`, `pullback_windows_opened` | Zone/touch/breakout/reversal/cycle events; normalize family/direction and daily zone lineage |
| Execution | `execution_events`, `orders`, `positions`, `entry_rejections`, `pullback_feedback` | Placement/fill/closure/modification events; compare lifecycle transitions, not every snapshot row |
| Account/risk | Daily realized PnL, gross loss, balance, locks and `mt5_state` | Portfolio-risk, margin and cost notes; match cash assumptions and session mode |

Explode each signal/event collection in its original order into a canonical comparison table: `broker_day`, UTC timestamp, tick/callback ordinal, M15 bar, zone lineage, family, direction, breakout lineage, event kind, requested/fill prices, SL/TP and logical trade key. Decode `mt5_state` with `json.loads`. Map Python enum values explicitly; do not compare their raw spellings with `TREND_UP` or `R-B`.

Convert server timestamps to UTC using the broker's verified timezone and DST history, not the workstation timezone. Preserve CSV row order for tied timestamps. A closed-bar breakout is logged when the next bar is processed, while its decision belongs to the preceding bar; `server_time` alone is insufficient. At midnight, the old bar is processed before the daily reset, so date extracted from the logging timestamp may differ from the breakout's owning day.

Join by semantic identity and sequence, then report the **first differing transition**, expected/actual fields and source input. Compare prices using the symbol's recorded digits/tick size; the journal rounds to `_Digits`, so it cannot verify hidden precision. Do not join unrelated runs by `event_id`, native tickets or Python-generated request IDs. Establish a logical trade mapping at placement/fill and follow it through closure. Repeated snapshot entries must not be counted as new trades.

There is currently no built-in export that recreates every EA journal event, `rule_id` and overloaded field. Creating identical-shaped CSV output requires an explicit event adapter; decorating a DataFrame return alone cannot supply absent events. Ordinary `LinearReplayEconomics` is an assumption-based replay. Exact native comparisons require recorded quotes, operation responses, account/order/position views and ordered transaction callbacks through `RecordedExecutionReplay`; this CSV lacks that complete recording. The existing `trace.first_difference` can compare normalized traces once both traces exist. Do not claim fill/account parity from signal agreement or this journal alone.

Sources: [runner](../../../src/application/xauusd_trading_strategy_1_vector/runner.py), [entry point](../../../src/application/xauusd_trading_strategy_1_vector/__main__.py), [stream processing](../../../src/application/xauusd_trading_strategy_1_vector/the_strategy.py), [market transitions](../../../src/application/xauusd_trading_strategy_1_vector/market.py), [replay configuration](../../../src/application/xauusd_trading_strategy_1_vector/domain/replay.py), [native replay](../../../src/application/xauusd_trading_strategy_1_vector/native_replay.py), [trace comparison](../../../src/application/xauusd_trading_strategy_1_vector/trace.py), [export](../../../src/application/xauusd_trading_strategy_1_vector/reporting.py), [dump implementation](../../../br_pre_commit/src/br_pandera/output_dump.py), [dump configuration](../../../br_pre_commit/src/br_pandera/dump_folder.py), [decorator](../../../br_pre_commit/src/br_pandera/__main__.py).

## Planned Python changes: traceable DataFrame returns

This section is an **implementation plan**, not implemented behavior. Scope: expose existing state and transitions with MT5-compatible tags in typed DataFrame returns. Keep file writing entirely with `@pandera_validate(dump_output=True)`; no CSV writer, dump manager or file-operation layer is needed.

### Best capture boundary

**`VectorizedXauUsdStrategy.process_native_stream` is the nearest existing DataFrame-returning boundary to the complete journal.** It observes every tick, calls `MarketState.step` in order, and already returns validated tick/candle frames under the dump decorator. `MarketState.step` is the best place to collect market events; `ExecutionReplay._event` is the nearest existing execution-event collector, but covers only execution and returns `None`, not a DataFrame. Decorating `_event` would dump `None` and would not solve the task.

Recommended return contract: extend `process_native_stream` to return `(tick_state_df, candle_state_df, journal_event_df)`, where `journal_event_df` is `pt.DataFrame[JournalEventSchema]`. Update its unpacking in `process_tick_data` and all direct callers/tests. The decorator then dumps tuple components `1`, `2`, `3` automatically. Retain the current manifest handoff and existing file operations; the event frame can remain diagnostic output without adding persistence categories. A later caller needing the event frame must retain it explicitly rather than expecting the manifest to contain it.

One tick can generate many journal rows, so a single `event`/`zone_id` scalar on the tick frame cannot represent the full sequence. Keep tick-wide state labels on the tick frame and ordered individual events in the third frame. Use one in-memory collector shared by market and execution paths, scoped to the existing broker/symbol `MarketState` lifetime. Assign event sequence at the transition, not after grouping by type; keep it across daily `process_native_stream` calls. Capture startup events before the first tick and transaction events when callbacks occur. Clear only the collected batch after frame assembly, not the sequence or strategy state.

### Event/rule groups and best Python methods

These rows cover every group in the event inventory above. Emit beside the transition/decision; do not reconstruct a full journal by comparing end-of-tick snapshots, which miss intermediate values, rejected attempts and multiple changes in one tick.

| Group and rule tags | Best existing Python location | Planned DataFrame evidence / missing emission |
| --- | --- | --- |
| Startup/input: `a-4`, `S1-HEDGING`, `b-21/b-22/TEST-HARNESS`, `MVP-SIMPLE`, `S1` | `__main__.main`, `normalize_mt5_zone_rows`, `ZoneCache.__init__`, first `MarketState.step`; native economics/configuration boundary | Runtime configuration and raw/daily load events; emit only checks actually performed. Offline Python has no attached-chart timeframe, EA deinit callback or automatic native hedging validation: mark such rows unsupported rather than fabricate validation success |
| Zone load/merge: `a-5/a-11`, `a-8/a-9` | `normalize_mt5_zone_rows`, daily preparation in `ZoneCache.__init__`, `MarketState._change_day` / `ExecutionReplay._change_day` | Typed daily zone table plus ordered merge/load records. Precomputed daily merges must be replayed into the collector at daily loading, not all emitted at cache construction as though every day loaded at startup |
| Candle/trend: `a-1/a-2/a-3`, `trend-1` | New-bar branch and strict Bid comparisons in `MarketState.step` | `CANDLE_CLASSIFIED`, `TREND_REFERENCE_UPDATED`, `TREND_STATE_CHANGED`; capture reference values and trend at each exact stage |
| Engagement/touch/gap: `b-3`, `trend-2/b-31`, `trend-2/b-1` | Bar-open engagement initialization in `MarketState.step`; engagement/cross/touch decisions in `MarketState._touches` | `ZONE_ENGAGED`, `ZONE_TOUCH_DIRECTION_CONFIRMED`, `MULTI_ZONE_TICK_GAP`; retain zone, direction and per-M15 slot outcome, including touches later blocked by usage/risk |
| Breakout: `b-3/b-4/trend-1` | `MarketState._breakouts` | `BREAKOUT_SIGNAL` with existing `candidate_id` as `breakout_id`, owning old broker day/bar and closing trend snapshot |
| Pullback cycle: `b-8/b-25`, `b-8` | `MarketState._age`, `_signal_pullbacks`, `_breakouts` for signals-only; `ExecutionReplay._open_cycle`, `_age_cycles`, `_pullbacks`, `_end_cycle` for replay | Creation, penetration latch, native-validity wait, expiry and parent lineage. Creation/penetration do not require a native order; placement requires accepted execution |
| Entry/risk: `b-1/b-11/b-29/b-30`, `TEST-HIGH-R/b-29/b-30`, `AR-RISK-01`, `MVP-RISK/TEST-HARNESS` | `ExecutionReplay._submit`, `_risk`, `_risk_used`, `_budget`, `_send`, `_new_cash_risk`; native overrides for recorded economics | Risk-model readiness, portfolio/margin prechecks, reversal request and accepted pending placement; capture computed values before guards/send and preserve actual outcome. Current generic event collector does not emit every successful diagnostic |
| Native fills/costs/closures: `b-20`, `b-20/b-23/b-26/b-29`, entry fill tags | Simulation: `ExecutionReplay._fill`, `_close`, `_event`; recorded native: `RecordedExecutionReplay.on_deal`, `_entry_deal`, `_exit_deal` | Fill/close and per-deal cost rows with actual native tickets when recorded. Do not emit a fill solely because `_send` accepted a request; retain opening and closing deal costs separately |
| Usage: `TEST-HIGH-R/b-24`, `TEST-HIGH-R/b-24/b-26`, `TEST-HIGH-R` | Usage guards in `ExecutionReplay._submit`; closing usage updates in `_close` / `RecordedExecutionReplay._exit_deal` | Blocked, consumed and remaining high-zone-slot events; distinguish attempt, fill count and closure consumption |
| Reversal invalidation: `b-3` | `ExecutionReplay._breakout`, `_close`; recorded `_close` plus subsequent native deal callback | `REVERSAL_EXIT_REQUESTED` and accepted-request confirmation, followed separately by actual `POSITION_CLOSED` |
| Profit protection: `b-29` | `ExecutionReplay._manage`, `_structure_stop`, `_accept_modification`, `_protection_valid`; recorded `_manage`/`_accept_modification` | R-stage, structural candidate, SL request/confirmation/retry; capture raw internal `R`/`P` type, tracked risk anchor and observed protection result |
| Daily limits/risk cancellation: `b-23`, `AR-RISK-01` | `ExecutionReplay._daily_guard`, `_enforce_pending_risk`, `_change_day`, `_cancel`, `_end_cycle` and native overrides | Daily-stop/would-trigger and cancellation decisions, including reasons and source day; absence in this sample does not remove these trace paths |
| Session: `AR-SESSION-01` | `ExecutionReplay._session`, `_session_positions`, `_session_pending`; `RecordedEconomics` session views and recorded replay overrides | Schedule/window/cutoff plus cancel/flatten lifecycle. Preserve native session information when available; assumption-based sessions must remain identified as simulated |

`ExecutionReplay._event` should append normalized execution records into the shared collector or feed a common typed event-construction helper. It cannot be the sole source: market events and successful risk/session diagnostics require explicit emissions at the methods above. Map event/rule tags centrally, with source-stage context; do not infer all rule tags from signal family alone.

### Zone IDs: existing parity and the correct change point

The active **`ZoneCache.__init__` already assigns `R1…Rn` before merging and concatenates IDs with `&`**, using the EA's low-only pairwise swap sort and strict `< 1.5` merge. `get_zones_for_day` returns copies retaining those IDs. No active-path ID renaming is needed.

For dumpable zone evidence, extract that daily preparation into a synchronous typed DataFrame-returning method, proposed `ZoneCache.prepare_daily_zones`, decorated with `@pandera_validate(dump_output=True)`. Return `broker_day`, `zone_id`, `zone_low`, `zone_high`, `priority` and constituent IDs; build cached `XauZone` objects from that result. Preserve the exact current ordering, especially equal-low inputs: replacing the EA-compatible pairwise swaps with a different stable or low/high sort can change IDs. Retain ordered intermediate merge records if comparing `ZONE_MERGED`, since the final merged table alone loses the old bounds and incremental lineage.

The separately exported `domain.xau_usd.zone.build_merged_zones` currently sorts by `(low, high)`, assigns day-prefixed **post-merge** IDs and drops constituent lineage. It is not used by `ZoneCache`; do not use it to generate this journal's zone tags. If consolidating consumers later, make it share the verified daily preparation rather than introducing a second tagging algorithm. Audit callers before changing its contract.

### Tick trend tags: expose labels without changing calculations

`MarketState.step` already applies the strict three-closed-bar Bid comparisons and persistent `XauTrend` state. Add `trend_state` mapped as `NONE → TREND_NONE`, `UP → TREND_UP`, `DOWN → TREND_DOWN` to the returned payload; retain numeric `trend` for existing consumers. Initialize the column in `_initialize_per_tick_temp_state` and declare it in `PerTickState` so the exact-column guard and Pandera validation agree.

For event parity, take separate labels at the transition: old-bar breakout uses trend **before** the new reference/current-tick update; the final tick row uses trend **after** the current tick update. `MarketState._breakouts` runs before daily reset/reference roll, which is the appropriate capture point. Emit reference-update events only at initialization/new bar, and state-change events only when trend actually changes. Do not derive every event's `trend_state` from the final tick label. No trend-algorithm modification is justified solely to add readable tags.

### Signal tags and IDs: separate identity, family and direction

Use one proposed pure label mapper at event/snapshot construction; update `ExecutionReplay.order_snapshot`, `position_snapshot`, `_event` and the new event-frame assembler. Also project labels from candidates produced by `MarketState._breakouts`, `_touches`, `_signal_pullbacks` and replay `_pullbacks` when assembling signal rows. Update the relevant typed snapshot/event contracts in `domain/schema.py`; do not replace numeric enum fields used by consumers.

| Context | Planned tag | Identity source |
| --- | --- | --- |
| Risk model direction only | `BUY` / `SELL` | Candidate direction; no family implied |
| Breakout signal/request/fill | `BO-B` / `BO-S` | `MarketState._breakouts` already produces `BO#{breakout_sequence:02d}` |
| Reversal signal/request/fill | `R-B` / `R-S` | Preserve existing internal candidate ID; MT5 has no separate reversal sequence column |
| Pullback signal/request/fill | `PB-B` / `PB-S` | Candidate `parent_breakout_id` and internal candidate ID; MT5 lineage refers to the originating `BO#nn` |
| Raw management/usage type | `R` / `P` (or `B` for direct breakout) | `trace.trade_type` already maps family to these internal types and preserves recorded native type |

`R` explicitly means **reversal trade family** here; `P` means **pullback trade family**. `BUY/SELL` are direction labels, not competing signal families. Keep `signal_type` and `trade_type` distinct so family/direction survives even on rows where the EA prints only the raw type.

Expose `breakout_id` only where the EA supplies it; `parent_breakout_id` is a copied reference, not a new ID. Direct-breakout execution metadata can carry the originating breakout as parent too; preserve the EA call's context rather than blanket-filling every column. Keep existing internal `candidate_id`/`request_id` in extra columns instead of renaming them to EA IDs. Add owning `broker_day`, `signal_bar_time` and `source_time` to disambiguate repeated daily IDs and midnight logging. Exact `E1…` correspondence requires the same initialization, attempted journal calls, filtering and callback sequence; a Python-local event sequence provides order but must not be advertised as equal merely because it starts at 1.

### Planned schemas, assembly and checks

- `JournalEventSchema`: the 25 MT5 columns, plus owning `broker_day`, `bar_time`, `source_kind` (`market`, `simulation`, `native_callback`), within-stream event ordinal and Python logical IDs. Use nullable exact native ticket types or strings; unknown native IDs stay unavailable, never copied from synthetic IDs. Define explicit blank/zero/`N/A` conversion only for an MT5 presentation projection.
- Tick state: add `trend_state`; retain existing signal collections and numeric fields. Event rows hold individual zone/signal tags; no scalar field should overwrite multiple same-tick signals.
- Zone preparation: add a dedicated schema for final daily zones, and typed intermediate merge records where needed. Keep day separate from the MT5 zone tag.
- Assemble the event frame in `process_native_stream` after collecting events in execution order; validate even an empty frame with fixed columns/dtypes. Returning a frame containing dictionaries/dataclasses is insufficient if they cannot serialize: use scalar columns in the event frame, inspect dump warnings and verify its descriptor references a real Parquet payload.
- Extend `process_tick_data` unpacking, `_initialize_per_tick_temp_state`, `PerTickState`, relevant `TypedDict` contracts and direct call sites/tests together. Do not edit legacy vector helpers to obtain active-stream evidence.
- Test exact daily tags/merged lineage with equal-low inputs and gaps at/below 1.5; trend equality/persistence/reference-roll timing; all direction/family/raw-type labels; multiple events per tick and midnight ownership; accepted send versus actual native fill; event ordering/sequence across daily batches; and rejection of malformed frame schemas. Use short deterministic fixtures and the same intentionally short comparison period.

Acceptance: decorated target methods return validated, serializable DataFrames with the same zone/breakout lineage and context-sensitive labels as the EA. Comparing these traces can then reveal calculation/transition differences. It does not supply missing native callbacks, certify native economics, or require a longer run.

Sources: [active zone cache](../../../src/application/xauusd_trading_strategy_1_vector/zone_cache.py), [zone row normalization](../../../src/application/xauusd_trading_strategy_1_vector/zone_loader.py), [separate zone helper](../../../src/domain/xau_usd/zone.py), [market methods](../../../src/application/xauusd_trading_strategy_1_vector/market.py), [replay methods](../../../src/application/xauusd_trading_strategy_1_vector/replay.py), [recorded callbacks](../../../src/application/xauusd_trading_strategy_1_vector/native_replay.py), [typed state/event contracts](../../../src/application/xauusd_trading_strategy_1_vector/domain/schema.py), [existing raw trade-type mapping](../../../src/application/xauusd_trading_strategy_1_vector/trace.py).

## Column glossary

| Column | Meaning |
| --- | --- |
| `event_id` | EA-local sequence `E1`, `E2`, …; one ID per journal call, including filtered calls |
| `server_time` | Broker/server logging timestamp with milliseconds; not necessarily signal bar time |
| `ea_version` | Writer's version label, here `2.10-ROBUST-FINAL`; not a binary hash |
| `symbol` | Exact broker symbol, here `XAUUSD!` |
| `broker_server` | Account server, here `Opogroup-Server1` |
| `sl_tp_model` | Configured model label, here `MVP_SIMPLE_EXPLICIT_ROBUST` |
| `rule_id` | Slash-separated source rule/QA identifiers associated with the event; not trade IDs |
| `event` | Lifecycle or diagnostic event name; use this to interpret the numeric fields |
| `zone_id` | Daily zone tag or merged lineage, e.g. `R8&R9`; blank for events without a zone |
| `trend_state` | Global trend at logging time; closed-bar breakout processing temporarily uses the closing trend snapshot |
| `signal_type` | Direction, signal family plus direction, or raw tracked trade type; see below |
| `entry_type` | Context: `Market`, `Stop`, `Close`, `ModifySL`, `Telemetry`, `PostFill`, or blank |
| `breakout_id` | ID of a newly reported breakout, e.g. `BO#01` |
| `parent_breakout_id` | Existing breakout ID carried by its descendant request/cycle/trade; not another counter |
| `requested_price` | Intended entry/decision price on trading rows; overloaded on diagnostics |
| `fill_price` | Actual deal price on fill/cost/closure rows; overloaded on diagnostics |
| `sl` | Stop-loss price on trading rows; overloaded on diagnostics |
| `tp` | Take-profit price on trading rows; overloaded on diagnostics |
| `order_ticket` | Native order ID: a request/pending-order lifecycle; one order may generate multiple deals |
| `deal_ticket` | Native execution-deal ID, including opening/closing deals and their costs |
| `position_ticket` | Native selected/tracked position ticket; distinguish it from `DEAL_POSITION_ID`/position identifier used internally for lineage |
| `gap_below` | Current daily zone's low minus the preceding lower zone's high |
| `gap_above` | Next higher zone's low minus the current daily zone's high |
| `nearest_gap` | Minimum available nonnegative adjacent gap; the only available gap at an outer edge |
| `reason_error` | Event-specific explanation, values, stages or failure reason; populated on successful events too |

Blank IDs mean no applicable identity supplied; ticket `0` means no ticket supplied, not an actual native ticket. Numeric `0.00` may be a placeholder. `N/A` gaps mean no matching zone or no neighbor; they are not zero distance. Gaps are XAUUSD **price distances**, not cash PnL, points or pips. The writer looks up gaps in the current `g_zones` by exact ID at logging time: merged-zone diagnostics during construction or old-day carried-position events can lack valid historical gap context.

### Numeric diagnostic overloads

| Event | `requested_price` | `fill_price` | `sl` | `tp` |
| --- | --- | --- | --- | --- |
| `CANDLE_CLASSIFIED` | Open | Close | Low | High |
| `TREND_REFERENCE_UPDATED` | Reference low | Reference high | 0 | 0 |
| `TREND_STATE_CHANGED` | Triggering Bid | 0 | Reference low | Reference high |
| `ZONE_MERGED` | Previous low | Previous high | Merged low | Merged high |
| `VOLUME_SET` | Test lot volume | Native PnL for a $1 price move | 0 | 0 |
| `MULTI_ZONE_TICK_GAP` | Previous Bid | Current Bid | 0 | 0 |

Never treat every nonzero `sl`/`tp` as an order protection level. Source: EA `WriteJournal` lines 454–489, `GetZoneGapContext` 365–390, candle/trend code 1271–1309 and each event's call site.

## Zones, trends and signal labels

### Daily zone tags and merging

`LoadZonesForDay` selects that broker day's raw rows, sorts by ascending lower boundary, and assigns **pre-merge** tags `R1`, `R2`, … . `MergeZones` merges the next interval if `next.low − merged.high < 1.5`, including overlaps; equality at 1.5 does not merge. Bounds become the minimum low and maximum high, any high-priority constituent makes the merged zone high priority, and constituent tags join with `&`. It does not renumber after merging.

Thus `R8&R9` is **one zone formed from two input zones**, not two simultaneous signals or positions. A chain can become `R8&R9&R10`. `R` in a zone tag denotes the range tag and is separate from reversal `R` in `signal_type`. Source: EA `SortZones`, `MergeZones`, `LoadZonesForDay`, lines 1107–1157 and 1221–1253.

### Trend calculation and timing

- Reference high = `max(High[1], High[2], High[3])`; reference low = `min(Low[1], Low[2], Low[3])`, using the three most recent **closed M15 candles**.
- Each tick: `Bid > reference_high` sets `TREND_UP`; `Bid < reference_low` sets `TREND_DOWN`; equality or Bid inside the reference interval preserves the previous trend. It does not return to `TREND_NONE` inside the interval.
- `TREND_NONE` is the initial state until a strict reference break. Rolling references and daily zone loading do not reset trend.
- At a new bar, existing pullback cycles age, the old bar is evaluated with its stored trend snapshot, the broker day changes if needed, references roll, then engagement resets from the new bar's open. Breakouts require engagement, matching trend and a close beyond the configured buffer. Candle classification is simply close above/below/equal open.
- Directional reversal touch: in uptrend, previous Bid below zone low and current Bid at/above low yields a sell reversal attempt; in downtrend, previous Bid above zone high and current Bid at/below high yields a buy reversal attempt. A tick spanning multiple whole zones suppresses these reversal touches rather than inventing an intratick path.

Source: EA `UpdateTrendReference`/`UpdateTrendState` 1282–1309, `ProcessDirectionalReversalTouches` 2459–2482, `ProcessClosedBar` 2812–2846 and `ProcessNewBar` 3276–3297.

### `signal_type` and `entry_type`

| Label | Meaning |
| --- | --- |
| `BUY`, `SELL` | Direction only on risk-model calculation rows; does not identify a signal family or prove an order |
| `BO-B`, `BO-S` | Buy/sell breakout; a qualifying closed-bar signal, optionally direct market execution if enabled |
| `R-B`, `R-S` | Buy/sell reversal, normally a market-entry attempt against the directional zone touch |
| `PB-B`, `PB-S` | Buy/sell pullback: a breakout-derived cycle, penetration latch and exact broken-zone-edge stop entry |
| `R` | Raw internal reversal trade type on usage/protection rows; omits direction |
| `P` | Raw internal pullback trade type on protection rows; omits direction |

**`PS-B` and `PS-S` do not occur in this CSV or the current label mapper. The labels here are `PB-B` and `PB-S`.** Internal type `B` maps to breakout; internal type `P` maps to pullback. In risk notes, `R0`/`1R` instead mean initial risk distance and its multiples, not reversal. `P` does not mean profit.

`Close` marks a breakout decision from a closed candle, not automatically a position closure. `Stop` means a pending buy-stop/sell-stop entry, not stop-loss. `ModifySL` means position protection modification. `Telemetry` and `PostFill` are diagnostic contexts. Blank means the call supplied no entry context. Source: EA `SignalLabelByType`/`OrderKindByType`, lines 1517–1528; pending placement 2642–2664; management 3025–3038.

## Counter resets and identity

| Identity/state | Daily reset? | Correct interpretation |
| --- | --- | --- |
| `zone_id` | Yes: rebuild and tag from `R1` for each day's input | Composite key is owning broker day + zone lineage; the same tag tomorrow can describe different prices |
| `breakout_id` | Yes: sequence resets to zero; next ID is `BO#01` | Use owning broker day + breakout ID; signal may be logged at next-bar/midnight processing |
| `parent_breakout_id` | No independent counter | Copies the originating breakout ID; preserve its originating day through descendants |
| `event_id` | No daily reset | Global EA-instance sequence; initialization/restart can restart numbering; filtering can leave gaps |
| Native order/deal/position tickets | No EA daily counter reset | Assigned by MT5/server/tester; treat as native identities within the recorded run |
| Zone usage/fill counts | Yes, when daily zones are rebuilt | Distinct reversal/pullback counters; repeated signals do not necessarily consume a zone |
| Daily PnL/gross loss/daily-stop state | Yes at broker day change | Account balance and tracked surviving positions do not thereby reset |
| Trend | No | Preserves previous direction until a strict opposite reference break |

Day change cancels old daily pullback cycles and reloads zones. Do not infer that it closes every position: this run separately uses `ALL_FLAT` session safety. Sources: EA globals 253–260, `NextEventId` 358–362, `NextBreakoutId` 2485–2489, `LoadZonesForDay` and `HandleDayChange` 3257–3274.

## Event groups and every observed event

Counts are from this CSV; absent events are not evidence that their code paths do not exist.

| Group | Event (count) | Meaning |
| --- | --- | --- |
| Startup/input | `TF_VALIDATED` (1) | M15 requirement accepted |
| Startup/input | `ACCOUNT_MODE_VALIDATED` (1) | Hedging account accepted |
| Startup/input | `VOLUME_SET` (1) | Lot size and native $1-move economics validated |
| Startup/input | `ZONES_LOADED` (5) | Raw-file load or daily final-zone load; distinguish via note |
| Startup/input | `EA_INITIALIZED` (1) | Runtime profile/input summary |
| Startup/input | `EA_DEINITIALIZED` (1) | EA termination with reason code |
| Zones | `ZONE_MERGED` (13) | Adjacent/overlapping raw ranges combined |
| Zones | `ZONE_ENGAGED` (252) | Bar opens inside or tick enters/crosses zone; sets directional engagement |
| Zones | `ZONE_TOUCH_DIRECTION_CONFIRMED` (132) | First eligible directional touch for zone/direction/M15; not necessarily an executable trade |
| Market/trend | `CANDLE_CLASSIFIED` (276) | Closed candle classified by close versus open |
| Market/trend | `TREND_REFERENCE_UPDATED` (277) | Three-closed-bar reference recomputed |
| Market/trend | `TREND_STATE_CHANGED` (45) | Strict Bid break changed persistent trend |
| Market/trend | `MULTI_ZONE_TICK_GAP` (1) | Tick spans multiple zones; no synthetic path/signals |
| Signal/cycle | `REVERSAL_SIGNAL` (19) | Executable reversal request prepared after eligibility/risk checks |
| Signal/cycle | `BREAKOUT_SIGNAL` (44) | Buffered engaged-zone close confirms breakout lineage |
| Signal/cycle | `PULLBACK_CYCLE_CREATED` (19) | Breakout spawned a valid t+1…t+5 pullback window |
| Signal/cycle | `PULLBACK_PENETRATION_LATCHED` (14) | Required retracement into broken zone observed; latch retained |
| Signal/cycle | `PENDING_WAITING_NATIVE_VALIDITY` (5) | Exact rule price currently invalid versus market/native stop distance; wait |
| Signal/cycle | `PENDING_PLACED` (14) | Native stop order successfully placed |
| Signal/cycle | `PENDING_EXPIRED` (5) | Cycle expired and any associated pending order ended |
| Usage | `ZONE_USAGE_BLOCKED` (97) | Reversal quota/usage prevents another entry |
| Usage | `ZONE_CONSUMED` (15) | Reversal usage exhausted after closure |
| Usage | `HIGH_REVERSAL_SLOT_CLOSED` (4) | High-zone reversal closed while another permitted slot remains |
| Risk/economics | `RISK_MODEL_READY` (33) | Entry SL/TP/R0/target prepared; includes high-zone variant |
| Risk/economics | `PORTFOLIO_RISK_PRECHECK` (33) | Prospective request checked against portfolio budget |
| Risk/economics | `PORTFOLIO_RISK_POST_FILL` (33) | Risk re-evaluated against actual native fill/state |
| Risk/economics | `MARGIN_PRECHECK` (33) | Requested-price margin diagnostic |
| Risk/economics | `MARGIN_POST_FILL` (33) | Account margin diagnostic after fill |
| Risk/economics | `DEAL_COSTS_RECORDED` (66) | Deal commission/swap/fee/profit recorded; opening and closing deals |
| Execution | `ORDER_FILLED` (33) | Native deal callback registered an entry |
| Execution | `POSITION_CLOSED` (33) | Native closure registered and realized results/usage updated |
| Execution | `REVERSAL_EXIT_REQUESTED` (1) | Opposite breakout requested reversal close |
| Execution | `REVERSAL_EXIT_CONFIRMED` (1) | Close request accepted in invalidation path; reconcile subsequent native closure |
| Protection | `R_STAGE_CHANGED` (37) | Profit threshold reached: 1R risk-zero, 1.5R lock +0.5R, 2R structural trailing |
| Protection | `SL_MOVE_REQUESTED` (35) | Improved stop submitted |
| Protection | `SL_MOVE_CONFIRMED` (35) | Stop modification accepted/read back as confirmed by management path |
| Protection | `SL_MOVE_RETRY` (1) | Native validity/freeze or response prevented desired stop; retry later |
| Protection | `STRUCTURE_TRAIL_CANDIDATE` (276) | Confirmed higher-low/lower-high pivot considered; does not itself prove an SL move |
| Session | `SESSION_SCHEDULE` (5) | Native symbol trade-session schedule recorded |
| Session | `SESSION_WINDOW_ACTIVE` (3) | Current native session window became active |
| Session | `SESSION_PRE_CLOSE_CUTOFF_ENTERED` (3) | Preclose cutoff entered for configured session handling |

Typical chain: breakout → cycle → penetration → pending placement → native fill → protection → closure. Reversal chain: touch → eligibility/risk → reversal signal → native fill → protection/possible breakout invalidation → closure. Risk/margin rows are telemetry around those chains. A touch can be blocked; a breakout can have no child cycle; a cycle can expire without filling.

## Rule and QA identifiers used here

The journal stores composite identifiers, not the full rule text. The following meanings are derived from current tagged call sites; they do not replace confirmed specification documents.

| Identifier/family | Brief meaning in this writer |
| --- | --- |
| `a-1/a-2/a-3` | Bullish, bearish and doji candle classification |
| `a-4` | M15 timeframe constraint |
| `a-5`, `a-11` | Zone-file validation/loading and daily valid-zone availability |
| `a-8/a-9` | Merge zones under the strict 1.5 price-gap threshold and retain constituent lineage |
| `trend-1` | Three-closed-M15 reference, persistent trend and breakout trend snapshot |
| `trend-2` | Directional first-touch and multi-zone tick-gap handling |
| `b-1` | Reversal entry/touch execution path; also fill tagging |
| `b-3` | Directional zone engagement and opposite-breakout reversal invalidation |
| `b-4` | Buffered close breakout confirmation |
| `b-8` | Pullback cycle, penetration, window lifetime and exact-price pending entry |
| `b-11` | Native entry/fill execution tagging |
| `b-20` | Deal costs and realized accounting |
| `b-21/b-22` | Volume and native cash-per-price-move validation |
| `b-23` | Daily loss/cancellation context and realized closure accounting |
| `b-24` | Reversal zone usage limits, including high-zone quota |
| `b-25` | Pullback cycle lineage/eligibility; pullback does not consume reversal usage |
| `b-26` | Reversal closure and consumed/remaining usage state |
| `b-29` | R-based stop/profit protection and structural trailing |
| `b-30` | Initial risk/target availability and entry SL/TP construction |
| `b-31` | One reversal signal slot per M15/zone/direction |
| `S1-HEDGING` | Required native hedging account mode |
| `S1` | Strategy lifecycle/deinitialization tag |
| `TEST-HARNESS` | Tester economics/configuration diagnostics |
| `TEST-HIGH-R` | High-priority reversal quota and SL-multiplier variant |
| `MVP-RISK` | Native margin diagnostic wrapper |
| `MVP-SIMPLE` | Selected runtime strategy profile/configuration summary |
| `AR-SESSION-01` | Session schedule, cutoff, cancellation/flattening family |
| `AR-RISK-01` | Portfolio-risk budget and reservation accounting family |

For the ordinary initial-risk model: buy SL is `max(lower_neighbor.high, entry − R_CAP)`; sell SL is `min(upper_neighbor.low, entry + R_CAP)`; `R0 = abs(entry − SL)`. Select the first farther zone with target distance at least `target_multiplier × R0`, using its near edge. Missing stop neighbor, nonpositive R0 or missing target rejects the entry. High-zone reversals use a separate SL-multiplier calculation; inspect their `RISK_MODEL_READY` notes and match `high_reversal_sl_multiplier`, rather than applying the ordinary formula universally. Profit-protection R is anchored to the tracked initial risk, not recomputed from every moved stop.

## Source navigation and validation

The [EA source](../Experts/XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5) is the definition behind the tables. Locate function/event names with `rg -n`; line numbers above describe the inspected source and can drift. Main sections: journal/gaps 365–489; zones 1107–1253; trend 1282–1309; initial risk 1376–1460; labels 1517–1528; high-zone risk 2229–2328; reversal 2356–2482; pullback 2485–2719; breakout 2812–2846; protection 2887–3069; deal/closure 3078–3250; daily/new-bar lifecycle 3257–3297.

Validated the document's observed event inventory/counts and all 25 column names against the CSV, and reviewed definitions against current source. No Python strategy, MT5 tester or native replay was run to create this guide; native parity remains unverified.
