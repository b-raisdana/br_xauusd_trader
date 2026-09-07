# Test and Verification Status

این فایل فقط وضعیت Evidence قابل بازتولید در Repository فعلی را نشان می‌دهد. گزارش تاریخی بدون Artifact/Command/Commit، PASS جاری محسوب نمی‌شود.

## وضعیت فعلی Gateها

| Gate | Scope | وضعیت فعلی | Evidence / Blocker |
|---|---|---|---|
| Migration integrity | Rule/Decision/Experiment separation | PASS | Template/Handoff Merge شد؛ Legacy از Active Rules جدا و تصمیم‌های نهایی Leader ثبت شد. |
| Package structure smoke | Required root, Source-of-Truth files and canonical ranges | PASS | Canonical SHA-256 and required structure remain covered by pytest. |
| Current-code quality | Ruff, format, mypy, pytest, diff check | PASS | Local gate on 2026-09-07; 109 tests PASS, including full fixture-driven Python execution lifecycle, atomic typed recovery, normalized Zone-day replay, constrained MT5 export, fail-closed time-basis matching and inert MQL boundaries. |
| Legacy static integrity | Historical sources/manifests without promotion | PASS | Python AST 9/9; PowerShell parser 12/12; MQL5 strict + balanced braces 3/3; Git-staged core manifest 16/16 across byte-preserved attributes. Not compile/runtime evidence. |
| Zone/Trend/orchestration slice | Rule → causal ticks → bar close → deterministic tests | PASS | 21 focused tests; strict tick-chain/final-close validation and Breakout-before-Trend-roll PASS; 23 canonical days → 421 merged Zones; 444/444 source rows retained. |
| Breakout/Reversal signal slice | Strict qualification, touch and accounting contracts | PASS | 9 focused/integration tests; strict buffer/lineage, same-Tick Trend, directional Market touch, gap/wick, duplicate, daily usage and shared bar slot PASS. |
| Pullback signal slice | Conservative entry lifecycle and accounting | PASS | 7 focused/integration tests; penetration/edge retry, five-bar window, Breakout lineage, shared Reversal/Pullback bar slot, rollover cancellation, Multiple PB and Normal1/High∞ PASS. |
| Momentum/TP slice | Strict trend, target trigger, conflict and extension lifecycle | PASS | 5 focused tests; Same-Bar/closed/current checks, crossing/gap, touch block, safe one-step modify, restore and Market Close PASS. |
| Initial Risk/Execution slice | Geometry, native RF, protection and fixed capital profiles | PASS | 7 focused tests; Free Space, Stop/Target, RF, monotonic steps, protected order, 0.01 lot, max3/max5 and margin boundary PASS. |
| Financial Safety slice | Daily net-realized and GROSS15 entry gates | PASS | 6 focused tests; daily latch/reset/actions, inclusive gross budget, all four native risk components, combined rejection and invalid-input failure PASS. |
| Operational Safety slice | Broker session boundary and restart lock | PASS | 4 focused tests; inclusive pre-close action set, time-basis validation, persisted same-day detection and next-day release PASS. |
| Audit payload slice | Immutable trace records, durable JSONL and leader marker DTOs | PASS | 23 focused/integration tests; typed/atomic recovery and linked ORDER/FILL/REJECT/CLOSE/MODIFY/CANCEL projection PASS. Reject preserves protection/Pending state and accepted Modify cannot loosen SL. |
| Equivalence-vector scaffold | Shared versioned Decimal-string inputs/outputs | PASS for Python + MQL runtime | 16 vectors execute in Python; generated-header drift and explicit `1e-9` MQL tolerance PASS; isolated Strategy Tester emitted the exact core success marker. |
| Rule traceability | Rule name → code → test → journal | PASS for Python lifecycle | Replay traces Signal→ORDER→FILL/REJECT→CLOSE/MODIFY/CANCEL with semantic Rule IDs, request IDs and lineage; MQL/Native parity remains NOT_RUN. |
| Contract tests | همه موارد بخش 3 `TODO.md` | PASS at Python domain boundary | All listed fast contracts PASS; external Native/MT5 parity and durable side effects remain separate gates. |
| MT5 tick acquisition | Read-only UTC raw input, ignored cache | PASS for bounded smoke | Bridge 5.0.6180 exported 6,487 ticks/290,594 bytes; explicit-offset normalization replayed all rows as one M15 bar. An ordered five-tick probe uniquely correlated local server time to UTC; no cache, probe values, resolved Broker-specific offset or account identity are committed. |
| Targeted regression | Trend/Normal/FreeSpace/Strict/TP/Safety | NOT_RUN | Current replay engine applies explicit full lifecycle fixtures through shared usage and Audit State; MQL/Native evidence and full historical input remain missing. |
| Python ↔ MT5 equivalence | Frozen core vectors | PASS for frozen core; lifecycle NOT_RUN | 16 shared vectors PASS in Python and isolated MQL runtime at `1e-9`; real-tick order lifecycle comparison remains. |
| MT5 compile/runtime smoke | `#property strict`, zero errors, inert startup | PASS for current inert core + Native/Visual boundaries | Build 6151: 0 errors/0 warnings; isolated Strategy Tester validated 16 vectors, Symbol/Session/Profit/Margin adapters, the audit label/tooltip payload and five bounded opt-in time-probe markers. This is not full EA acceptance or visual inspection. |
| MT5 real-tick acceptance | 200/300 USD scenarios | NOT_RUN | Broker profile و `.set` جاری موجود نیست. |
| Visual QA | Chart + Journal + Rule IDs | NOT_RUN | بعد از Technical PASS. |
| MVP Freeze | Rulebook/Code/Evidence immutable version | NOT_RUN | همه Gateهای قبلی لازم‌اند. |
| Shadow/Demo | Broker acceptance | NOT_RUN | پس از MVP Freeze. |
| Limited Live | Explicit Leader approval | BLOCKED | شواهد و Risk approval موجود نیست. |
| Historical bundle core manifest | `SHA256_KIT.txt` | PASS | هر 16 ورودی Manifest با فایل استخراج‌شده Match شد. |
| Historical patch manifest | `SHA256_PATCH.txt` | FAIL | `README_FA.md` mismatch و دو مسیر `reversal_portfolio_reference/*` در Bundle موجود نیستند؛ Evidence دست‌کاری نشد. |
| Canonical ranges identity | uploaded/data/reference copies | PASS | SHA-256 هر سه نسخه یکسان است. |

