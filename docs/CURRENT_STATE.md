# Current State

## Snapshot

- Project: XAUUSD EA
- Project level: STANDARD
- Current activity: Shared Python/MQL lifecycle contracts validated / inert MQL state projector next
- Strategy target: MVP v2 Consolidated Rulebook
- Rule status: Core Python strategy, Risk/Execution, Safety and Audit rules implemented and contract-tested; full MT5 orchestration/rendering remain
- Research handoff: MERGED_READY_FOR_IMPLEMENTATION
- Last verified Git checkpoint entering this continuation: `f345b64` — Replay Modify/Cancel outcomes
- Last verified date: 2026-09-07
- Current branch: main
- GitHub sync: PRIVATE `origin/main` — synchronized; use Git log for the exact head
- Live state: RESEARCH_ONLY

## Source-of-Truth files

- `PROJECT_BRIEF.md`: هدف، Scope، محدودیت و Success Criteria
- `RULES.md`: تنها قوانین فعال؛ ساختار تشریحی و نام‌های Function-like
- `RULES_ARCHIVE_FUTURE.md`: Superseded/Rejected/Post-MVP و Crosswalk تاریخی
- `DECISIONS.md`: دلیل تصمیم‌های پایدار
- `EXPERIMENTS.md`: Evidence و آزمایش‌های برنامه‌ریزی‌شده
- `TEST_STATUS.md`: وضعیت واقعی اثبات و Gateها
- `TODO.md`: Ledger اجرایی تا Freeze
- `CURRENT_STATE.md`: Recovery سریع و Next Action

## Baseline فعال مستندی

- Zone ورودی روزانه استاد، merge زنجیره‌ای زیر 1.5 دلار و Priority High/Normal.
- Trend روزانه `NONE → N1 → N2 → N3` بدون Carry روز قبل.
- Breakout با Trend در Close و Buffer strict یک دلار.
- Reversal Market Touch؛ Normal max1 و High max2 در Broker Day.
- Pullback Conservative با penetration 0.20، Window پنج کندل، Normal1/High∞ و Multi-PB per BO.
- Strict Pullback Trend با Current Candle/Same-Bar، pre-zone یک دلار، Reversal block در Touch واقعی و TP Extension یک‌مرحله‌ای برگشت‌پذیر.
- Free Space minimum سه دلار، Initial Stop cap شش دلار، Initial Target اولین Zone حداقل شش دلار دورتر.
- Native RF و Profit Protection نامحدود بر مضارب `BASE_R_USD=6`.
- Lot ثابت 0.01، concurrency سه/پنج برای 200/300 دلار، Daily Loss 20% و GROSS15.
- Session flatten پنج دقیقه قبل پایان و Restart fail-closed.

این Baseline از نظر Business Logic مستند است، اما هنوز در Repository جاری `IMPLEMENTED/TESTED/FROZEN` محسوب نمی‌شود.

## موارد تکمیل‌شده

