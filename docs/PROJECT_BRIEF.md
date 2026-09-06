# Project Brief

## هویت و نقش‌ها

- نام پروژه: XAUUSD EA
- سطح پروژه: STANDARD
- مالک تصمیم‌های محصول و ریسک: Project Leader
- شریک علمی و مستندسازی: ChatGPT Work
- مالک اجرای فنی، تست، Debug، Git و GitHub: Codex
- Source of Truth: فایل‌های Repository، نه گفتگو

## بازار و محیط اجرا

- Symbol: XAUUSD
- منطق کندلی: M15
- Touch، Fill، Spread، SL/TP و Execution: Tick واقعی
- مرجع نهایی پذیرش: MT5 Strategy Tester با `Every Tick Based on Real Ticks`
- Python/Polars: Research، Screening، Replay و QA سریع
- Broker تاریخی: MetaQuotes-Demo؛ Broker نهایی Live هنوز انتخاب/ثبت نشده است
- Zoneها: ورودی روزانه استاد؛ تولید خودکار Zone خارج از Scope MVP

## هدف

پیاده‌سازی الگوریتمیک یک روش Price Action آموزش‌داده‌شده برای اجرای دستی طلا، در قالب EA ماژولار و قابل Audit که قوانین Active Zone/Trend/Breakout/Reversal/Pullback/Risk را بدون تفسیر پنهان اجرا کند، در Python و MT5 رفتار قابل‌مقایسه داشته باشد و پس از عبور از Gateهای فنی و بصری وارد Shadow/Demo شود.

## مسیر تحویل

`Rule Consolidation → Contract Tests → Targeted Regression → Python/MT5 Equivalence → MT5 Acceptance → Visual Leader Acceptance → MVP Freeze → Shadow/Demo`

Real Money و افزایش ریسک خارج از این مسیر و نیازمند تأیید مستقیم Project Leader است.

## نمای ساده Project Leader

برای مدیریت روزمره، Project Leader معمولاً فقط این چهار فایل را نیاز دارد:

1. `PROJECT_BRIEF.md` — هدف، Scope و معیار موفقیت.
2. `RULES.md` — رفتار دقیق Active MVP.
3. `TODO.md` — کارهای باقی‌مانده و Gateها.
4. `CURRENT_STATE.md` — وضعیت جاری، Blocker و Next Action.

`RULES_ARCHIVE_FUTURE.md`، `DECISIONS.md`، `EXPERIMENTS.md` و `TEST_STATUS.md` فایل‌های پشتیبان Audit هستند و عمدتاً توسط AI نگه‌داری می‌شوند.

## Success Criteria

- هر رفتار معاملاتی و Risk به نام Rule فعال قابل ردیابی باشد.
- همه Contract Testهای `TODO.md` PASS شوند.
- اختلاف توضیح‌نشده Python و MT5 صفر باشد.
- MT5 Compile Gate بدون Error و اجرای Real-Tick قابل بازتولید باشد.
- هزینه‌ها از Bid/Ask و Deal History واقعی Broker/Tester محاسبه شوند.
- صفر SL-loosening، صفر Exposure ناخواسته بعد Session و صفر Fill همان‌روز بعد Restart ثبت شود.
- چند روز مرجع روی Chart و Journal توسط Project Leader تأیید شوند.
- Rulebook، Code و Evidence نسخه پذیرفته‌شده Freeze و غیرقابل Overwrite شوند.

معیارهای سودآوری، Drawdown و مدت Shadow لازم برای Limited Live باید پس از تولید Evidence معتبر توسط Project Leader تصویب شوند.

## محدودیت‌های قطعی

- `BASE_R_USD = 6.00 USD` ثابت است و با `ACTUAL_STOP_DISTANCE` یکی نیست.
- حجم MVP ثابت است؛ Dynamic Sizing فعال نیست.
- Optimization/Grid Search گسترده روی Sample فعلی انجام نمی‌شود.
- هیچ Backtest مثبتی به‌تنهایی مجوز Live نیست.
- Credential/Secret داخل Git قرار نمی‌گیرد.
- Rule جدید یا تغییر Business Logic بدون تأیید Project Leader وارد Active Rulebook نمی‌شود.
- پاسخ‌ها و اسناد مدیریتی برای Project Leader تا حد ممکن فارسی، ساده و قابل فهم باشند؛ عنوان فارسی Rule پیش از شناسه Semantic انگلیسی بیاید.
- تغییر علمی ضعیف، Overfit، Risk شبه-Martingale یا نتیجه‌گیری آماری نامعتبر باید صریحاً نقد شود.

## خارج از Scope MVP

Aggressive Pullback، تولید خودکار Zone، Buffer پویا، Indicator Filterها، Dynamic Lot Sizing، Session-specific Base R، Daily Profit Giveback، Recursive TP Extension، Persistent Restart Recovery کامل، Strategy 2/3 و پروژه مستقل VLAD.

## وضعیت شواهد

شواهد تاریخی امیدوارکننده و منفی در `EXPERIMENTS.md` ثبت می‌شوند، اما تا زمان بازیابی Dataset/Config/Artifact/Commit نباید به‌عنوان PASS جاری یا تضمین عملکرد تلقی شوند.

## انضباط علمی

- Dataset اصلی تاریخی حدود 23 روز Zone دارد و برای Optimization چندپارامتری کوچک است.
- هر بار فقط یک خانواده Rule تغییر و اثر علّی آن گزارش شود.
- Train/Forward/OOS بر مبنای روز جدا بمانند.
- انتخاب فقط بر اساس Net PnL ممنوع است؛ Trade Count، PF، Forward، Tail Loss، Concentration و اثر مستقیم Rule نیز گزارش شوند.
- نتیجه منفی تاریخی حتی اگر Project Leader Rule متفاوتی را انتخاب کند حذف نمی‌شود.
- تأیید Business Rule با اثبات آماری آن یکی نیست.