## Coverage الزامی Rules

| گروه Rule | تست‌های اجباری | وضعیت |
|---|---|---|
| Zone | Load/Normalize/Sort، line Zone، chain merge `<1.5`، Priority، no hard cap | PASS |
| Trend | Day bootstrap، live threshold، sticky state، Tick event order | PASS |
| Breakout | Engage، Trend at Close، strict ±1 buffer، lineage، close opposite Reversal | NOT_RUN — Engage/validation/lineage, opposite-direction closure instruction and generic protected Close lifecycle PASS; Breakout-to-position wiring remains. |
| Reversal | directional Market touch، wick validity، Normal1/High2، duplicate guard | PASS |
| Pullback | penetration 0.20، broken-edge entry/retry، t+1..t+5، multi-PB، Normal1/High∞ | PASS |
| Strict/Conflict/TP | closed/current candle، Same-Bar، Doji، crossing/gap، touch block، extend/restore/close | PASS |
| Free Space | Buy/Sell formula و minimum 3 USD | PASS |
| Initial risk | Stop Zone/cap6، first target ≥6، missing-Zone reject | PASS |
| Profit protection | Native RF، X-step، no SL loosening | PASS |
| Execution | SL/TP at creation، native costs، one order/bar، 0.01 lot، max3/max5 | PASS at Python contract boundary — read-only MT5 Native adapter compiles; runtime validation/equivalence remains. |
| Risk budgets | Daily realized 20% و GROSS15 reservation | PASS |
| Safety | Session-5min flatten و restart fail-closed | PASS at Python contract boundary — Broker session adapter compiles; runtime validation and persistence remain. |
| Audit/Visual | Event/Rule/Zone/BO lineage، reject reasons، chart markers/tooltips | NOT_RUN — Python full lifecycle durable events/recovery and MQL render-only primitives/payload PASS; chart-object visual inspection remains. |

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