- Current Python domain package `src/xauusd/` now implements deterministic Zone/Trend state, causal tick-chain validation, bar-close Breakout orchestration and daily lineage, Breakout-armed Pullback windows/candidates/expiry actions, tick-real Reversal candidates, daily usage/duplicate guards and a shared one-entry-attempt-per-M15 ledger.
- Zone/Trend/orchestration contract evidence: 21 focused tests PASS; bar close consumes the final processed tick state before rolling its candle into Trend history, duplicate close is rejected, and canonical `ranges.csv` loads as 23 Broker Days, 421 merged Zones with all 444 source rows retained.
- Breakout/Reversal contract evidence: 9 focused/integration tests PASS, including strict equality rejection, daily `BO#` reset, Market-only directional touch, wick penetration, multi-Zone gap suppression, Normal1/High2 shared-direction usage, audit-only non-consumption, failed-request consumption and same-Tick new-Trend consumption.
- Pullback contract evidence: 7 focused/integration tests PASS, including inclusive 0.20 penetration, exact broken-edge retry, `t+1..t+5`, orchestrated pending cancellation at day change, Breakout lineage, shared bar-attempt blocking against Reversal, Normal1/High unlimited fills and one active Zone+Direction window.
- Momentum/TP contract evidence: 5 focused tests PASS, including Same-Bar/current and closed-candle strictness, Doji failure, target-relative first crossing with tick gap, actual-touch-only Reversal blocking, one-step extension, safe modify retry, restore and Market Close symmetry.
- Initial Risk/Execution evidence: 7 focused tests PASS, including adjacent Free Space 3.00, structural Stop with six-dollar cap, first qualifying Target, native-cost RF, unlimited monotonic protection steps, protected orders, fixed 0.01 lot, 200/300 concurrency and native margin boundary.
- Financial Safety evidence: 6 focused tests PASS, including sub-300 net-realized 20% latch/reset/actions, GROSS15 inclusive aggregation of realized/open/pending/new native cash risk, gross-loss non-netting, combined rejection precedence and fail-closed invalid inputs.
- Operational Safety evidence: 4 focused tests PASS, including Broker-derived inclusive five-minute pre-close actions, timezone-basis validation, first attach, same-day restart flatten/cancel/lock and next-Broker-Day release.
- Audit/Visual evidence: 23 focused/integration tests PASS. Reversal, Breakout and Pullback signals plus protected ORDER/FILL/REJECT/CLOSE/MODIFY/CANCEL outcomes persist with request/BO lineage. Modify/Cancel reject events preserve current Position/Pending state, accepted Modify enforces no SL loosening, and typed recovery reuses the same invariant. Visual chart inspection remains.
- Equivalence scaffold: versioned `tests/vectors/core_contracts.json` uses Decimal strings and executes eighteen Python vectors spanning Zone/Engagement/Signal/Trend/Pullback/Momentum/TP/Risk/Safety/Restart plus explicit Execution transition and protection-modification validity; generated MQL constants are byte-drift tested and the MQL startup consumer passed in isolated Strategy Tester. Real-tick lifecycle equivalence remains separate.
- Current MQL5 baseline: `src/mt5/XAUUSD_MVP.mq5` plus modular Contract, Native and Visual includes compile with eighteen matching startup assertions and explicit `1e-9` double tolerance. Shared pure MQL contracts now cover terminal Execution transitions and monotonic protected-position modification. `scripts/run_mt5_contract_smoke.ps1` reproduced the core, Native, Visual and five-tick time-probe markers on 2026-09-07. The Native boundary runtime-validated Broker symbol metadata, current trade session, `OrderCalcProfit` cash risk and `OrderCalcMargin`; the Visual boundary is render-only. No order-send API exists. MetaEditor build 6151 reports 0 errors/0 warnings; `OnTick` only emits the bounded opt-in diagnostic probe and `InpEnableTrading=true` fails initialization.
- Price boundaries use finite `Decimal` values and merged Zone IDs use `{BrokerDay ISO}:R{sorted ordinal}`; future MQL5 parity must test conversion/tolerance explicitly.
- `.gitattributes` now preserves canonical `ranges.csv` and all immutable Legacy evidence byte-for-byte across Windows/Linux; staged Git blobs verify core manifest 16/16 and canonical SHA-256 exactly.
- First-run repository audit completed on 2026-09-06: all current and legacy source/test files were inventoried; `_migration_inbox` is absent.
- Current executable baseline established with project-local Python 3.11.15, `uv`, deterministic migration tests, Ruff, mypy and pytest.
- Windows runtime discovery confirmed Git 2.54.0, GitHub CLI 2.100.0 and MT5 Terminal/MetaEditor build 6151. PowerShell entry points require `-ExecutionPolicy Bypass` on this host.
- Quality gate now fails closed on external command failures and excludes immutable `legacy_reference/` from current-code lint/type enforcement.
- Normalized Python replay now enforces Broker-Day ownership, unique/non-overlapping bars, chronological in-bar ticks, OHLC consistency and final Bid=Close before routing through the same MarketState and durable audit projector. Historical tick input and exit/execution replay remain.
- `build_replay_days` deterministically groups normalized bars, attaches only the matching canonical daily Zones and fails closed when a replayed Broker Day has no Zone input. The ignored bounded sample ran through 1 day, 1 bar, 6,487 ticks and 19 merged Zones with zero signals; this is a connectivity smoke, not strategy evidence.
- Replay ticks can now carry explicit Candidate-bound execution outcomes. Market fill, Pending fill and Broker reject flow through the shared attempt/daily-usage State and durable Execution ledger; missing fixtures remain audit-only, while duplicate/unknown/early fixtures and accepted Market outcomes without fill price fail closed. Four deterministic replay tests cover these boundaries without inferring Broker behavior from price.
- Replay ticks can also carry explicit Close outcomes linked to an already FILLED request, with separate close time/price, Rule IDs and reason. Close on a rejected, unknown or already resolved request fails closed; price touching SL/TP never invents a Native exit.
- Replay now accepts explicit TP/SL Modify and Pending Cancel outcomes, including Native rejection. Each request may have only one lifecycle outcome per Tick, every outcome must fall between its Tick and bar close, and accepted Pending cancellation also clears Pullback pending state. Eight deterministic replay lifecycle cases cover Market/Pending Fill, Reject, Close, Modify and Cancel.
- `scripts/export_mt5_ticks.py` pins the MT5 Python bridge, accepts only explicit UTC ranges, writes only under ignored `data/cache/`, exports no account identity, and was runtime-validated on a 15-minute window: 6,487 ticks, 290,594 bytes, SHA-256 `498d87fa9c8359207284207537c91e85eee9f6a3c11f070d2e1cfb0a04c03d04`. The cache itself is not committed.
- `load_mt5_tick_bars` preserves source row order for equal-millisecond ticks, rejects backward time, requires an explicit whole-minute offset, and creates internally consistent M15 Bid candles. The ignored 6,487-tick sample mechanically normalized/replayed as one bar.
- `scripts/match_mt5_time_basis.py` fail-closes unless an ordered multi-tick probe uniquely matches one whole-30-minute UTC offset in the terminal history. A five-tick local correlation produced one unique match; the probe values, resolved Broker-specific offset and account identity are intentionally not persisted or committed.
- Current test baseline: 111 passed; legacy Python AST parse: 9/9; PowerShell parsing is covered by the repository checks; all three historical MQL5 files have `#property strict` and balanced braces. The isolated 18-vector MQL core/native/visual/time-probe runtime smoke passed; this is not strategy acceptance.
- Template و Handoff به‌صورت محتوایی Merge شدند و Workflow محلی CI حفظ شد.
- Repository روی Branch `main` ایجاد و Baseline در Git ثبت شد.
- `FINAL_PROJECT_HANDOFF_2026-09-06.md` طبق تصمیم Project Leader وارد Repository نشد.
- پوشه‌های غیرضروری `research/` و `output/` ایجاد نشدند.
- `ZONE_ENGAGEMENT` مطابق رفتار Legacy تثبیت شد.
- Pre-Zone Trigger نسبت به Zone حامل TP جاری تثبیت شد.
- مصرف سهمیه Reversal و محدودیت یک Entry attempt در هر M15 تثبیت شد.
- Active Rules و Archive/Future از هم جدا شده‌اند.
- تعارض R ثابت و Stop Distance رفع شده است.
- تعارض Normal/High Reversal و PB consumption با اولویت فایل‌های Rule پیوست حل شده است.
- تصمیم‌های Strict Trend، Same-Bar، Pre-Zone و Reversible TP Extension ثبت شده‌اند.
- Evidence مثبت و منفی تاریخی از Rule جدا شده است.
- TODO و Test Gateهای لازم برای بازسازی مهندسی مشخص‌اند.

