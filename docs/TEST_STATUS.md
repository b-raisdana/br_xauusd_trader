# Test and Verification Status

## Pre-commit setup (2026-09-15)

- `br_pre_commit` matches fetched `origin/main` at `5e07919592792a0c8a5c5f19f4e36640df994ec8`.
- Reinstall with `powershell -ExecutionPolicy Bypass -File scripts/setup_pre_commit.ps1`; uses the active Python environment. Local Git settings ignore NTFS executable-bit differences; upstream shell launchers are normalized to LF without changing the submodule commit.
- Staged `pre-commit run` and the installed shared wrapper pass Ruff, formatting and pytest. Current Windows pytest: 85 passed (one upstream Protobuf deprecation warning); earlier test counts below are historical.
- Existing staged work relocates MQL files to `mt5/`, removes obsolete tests and TODO documents, and adds configuration and an MT5 initialization helper. This tooling check does not establish fresh MQL compile or trading parity evidence.

این فایل فقط وضعیت Evidence قابل بازتولید در Repository فعلی را نشان می‌دهد. گزارش تاریخی بدون Artifact/Command/Commit، PASS جاری محسوب نمی‌شود.

## وضعیت فعلی Gateها

| Gate | Scope | وضعیت فعلی | Evidence / Blocker |
|---|---|---|---|
| Migration integrity | Rule/Decision/Experiment separation | PASS | Template/Handoff Merge شد؛ Legacy از Active Rules جدا و تصمیم‌های نهایی Leader ثبت شد. |
| Package structure smoke | Required root, Source-of-Truth files and canonical ranges | PASS | Canonical SHA-256 and required structure remain covered by pytest. |
| Current-code quality | Ruff, format, mypy, pytest, diff check | PASS with unrelated format debt | 2026-09-13: Ruff check PASS, mypy 65 files PASS, pytest 224 PASS, diff check PASS; repository-wide Ruff format remains blocked by 28 pre-existing mirrored skill Markdown files, while all changed files pass the format hook. |
| Legacy static integrity | Historical sources/manifests without promotion | PASS | Python AST 9/9; PowerShell parser 12/12; MQL5 strict + balanced braces 3/3; Git-staged core manifest 16/16 across byte-preserved attributes. Not compile/runtime evidence. |
| Zone/Trend/orchestration slice | Rule → causal ticks → bar close → deterministic tests | PASS | 21 focused tests; strict tick-chain/final-close validation and Breakout-before-Trend-roll PASS; 23 canonical days → 421 merged Zones; 444/444 source rows retained. |
| Breakout/Reversal signal slice | Strict qualification, touch and accounting contracts | PASS | 9 focused/integration tests; strict buffer/lineage, same-Tick Trend, directional Market touch, gap/wick, duplicate, daily usage and shared bar slot PASS. |
| Pullback signal slice | Conservative entry lifecycle and accounting | PASS | 7 focused/integration tests; penetration/edge retry, five-bar window, Breakout lineage, shared Reversal/Pullback bar slot, rollover cancellation, Multiple PB and Normal1/High∞ PASS. |
| Momentum/TP slice | Strict trend, target trigger, conflict and extension lifecycle | PASS | 5 focused tests; Same-Bar/closed/current checks, crossing/gap, touch block, safe one-step modify, restore and Market Close PASS. |
| Initial Risk/Execution slice | Geometry, native RF, protection and fixed capital profiles | PASS | 7 focused tests; Free Space, Stop/Target, RF, monotonic steps, protected order, 0.01 lot, max3/max5 and margin boundary PASS. |
| Financial Safety slice | Daily net-realized and GROSS15 entry gates | PASS | 6 focused tests; daily latch/reset/actions, inclusive gross budget, all four native risk components, combined rejection and invalid-input failure PASS. |
| Operational Safety slice | Broker session boundary and restart lock | PASS | 4 focused tests; inclusive pre-close action set, time-basis validation, persisted same-day detection and next-day release PASS. |
| Audit payload slice | Immutable trace records, durable JSONL and leader marker DTOs | PASS | 23 focused/integration tests; typed/atomic recovery and linked ORDER/FILL/REJECT/CLOSE/MODIFY/CANCEL projection PASS. Reject preserves protection/Pending state and accepted Modify cannot loosen SL. |
| Equivalence-vector scaffold | Shared versioned Decimal-string inputs/outputs | PASS for Python + MQL runtime | 19 vectors execute in Python, including lifecycle transition/protection validity and causal Trend-before-Reversal Tick order; generated-header drift and MQL runtime PASS. |
| Rule traceability | Rule name → code → test → journal | PASS through bounded MQL Native lifecycle/protection/session management | MQL signal event loop ran one real-tick day; candidate→risk/safety/audit/send/binding/outcome, Deal-history risk, RF protection, TP extension/restore, restart and final flatten passed with exact project filters. |
| Current MQL real-tick signal parity | 2026-08-28, 541,333 native Ticks, 88 M15 bars, canonical Zones, UTC+00 | PASS | Python=MQL counts: Breakout 28, Reversal 62, Pullback 410,904; MQL completion `failed=0`. Candidate-only evidence; no outcome, cost or PnL claim. |
| MT5 Tester profile 200 | 2026-08-28, real ticks, 0.01 lot, max3 | PASS | 10/8/2، 3 Breakout accepted، net -12.27، zero unknown reject/failure/exposure. |
| MT5 Tester profile 300 | 2026-08-28, real ticks, 0.01 lot, max5 | PASS | 17/15/2، 5 Breakout accepted، net -5.47، zero unknown reject/failure/exposure. |
| Contract tests | همه موارد بخش 3 `TODO.md` | PASS at Python domain boundary | All listed fast contracts PASS; external Native/MT5 parity and durable side effects remain separate gates. |
| MT5 tick acquisition | Read-only UTC raw input, ignored cache | PASS for bounded smoke | Bridge 5.0.6180 exported 6,487 ticks/290,594 bytes; explicit-offset normalization replayed all rows as one M15 bar. An ordered five-tick probe uniquely correlated local server time to UTC; no cache, probe values, resolved Broker-specific offset or account identity are committed. |
| Targeted regression | Active MVP Rules | PASS for required scope | Bootstrap and both Zone priorities are fixed Rules; FreeSpace `<=3 Block / >3 Allow`، Strict/TP/Safety deterministic tests PASS. Sticky/priority-PnL/external-fixture comparisons are not MVP gates; FreeSpace15 is Post-MVP. |
| Python ↔ MT5 equivalence | Frozen core vectors | PASS for MVP scope | Shared vectors PASS at `1e-9`; causal signal counts match on 541,333 ticks and project-owned Native lifecycle passes both capital profiles. Multi-day Native parity is not an MVP gate because no independent Python Native fixture exists. |
| MT5 compile/runtime smoke | `#property strict`, zero errors, inert startup | PASS for current inert core + State/Execution/Native/Audit boundaries | Build 6151: 0 errors/0 warnings; Strategy Tester validated 19 vectors, causal/daily/Pullback/TP state, Daily/GROSS15/Concurrency/Margin/Operational safety, synthetic execution, Native adapters and audit payload. |
| MT5 real-tick acceptance | 200/300 USD scenarios | PASS for bounded technical run | Versioned local-only INI profiles and restart profile pass on 2026-08-28 with real ticks, live/remote/cloud disabled; broader regression remains. |
| MT5 multi-day lifecycle | 23 Zone days, capital 200, real ticks | PASS final MVP | 308/244/64؛ 109 Breakout accepted، 14 conflict closes، max2، cancel/session-close 2/3، TP 8/2/2؛ zero unknown reject, SL-loosen, exposure or failure. |
| Signal priority attribution | Same 23-day MQL run | PASS informational | Reversal Normal 86/86/0 and High 26/26/0; Pullback Normal 146/56/90 and High 44/20/24. Per-priority PnL is intentionally not an MVP acceptance criterion. |
| QA day 2026-07-29 | Real-tick technical ledger summary | PASS technical | 17/15/2، 7 Breakout accepted، net +67.87 and zero failure. |
| Final reusable report | Structured evidence + comprehensive Markdown | PASS Stage 7 | Canonical JSON/report include hashes, profile counters, Symbol spec, TP and restart evidence; summaries must reuse them without rerunning MT5. |
| MVP Freeze | Rulebook/Code/Evidence immutable version | PASS | Version manifest and immutable Git tag identify the accepted research/tester-only MVP. |
| Shadow/Demo | Broker acceptance | NOT_RUN | پس از MVP Freeze. |
| Limited Live | Explicit Leader approval | BLOCKED | شواهد و Risk approval موجود نیست. |
| Historical bundle core manifest | `SHA256_KIT.txt` | PASS | هر 16 ورودی Manifest با فایل استخراج‌شده Match شد. |
| Historical patch manifest | `SHA256_PATCH.txt` | FAIL | `README_FA.md` mismatch و دو مسیر `reversal_portfolio_reference/*` در Bundle موجود نیستند؛ Evidence دست‌کاری نشد. |
| Canonical ranges identity | uploaded/data/reference copies | PASS | SHA-256 هر سه نسخه یکسان است. |

