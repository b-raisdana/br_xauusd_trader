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

- [ ] ساخت EA جدید ماژولار — inert current core و Native/Visual adapterها compile/runtime smoke شدند؛ Python causal Signal lifecycle، shared attempt state و protected ORDER→FILL/REJECT→CLOSE durable projection پیاده شد؛ اتصال آن به replay، Native acceptance و MT5 parity باقی است.
- [x] ماژول Zone/Trend — Load/Merge/Priority، Engagement و Trend bootstrap روزانه مستقل پیاده و Contract-tested شد.
- [x] ماژول Signalها — Breakout، Reversal و Pullback با State مشترک Order Slot و Lineage روشن پیاده و Contract-tested شدند.
- [x] ماژول Strict Trend/Conflict/TP — closed/current momentum، Trigger crossing، Touch block و TP state برگشت‌پذیر پیاده و تست شدند.
- [x] ماژول Risk/Execution — Initial SL/TP، Base R، RF، Profit Protection، Native input boundary، fixed volume/concurrency و Margin Gate پیاده و تست شدند.
- [x] ماژول Safety — Daily loss، Portfolio risk، Broker session flatten و Restart fail-closed پیاده و Contract-tested شدند.
- [ ] ماژول Audit/Visual — Event/serialization، durable fail-closed JSONL Journal و MT5 render-only Zone/marker primitives پیاده و compile/runtime-payload tested شد؛ Visual chart inspection باقی است.
- [x] Compile Gate — current inert baseline با `#property strict` روی MetaEditor build 6151، صفر Error و صفر Warning compile شد؛ پس از هر توسعه باید تکرار شود.

---

## 3) Contract Testهای سریع در Python

- [x] Trend bootstrap — رفتار `NONE → N1 → N2 → N3` روی شروع روز و عدم Carry روز قبل تست شد.
- [x] Tick event order — Coordinator Trend و Touch را به‌ترتیب به‌روزرسانی می‌کند و Reversal Signal همان Tick از Trend جدید استفاده می‌کند.
- [x] Breakout strict buffer — شرط دقیق `Close > High+1` و `Close < Low-1` تست شد.
- [x] Breakout engagement — Open داخل Zone، Touch جهت‌دار Buy/Sell، Reset هر M15 و Tick Gap مطابق Legacy تست شد.
- [x] Reversal Market Touch — Touch جهت‌دار Tick-real، Market-only، Wick penetration و Multi-Zone gap تست شد.
- [x] Reversal daily usage — Normal max1 و High max2 با مجموع Buy/Sell تست شدند.
- [x] Reversal usage commit — Signal صرف مصرف نمی‌کند؛ Market Order موفق یا ناموفق سهمیه را مصرف می‌کند.
- [x] Duplicate reversal — چند Recross یک Zone/Direction در یک M15 فقط یک Signal می‌سازد و Directionها مستقل‌اند.
- [x] One new order per candle — اولین تلاش Order Slot مشترک کندل را حتی در شکست Broker مصرف می‌کند؛ Signal دوم فقط قابل Audit است.
- [x] Pullback window — فقط `t+1..t+5`، Cancel pending در t+6 و بدون Carry به روز بعد تست شد.
- [x] Multiple PB per BO — اولین Fill Parent Breakout را نمی‌بندد و Lineage در Fill بعدی حفظ می‌شود.
- [x] Pullback usage — Normal1/High∞، اشتراک Buy/Sell در Zone و استقلال Consumption از Reversal تست شد.
- [x] Conservative penetration — نفوذ inclusive 0.20 در هر دو جهت، نبود Maximum، Entry روی Broken Edge و Retry دقیق تست شد.
- [x] Strict Trend closed candles — همه Candleهای بسته‌شده بعد از PB در جهت لازم و Doji/مخالف به‌عنوان شکست تست شدند.
- [x] Strict Trend current candle — Buy با `Bid>Open` و Sell با `Ask<Open` فقط در نقطه تصمیم تست شد.
- [x] Same-Bar PB→Trigger — مجموعه closed خالی و Current Price نسبت به M15 Open تست شد.
- [x] Pre-Zone Trigger 1$ — Trigger نسبت به Zone حامل TP جاری، اولین Crossing و Tick Gap تست شد.
- [x] Opposite Reversal block — Reversal فقط در Touch واقعی Zone و فقط با Strict Trend معتبر Block می‌شود.
- [x] One-step TP extension — انتقال یک Zone جلوتر، نبود Recursive extension و حفظ TP در Modify ناموفق تست شد.
- [x] TP restore — شکست Strict Trend قبل از لمس TP اولیه، Restore و حفظ TP معتبر در Modify ناموفق تست شد.
- [x] TP market close fallback — شکست Strict Trend بعد از لمس/عبور TP اولیه برای Buy/Sell، Market Close می‌سازد.
- [x] Free Space definition — فرمول Buy/Sell، Zone مجاور، نبود Zone و Minimum inclusive سه دلار تست شد.
- [x] Initial Stop — نزدیک‌ترین Stop Zone، Cap ثابت شش دلار و نبود Stop Zone تست شد.
- [x] Initial Target — اولین Zone حداقل شش دلار دورتر، skip Zone نزدیک و Reject نبود Target تست شد.
- [x] Native RF — Break-even با cash-per-price و هزینه Native ورودی Adapter و عدم استفاده از Entry خام تست شد.
- [x] Profit Protection — Xهای متعدد بدون سقف و عدم SL loosening برای Buy/Sell تست شد.
- [x] Capital limits — 0.01 lot و فقط Profileهای max3/max5 برای 200/300 تست شد.
- [x] Daily/Portfolio Risk — Net Realized guard و GROSS15 native-cash reservation مستقل، مرزی و ترکیبی تست شدند.
- [x] Session safety — در مرز inclusive پنج دقیقه قبل Broker Session end، Entry/Pending/Cycle/Position Actionها تست شدند.
- [x] Restart fail-closed — persisted activation day، Restart همان روز Flatten/Cancel/Lock و روز بعد Resume تست شد.

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

- [x] Freeze test vectors — schema و 16 vector در Python و isolated MQL Strategy Tester با tolerance صریح و generated-header drift gate PASS شد.
- [ ] Python replay — causal runner، UTC export/normalization، time-basis correlation، Zone-day attachment، protected execution/close و atomic typed recovery موجود است؛ fixture-driven Market/Pending Fill/Reject wiring PASS شد و close/modify/cancel replay و full historical input باقی است.
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