## موارد تأییدنشده اجرایی

- Full MT5 orchestration/current EA, MQL lifecycle state projection, Native outcome acquisition, real-tick Python↔MQL5 lifecycle results and acceptance `.set` files.
- اتصال Evidenceهای تاریخی به Dataset/Config/Artifact/Commit.
- رفتار دقیق Broker Symbol/Session و Cost model در محیط هدف.
- نتیجه Regression Ruleهای جدید در برابر Finalist قدیمی.

## Repository audit mismatches

- `docs/RUNBOOK.md` previously said Python still needed verification; Python 3.11.15 is now verified and the exact setup commands are recorded.
- The original quality gate could print PASS after a failed external command. It now checks every exit code.
- CI/tooling originally linted immutable legacy Python. Current-code gates now exclude `legacy_reference/`, while separate read-only legacy integrity/static checks remain recorded here and in `TEST_STATUS.md`.
- Historical result/reference CSVs and the canonical Zone dataset are present, but the historical tick cache, full execution environment, compile logs and source commit provenance required to reproduce strategy PASS claims are not.
- A current inert MQL5 contract core now exists under `src/mt5/`; it is not a trading EA yet. Historical full implementations remain under `legacy_reference/`, contain superseded behavior and must not be promoted or patched into current source.

## Latest historical implementation

