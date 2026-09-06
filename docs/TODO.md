# TODO تا MVP

نسخه: v2 — Consolidated Migration  
این فایل تنها Ledger اجرایی تا Freeze MVP است. هر تغییر ابتدا اینجا ثبت می‌شود و سپس اجرا می‌شود.

وضعیت هر مورد: `TODO → IMPLEMENTED → TESTED → PRODUCT OWNER ACCEPTED → FROZEN`

---

## 0) مهاجرت به Repository استاندارد

- [x] Repository واقعی، Branch فعال، آخرین Commit معتبر و Working Tree بررسی شود.
- [x] این اسناد با نسخه‌های موجود Repository به‌صورت Diff/Merge ادغام شوند؛ فایل کامل‌تر حفظ شد و CI محلی از بین نرفت.
- [x] نام‌های قدیمی Rule به نام‌های فعال این Rulebook Crosswalk شوند.
- [ ] هر ادعای تاریخی PASS فقط پس از یافتن Artifact/Command/Commit متناظر در `TEST_STATUS.md` ثبت شود.
- [x] پس از Merge، Git checkpoint منسجم `4cc06b1` ساخته شد؛ GitHub هنوز پیکربندی نشده است.
- [x] ناسازگاری `SHA256_PATCH.txt` بدون تغییر Evidence بررسی و به‌عنوان مشکل Manifest/Path تاریخی ثبت شد.
- [x] Merge و کنترل انسجام Rulebook پیش از شروع کدنویسی انجام شد.
- [x] First-run audit: همه Source/Testهای جاری و Legacy inventory و static-inspect شدند؛ `_migration_inbox` وجود ندارد.
- [x] Runtime baseline: Python 3.11 محلی، MT5/MetaEditor discovery و فرمان‌های قابل تکرار Windows تأیید شدند.
- [x] Baseline quality gate: Ruff، format، mypy، pytest و `git diff --check` به‌صورت fail-closed اجرا شدند.

## 1) Baseline و مستندات

- [x] Consolidate قوانین اولیه و ثانویه — قوانین فعال، لغوشده و آینده از فایل‌های قبلی جدا و یکپارچه شدند.
- [x] اعمال اولویت Secondary — هرجا Secondary با Primary تضاد داشت، Rule جدید مبنا قرار گرفت.
- [x] رفع ابهام R — در قوانین فعال، R مبهم حذف و `BASE_R_USD=6` از `ACTUAL_STOP_DISTANCE` جدا شد.
- [x] تعریف نهایی Strict Pullback Trend — Current Candle و Same-Bar با Current Price نسبت به Candle Open ارزیابی می‌شوند.
- [x] تعریف TP Extension — Extension یک‌مرحله‌ای، Restore قبل از TP اولیه و Market Close بعد از عبور TP اولیه مشخص شد.
- [x] تعریف Pre-Zone Trigger — Baseline برابر 1 دلار و Crossing-based تعیین شد؛ Optimization انجام نمی‌شود.

---

## 2) بازسازی مهندسی کد

- [ ] ساخت EA جدید ماژولار — کد Legacy Patch نمی‌شود و EA بر اساس Rulebook فعال از نو به بخش‌های کوچک و قابل Trace تقسیم می‌شود.
- [x] ماژول Zone/Trend — Load/Merge/Priority، Engagement و Trend bootstrap روزانه مستقل پیاده و Contract-tested شد.
- [ ] ماژول Signalها — Breakout، Reversal و Pullback با Rule IDهای واضح و بدون منطق تکراری پیاده شوند.
- [ ] ماژول Strict Trend/Conflict/TP — سه Rule مشترک با State واحد و Triggerهای دقیق پیاده شوند.
- [ ] ماژول Risk/Execution — Initial SL/TP، Base R، RF، Profit Protection، Native Costs و Margin Gate پیاده شوند.
- [ ] ماژول Safety — Daily loss، Portfolio risk، Session flatten و Restart fail-closed پیاده شوند.
- [ ] ماژول Audit/Visual — Journal و Chart QA ساده و قابل فهم برای رهبر پروژه ساخته شود.
- [ ] Compile Gate — کد با `#property strict` و بدون Error آماده شود.

