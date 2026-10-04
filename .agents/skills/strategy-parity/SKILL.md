---
name: strategy-parity
description: Use when changing market state, risk, callbacks, recording or native contracts, or when asked whether Python matches the MT5 reference. Separates evidence classes and never overstates parity.
---

# Strategy parity

The reference definition is the MT5 EA
`mt5/MQL5/Experts/XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5` with its envelope
`mt5/MQL5/Experts/XauRobustLiveEnvelope.mqh`. See
[docs/todo/MT5-Python.Divergence.md](../../../docs/todo/MT5-Python.Divergence.md)
for open gaps and [docs/State-Variables.Glossary.md](../../../docs/State-Variables.Glossary.md)
for the 143 declared state variables.

## Evidence classes

Never let these be conflated, in a report or in automation:

| Class | Produced by | Proves |
|---|---|---|
| Offline regression | `dev.py test --tier parity` | Python behaves as specified for its fixtures |
| Recorded comparison | `recorded_runner` **with** `--expected` | Python matches a recorded native run for those inputs |
| MQ5 compile | MetaEditor, Windows | the native source builds |
| Native runtime parity | Strategy Tester | the native run reproduces |

Replay without `--expected` is **not** a comparison. `compared=false` never
establishes parity. A green offline suite is not native parity.

## Workflow

1. **State the invariant.** Which causal rule, ordering or state lifetime must
   hold? Write it down before touching code.
2. **Run the regression scope.** `dev.py test --tier parity` plus any affected
   `unit` module.
3. **Compare in order.** Native callbacks are chronological; never join by
   `event_id`, native ticket or a Python-generated request id. Establish the
   logical trade mapping at placement/fill and follow it through closure.
   Repeated snapshot entries are not new trades.
4. **Record the first difference**, not a summary verdict: field, expected,
   actual, and the inputs that reproduce it. `trace.first_difference` exists for
   this.
5. **Record identity** whenever claiming native proof: source SHA-256, matching
   envelope, build settings, input `ranges.csv`, and the recording consumed.

## Causality requirements

Preserve causal closed-candle windows, chronological callback order, cross-day
state, duplicate-tick identity and stream isolation. Current-candle extrema
must never enter their own reference. Missing bars are not replayed. Simulated
settlement ordering in the Python replay is an **assumption**, not proven native
callback ordering; do not upgrade it in a report.

## Native proof limits

No MQ5 compile has been run in this checkout, and no Strategy Tester run has
been performed. Until both exist with recorded identity, the strongest available
claim is "recorded comparison for the supplied inputs". Do not describe the
`LIVE_RC` filename as deployment approval; live enablement is always a Project
Leader decision.