- `XAUUSD_EA_MVP_F2_AR_OPS_01_v0_1.mq5`، lineage داخلی گزارش‌شده `1.91`: آخرین Implementation تاریخی Validate‌شده و فقط مرجع Regression.
- `XAUUSD_EA_MVP_F2_AR_RISK_01_v0_1.mq5`: predecessor تاریخی AR-OPS.
- `XAUUSD_EA_MVP_SIMPLE_FINALISTS_v0_1.mq5`: predecessor تاریخی Finalist.

هیچ‌کدام Source of Truth منطق جاری نیستند. Defectهای شناخته‌شده Implementation تاریخی:

1. Sticky Trend و Carry قبلی به‌جای Bootstrap روزانه جدید.
2. High-only Reversal به‌جای فعال‌بودن Normal max1.
3. Complete کردن Parent BO بعد از اولین PB Fill.
4. نبود Strict Pullback Trend و Block در Touch واقعی.
5. نبود TP Extension یک‌مرحله‌ای و Rollback.
6. استفاده از Profit Protection قدیمی `b-29`.
7. استفاده از FreeSpace15 به‌جای Baseline فعال سه‌دلاری.

Historical F2 پیش از Secondary Rules برای Demo/Shadow آماده ارزیابی شده بود؛ این وضعیت به Rulebook تغییرکرده فعلی منتقل نمی‌شود.

## وضعیت بسته فنی و داده

- RAR5 فنی با 173 Entry بررسی و به 168 فایل استخراج شد؛ اختلاف تعداد مربوط به Directory entryها است.
- Manifest اصلی `SHA256_KIT.txt` کامل PASS شد.
- `SHA256_PATCH.txt` قدیمی ناسازگار است: یک Hash mismatch و دو مسیر مفقود دارد؛ فایل Evidence اصلاح نشد.
- `ranges.csv` مستقل با نسخه‌های `data/ranges.csv` و `reference/ranges.csv` داخل Bundle Byte-identical است.

## منابعی که Handoff نام می‌برد ولی در ورودی فعلی موجود نیستند

- `XAUUSD_RULES_MASTER_SECONDARY_FINAL_INTEGRATED_v1_RTL(2).xlsx`
- `rules_before_MPV_v1.md`
- `rules_before_MVP_v4_MASTER_UPDATED_FROM_V3_RTL.xlsx`
- `XAUUSD_RULES_MASTER_RESET_v1.md`
- `XAUUSD_MASTER_TODO_RESET_v2.md`
- `TESTED_ITEMS_STATUS_REPORT_2026-08-31.md`
- `XAUUSD_LESSONS_LEARNED_v1.md`
- `XAUUSD_MVP_FINAL_DAILY_PNL_2026-09-01.csv`
- `XAUUSD_MVP_FINAL_RELEASE_2026-09-01_v1.zip`

محتوای قابل اتکای آنها از Handoff و Rulebook تجمیع شده است، اما Byte-level provenance این فایل‌های خام در ZIP حاضر نیست و نباید ادعای وجود آن شود.

## Status glossary

- `CURRENT CONFIRMED RULE`: Rule تأییدشده، حتی اگر هنوز پیاده/تست نشده باشد.
- `TESTED HISTORICAL CONTROL`: رفتار دارای Evidence تاریخی که ممکن است Superseded شده باشد.
- `APPROVED FOR TEST`: قبل از Promotion، Rule اجرایی محسوب نمی‌شود.
- `REJECTED / RETIRED`: نباید در MVP جاری پیاده شود.
- `POST-MVP`: حفظ می‌شود ولی MVP blocker نیست.
- `UNRESOLVED`: بدون تصمیم Project Leader قابل حدس‌زدن نیست.

## Current blocker

- None for local code production, isolated Strategy Tester smoke, or normal GitHub synchronization.

## Leader decisions

- برای شروع تولید کد تصمیم باز Leader وجود ندارد.
- معیارهای کمی پذیرش عملکرد، مدت Shadow، Broker Live، سرمایه Live و هر افزایش ریسک بعد از ارائه Evidence نیازمند تصمیم Project Leader است.

## Next autonomous action

Codex باید projector حالت lifecycle را روی قراردادهای خالص MQL بسازد و با outcomeهای مصنوعی در smoke ایزوله تست کند؛ سپس مرز read-only مشاهده outcomeهای Native را بدون ارسال Order آماده کند. Trading تا Live Gate inert می‌ماند.

فایل‌های Legacy فقط برای Forensic/Audit هستند و نباید مرجع روزمره اجرای MVP باشند.