---

## 3) Contract Testهای سریع در Python

- [x] Trend bootstrap — رفتار `NONE → N1 → N2 → N3` روی شروع روز و عدم Carry روز قبل تست شد.
- [ ] Tick event order — Coordinator اکنون Trend را قبل از Engagement به‌روزرسانی می‌کند؛ اثبات اینکه Reversal Signal همان Tick State جدید را مصرف می‌کند همراه ماژول Signal تکمیل شود.
- [ ] Breakout strict buffer — شرط دقیق `Close > High+1` و `Close < Low-1` تست شود.
- [x] Breakout engagement — Open داخل Zone، Touch جهت‌دار Buy/Sell، Reset هر M15 و Tick Gap مطابق Legacy تست شد.
- [ ] Reversal Market Touch — Touch جهت‌دار و عدم استفاده از Pending از قبل تست شود.
- [ ] Reversal daily usage — Normal max1 و High max2 با مجموع Buy/Sell تست شوند.
- [ ] Reversal usage commit — Signal صرف مصرف نکند؛ Market Order موفق یا ناموفق سهمیه را مصرف کند.
- [ ] Duplicate reversal — چند Recross یک Zone/Direction در یک M15 فقط یک Signal بسازد.
- [ ] One new order per candle — اولین تلاش Order Slot کندل را مصرف کند؛ Entry دوم ایجاد نشود و Signalهای اضافی فقط Audit شوند.
- [ ] Pullback window — فقط `t+1..t+5` و بدون Carry به روز بعد تست شود.
- [ ] Multiple PB per BO — اولین Fill نباید Parent Breakout را قبل از پایان Window ببندد.
- [ ] Pullback usage — Normal1/High∞ و استقلال Consumption از Reversal تست شود.
- [ ] Conservative penetration — نفوذ 0.20، Entry روی Broken Edge و Retry دقیق تست شود.
- [ ] Strict Trend closed candles — همه Candleهای بسته‌شده بعد از PB باید در جهت لازم باشند و Doji شکست محسوب شود.
- [ ] Strict Trend current candle — Buy با `Bid>Open` و Sell با `Ask<Open` در لحظه تصمیم تست شود.
- [ ] Same-Bar PB→Trigger — همان کندل PB با Current Price نسبت به M15 Open ارزیابی شود.
- [ ] Pre-Zone Trigger 1$ — Trigger نسبت به Zone حامل TP جاری، اولین Crossing و Tick Gap بدون Equality تست شود.
- [ ] Opposite Reversal block — Reversal فقط در Touch واقعی Zone و فقط در صورت Strict Trend معتبر Block شود.
- [ ] One-step TP extension — انتقال TP فقط یک Zone جلوتر و فقط وقتی Zone فعلی همان TP اولیه است تست شود.
- [ ] TP restore — شکست Strict Trend قبل از لمس TP اولیه باید TP را به مقدار قبلی برگرداند.
- [ ] TP market close fallback — شکست Strict Trend بعد از عبور TP اولیه باید Market Close ایجاد کند.
- [ ] Free Space definition — فرمول Buy/Sell و Minimum جدید 3 دلار تست شود.
- [ ] Initial Stop — Stop Zone و Cap ثابت 6 دلار با Edge Case نبود Stop Zone تست شود.
- [ ] Initial Target — اولین Zone حداقل 6 دلار دورتر و Reject در نبود Target تست شود.
- [ ] Native RF — Break-even خالص با هزینه‌های Native و عدم اشتباه با Entry خام تست شود.
- [ ] Profit Protection — برای Xهای متعدد و عدم SL loosening تست شود.
- [ ] Capital limits — 0.01 lot و max3/max5 تست شود.
- [ ] Daily/Portfolio Risk — Realized guard و GROSS15 reservation مستقل و ترکیبی تست شوند.
- [ ] Session safety — پنج دقیقه قبل Session پایان، Entry/Pending/Cycle/Position رفتار صحیح داشته باشند.
- [ ] Restart fail-closed — Restart همان روز باید Flatten/Cancel/Lock و روز بعد Resume کند.

