# Scenarios: on_tick.py Validation with Random CSV

## Data Generation

Random market data generator parameters:
- Bar count: 50 M15 bars
- Price range: realistic XAUUSD range
- Volume: random per bar
- Edge cases injected: zero volume, doji (O=H=L=C), monotonic trend
- Timestamps: consecutive M15 intervals from a start date

## Scenario 1: Normal Tick Processing

- Setup: Load market data. Settings with event loop enabled, probe emission enabled. Mock event loop returns success for processing.
- Action: For each bar, construct tick and call `on_tick()`.
- Expected: Handled on all bars, probe emitted on ticks 1-5, no event loop failure.

## Scenario 2: Probe Emit Limit

- Setup: Same as Scenario 1, verify probe count precisely.
- Expected: Probe count reaches exactly 5. Emitted on ticks 1-5 only.

## Scenario 3: Event Loop Disabled

- Setup: Event loop disabled in settings, probe emission enabled.
- Expected: Handled on all bars, probe fires for first 5 ticks, event loop never invoked, no failure.

## Scenario 4: Event Loop Absent

- Setup: Event loop enabled in settings but no event loop provided.
- Expected: Not handled, event loop failure reported on first call. Second call returns same with failure flag set (no double reporting).

## Scenario 5: Event Loop Exception

- Setup: Mock event loop raises exception on tick 25. Other calls return success.
- Expected: Tick 25 not handled, failure reported. Other ticks handled. Failure flag set after tick 25. Processing continues.

## Scenario 6: Invalid Ticks (NaN/Zero Prices)

- Setup: Bars with NaN/zero bid/ask from data. Event loop enabled.
- Expected: Invalid ticks not processed for probe. Event loop still called for invalid ticks. Results returned without exception. Probe count remains 0 if all ticks invalid.

## Scenario 7: Full Integration Loop

- Setup: Full data iteration.
- Expected: Full iteration completes. All results consistent. No state corruption across bars.

## Scenario 8: Alias Verification

- Setup: Call alias function instead of primary entry point.
- Expected: Identical behavior to primary entry point.
