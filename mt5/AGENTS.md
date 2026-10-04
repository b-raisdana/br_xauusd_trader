# AGENTS.md - mt5/

Delta to the root contract. Read the root `AGENTS.md` and
[mt5/README.md](README.md) first.

## Source identity

- Reference EA: `MQL5/Experts/XAUUSD_ROBUST_FINAL_LIVE_RCv2.mq5`, property
  version `2.20`.
- Envelope: `MQL5/Experts/XauRobustLiveEnvelope.mqh`. It defines the remaining
  platform event handlers and the release/account guards.
- Current source SHA-256:
  `b8bbf960e443c2fa8f2acab297b63d36f5a88473add5caf78eb403536f9ac923`.

`MQL5/Experts/*` and `MQL5/Files/*` are **intentionally Git-tracked**; nested
subdirectories are ignored. The `LIVE_RC` filename is not deployment approval.

## Build and evidence boundary

- **No MQ5 compile has been run in this checkout, and no Strategy Tester run has
  been performed.** Source presence is not compile evidence, and compile
  evidence is not parity evidence.
- Any native proof must identify the source file, its matching envelope, the
  build settings and the input `ranges.csv` **together**. Partial identity is
  not proof.
- MetaEditor and the terminal are Windows-only. `MetaTrader5` is declared with a
  `sys_platform == 'win32'` marker and is never installed on a Linux runner.
  Offline CI cannot produce native evidence; do not let it imply otherwise.

## Inputs

- `InpRangesFile="ranges.csv"`; broker dates `YYYY.MM.DD`; priorities
  normal/high. Only `false`, `0`, `no`, `off` (case-insensitive, trimmed) disable
  a row.
- Tester I/O uses `FILE_COMMON`; chart I/O uses terminal-local `MQL5/Files`.
- Assignment values in the source outrank adjacent comments describing earlier
  scenarios. Read the assignment, not the comment.

## Execution gates

Compile and tester runs are separate capabilities from Python broker
automation. The Strategy Tester cannot execute the Python strategy directly.

Live enablement is always a Project Leader decision. No source change, filename
or passing test authorizes real-money trading.

## Documented limits

`EndCycle` deactivates without checking deletion success. The deal callback
filters Magic but not explicitly symbol, and assumes a non-partial
full-position lifecycle for realized accounting. Initialization journal text
still says `2.10` despite property `2.20`. These are recorded observations, not
fixed defects, and must not be silently "corrected" in the reference.