# Current State

## Snapshot

- Project: XAUUSD EA
- Project level: STANDARD
- Current activity: MVP v2 technical freeze candidate complete; awaiting separate Demo/Shadow authorization and environment acceptance
- Strategy target: MVP v2 Consolidated Rulebook
- Rule status: Active Rulebook implementation is complete for Python contracts and guarded MQL Breakout/Reversal/Pullback protected-entry and Native lifecycle
- Research handoff: MERGED_READY_FOR_IMPLEMENTATION
- Last verified date: 2026-09-08
- Current branch: main
- GitHub sync: PRIVATE `origin/main` — rapid-MVP mode; routine push/PR/remote CI deferred, local Git retained
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
- Free Space باید strict بزرگ‌تر از سه دلار باشد (`<=3` Block)، Initial Stop cap شش دلار و Initial Target اولین Zone حداقل شش دلار دورتر است.
- Native RF و Profit Protection نامحدود بر مضارب `BASE_R_USD=6`.
- Lot ثابت 0.01، concurrency سه/پنج برای 200/300 دلار، Daily Loss 20% و GROSS15.
- Session flatten پنج دقیقه قبل پایان و Restart fail-closed.

این Baseline در نسخه `mvp-v2.0.0` برای Research/Strategy Tester، `IMPLEMENTED/TESTED/FROZEN` است؛ این وضعیت مجوز Demo/Live نیست.

## Status glossary

- `CURRENT CONFIRMED RULE`: Rule تأییدشده، حتی اگر هنوز پیاده/تست نشده باشد.
- `TESTED HISTORICAL CONTROL`: رفتار دارای Evidence تاریخی که ممکن است Superseded شده باشد.
- `APPROVED FOR TEST`: قبل از Promotion، Rule اجرایی محسوب نمی‌شود.
- `REJECTED / RETIRED`: نباید در MVP جاری پیاده شود.
- `POST-MVP`: حفظ می‌شود ولی MVP blocker نیست.
- `UNRESOLVED`: بدون تصمیم Project Leader قابل حدس‌زدن نیست.

## Current blocker

- None for local code production, isolated Strategy Tester smoke, or normal GitHub synchronization.
- Final Rulebook/Code freeze does not require visual review; it requires complete stored acceptance evidence and the canonical final report.

## Leader decisions

- برای شروع تولید کد تصمیم باز Leader وجود ندارد.
- معیارهای کمی پذیرش عملکرد، مدت Shadow، Broker Live، سرمایه Live و هر افزایش ریسک بعد از ارائه Evidence نیازمند تصمیم Project Leader است.

## Next autonomous action

بسته فنی MVP آماده Freeze/Tag است. اقدام بعدی فقط پس از مجوز جداگانه رهبر، آماده‌سازی و اجرای Demo/Shadow در محیط Broker هدف است؛ Live و افزایش ریسک همچنان ممنوع است.

فایل‌های Legacy فقط برای Forensic/Audit هستند و نباید مرجع روزمره اجرای MVP باشند.
