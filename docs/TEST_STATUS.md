# Test and Verification Status

این فایل فقط وضعیت Evidence قابل بازتولید در Repository فعلی را نشان می‌دهد. گزارش تاریخی بدون Artifact/Command/Commit، PASS جاری محسوب نمی‌شود.

## وضعیت فعلی Gateها

| Gate | Scope | وضعیت فعلی | Evidence / Blocker |
|---|---|---|---|
| Migration integrity | Rule/Decision/Experiment separation | PASS | Template/Handoff Merge شد؛ Legacy از Active Rules جدا و تصمیم‌های نهایی Leader ثبت شد. |
| Package structure smoke | Required root, Source-of-Truth files and canonical ranges | PASS | Canonical SHA-256 and required structure remain covered by pytest. |
| Current-code quality | Ruff, format, mypy, pytest, diff check | PASS | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\quality_gate.ps1` on 2026-09-06; 36 tests PASS. |
| Legacy static integrity | Historical sources/manifests without promotion | PASS | Python AST 9/9; PowerShell parser 12/12; MQL5 strict + balanced braces 3/3; Git-staged core manifest 16/16 across byte-preserved attributes. Not compile/runtime evidence. |
| Zone/Trend contract slice | Rule → Python domain → deterministic tests | PASS | 19 focused tests; 23 canonical days → 421 merged Zones; 444/444 source rows retained. |
| Breakout/Reversal signal slice | Strict qualification, touch and accounting contracts | PASS | 9 focused/integration tests; strict buffer/lineage, same-Tick Trend, directional Market touch, gap/wick, duplicate, daily usage and shared bar slot PASS. |
| Pullback signal slice | Conservative entry lifecycle and accounting | PASS | 6 focused tests; penetration/edge retry, five-bar window, Multiple PB, Normal1/High∞, independent counters, active-cycle and cancellation contracts PASS. |
| Rule traceability | Rule name → code → test → journal | NOT_RUN | Zone/Trend code and tests exist; Signal through Audit/Journal traceability remains incomplete. |
| Contract tests | همه موارد بخش 3 `TODO.md` | NOT_RUN | Zone/Trend subset PASS; remaining Signal/Risk/Safety contracts do not yet exist. |
| Targeted regression | Trend/Normal/FreeSpace/Strict/TP/Safety | NOT_RUN | Zone/result artifacts exist; historical tick cache, reproducible environment and current engines are missing. |
| Python ↔ MT5 equivalence | Frozen vectors | NOT_RUN | Engineهای جاری بررسی نشده‌اند. |
| MT5 compile | `#property strict`, zero errors | BLOCKED | MT5/MetaEditor build 6151 is installed, but current MQL5 source and compile log do not exist. |
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
| Breakout | Engage، Trend at Close، strict ±1 buffer، lineage، close opposite Reversal | NOT_RUN — Engage/validation/lineage and opposite-direction closure instruction PASS; position-close execution remains. |
| Reversal | directional Market touch، wick validity، Normal1/High2، duplicate guard | PASS |
| Pullback | penetration 0.20، broken-edge entry/retry، t+1..t+5، multi-PB، Normal1/High∞ | PASS |
| Strict/Conflict/TP | closed/current candle، Same-Bar، Doji، crossing/gap، touch block، extend/restore/close | NOT_RUN |
| Free Space | Buy/Sell formula و minimum 3 USD | NOT_RUN |
| Initial risk | Stop Zone/cap6، first target ≥6، missing-Zone reject | NOT_RUN |
| Profit protection | Native RF، X-step، no SL loosening | NOT_RUN |
| Execution | SL/TP at creation، native costs، one order/bar، 0.01 lot، max3/max5 | NOT_RUN — shared one-order/bar ledger PASS; remaining execution contracts absent. |
| Risk budgets | Daily realized 20% و GROSS15 reservation | NOT_RUN |
| Safety | Session-5min flatten و restart fail-closed | NOT_RUN |
| Audit/Visual | Event/Rule/Zone/BO lineage، reject reasons، chart markers/tooltips | NOT_RUN |

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