## Coverage الزامی Rules

| گروه Rule | تست‌های اجباری | وضعیت |
|---|---|---|
| Zone | Load/Normalize/Sort، line Zone، chain merge `<1.5`، Priority، no hard cap | PASS |
| Trend | Day bootstrap، live threshold، no prior-day carry، Tick event order | PASS |
| Breakout | Engage، Trend at Close، strict ±1 buffer، lineage، close opposite Reversal | NOT_RUN — Engage/validation/lineage, opposite-direction closure instruction and generic protected Close lifecycle PASS; Breakout-to-position wiring remains. |
| Reversal | directional Market touch، wick validity، Normal1/High2، duplicate guard | PASS |
| Pullback | penetration 0.20، broken-edge entry/retry، t+1..t+5، multi-PB، Normal1/High∞ | PASS |
| Strict/Conflict/TP | closed/current candle، Same-Bar، Doji، crossing/gap، touch block، extend/restore/close | PASS |
| Free Space | Buy/Sell formula و strict `>3 USD` | PASS |
| Initial risk | Stop Zone/cap6، first target ≥6، missing-Zone reject | PASS |
| Profit protection | Native RF، X-step، no SL loosening | PASS |
| Execution | SL/TP at creation، native costs، one order/bar، 0.01 lot، max3/max5 | PASS at Python contract + bounded MQL Native lifecycle; exact Symbol/Magic Deal-history evidence exists for both profiles. |
| Risk budgets | Daily realized 20% و GROSS15 reservation | PASS |
| Safety | Session-5min flatten و restart fail-closed | PASS — session flatten/cancel, final zero exposure and same-day MQL restart zero-attempt/position/exposure pass. |
| Audit/Report | Event/Rule/Zone/BO lineage، reject reasons، reusable result evidence | PASS Stage 7 — Python/MQL lifecycle audit plus final structured evidence/report synchronization pass. |

## Evidence تاریخی در انتظار بازیابی

| Evidence | ادعای تاریخی | وضعیت جاری |
|---|---|---|
| E-R0 | Compile و Control PASS | BLOCKED — Artifact/Commit missing |
| E-R2 | ALL_FLAT بهتر از Carry | BLOCKED — Protocol/Timezone missing |
| E-REV | 207/207 Replay و PnL نزدیک | BLOCKED — Fixtures/engines missing |
| E-OPS | 4/4 Restart behavior | BLOCKED — Logs/commit missing |
| Python bootstrap v4 | Data/cache validation successful | BLOCKED — script در Bundle موجود است؛ execution log/cache کامل و محیط بازتولیدشده موجود نیست |

توضیح: Bundle فنی اکنون در بسته Migration موجود است، اما PASSهای تاریخی تا زمانی که Command/Environment و Artifactها در Repository بازتولید نشوند، PASS جاری Strategy محسوب نمی‌شوند.

Statusها: `PASS`, `FAIL`, `NOT_RUN`, `BLOCKED`, `NOT_APPLICABLE`.