Gate: همه Contract Testهای بالا PASS.

---

## 4) Regression هدفمند قبل از بک‌تست سنگین

- [ ] روز مرجع QA — حداقل روزی که رهبر پروژه رفتار صحیح آن را می‌شناسد Signal-by-Signal بررسی شود.
- [ ] Trend regression — Rule جدید Bootstrap با Sticky قدیمی مقایسه و حذف/اضافه Signalها گزارش شود؛ انتخاب Rule تغییر نمی‌کند مگر با تصمیم جدید رهبر.
- [ ] Normal Reversal attribution — عملکرد Normal و High جدا گزارش شود چون Evidence قدیمی برای Normal ضعیف بوده است.
- [ ] FreeSpace validation — Rule جدید 3$ در برابر Control تاریخی 15$ فقط A/B گزارش شود؛ Grid Search ممنوع است.
- [ ] Strict Trend examples — چند Momentum سریع شامل Same-Bar و Multi-Bar روی Chart و Journal بررسی شود.
- [ ] TP Extension A/B — Baseline بدون Extension در برابر Rule یک‌مرحله‌ای جدید مقایسه شود، بدون Optimization پارامتر.
- [ ] Safety regression — هیچ تغییر Signal نباید Daily/Portfolio/Session/Restart safety را دور بزند.

Gate: اختلاف اجرایی بدون توضیح = صفر.

---

## 5) Python ↔ MT5 Equivalence

- [ ] Freeze test vectors — ورودی و خروجی سناریوهای Contract برای هر دو Engine یکسان شود.
- [ ] Python replay — نتایج سریع برای Signal/State/Exit تولید شود.
- [ ] MT5 Real Tick comparison — Finalist روی همان روزها با Every Tick Based on Real Ticks اجرا شود.
- [ ] اختلاف‌ها طبقه‌بندی شوند — فقط `RULE / CODE / DATA / TEST_CONFIG`؛ مشکل فنی بدون نیاز Business Logic به رهبر برنگردد.

Gate: صفر اختلاف توضیح‌نشده.

---

## 6) Final MT5 Acceptance

- [ ] Broker/Symbol specification — Contract size، Tick size/value، Stops/Freeze level، Session و Cost model ثبت شود.
- [ ] سناریوی 200 دلار — 0.01 lot، max3، Risk/Safety فعال و بدون Margin Block غیرمنتظره.
- [ ] سناریوی 300 دلار — 0.01 lot، max5، Risk/Safety فعال و بدون Margin Block غیرمنتظره.
- [ ] Technical QA — صفر SL-loosen، صفر exposure ناخواسته بعد Session، صفر same-day restart fill.
- [ ] Deal PnL audit — نتیجه نهایی از Deal History و هزینه Native محاسبه شود.

Gate: Technical Acceptance PASS.

---

## 7) تایید بصری رهبر پروژه

- [ ] انتخاب چند روز نمونه — روزهای Reversal، Breakout، چند Pullback، Strict Trend و TP Extension پوشش داده شوند.
- [ ] Chart ساده — Zone High/Normal، Markerهای R/BO/PB و Tooltip کامل نمایش داده شود.
- [ ] تطبیق Rule با Chart — هر Event قابل اتصال به Rule ID و Journal باشد.
- [ ] تایید رهبر پروژه — فقط پس از تایید منطق روی نمونه‌ها Rulebook/Code Freeze شوند.

---

## 8) Freeze MVP

- [ ] Freeze Rulebook — نسخه تاییدشده بدون Overwrite قفل شود.
- [ ] Freeze Code — سورس تاییدشده Versioned و Immutable شود.
- [ ] Freeze Test Evidence — فقط خلاصه Evidence لازم برای بازتولید Acceptance نگه‌داری شود؛ خروجی‌های حجیم موقت Core Project نیستند.
- [ ] آماده Shadow/Broker Acceptance — MVP پس از Freeze وارد مرحله اجرای محدود و جمع‌آوری داده جدید شود.
