# TODO تا MVP

وضعیت هر مورد: `TODO → IMPLEMENTED → TESTED → PRODUCT OWNER ACCEPTED → FROZEN`

---

## 1) Baseline و مستندات

- [x] Consolidate قوانین اولیه و ثانویه — قوانین فعال، لغوشده و آینده از فایل‌های قبلی جدا و یکپارچه شدند.
- [x] اعمال اولویت Secondary — هرجا Secondary با Primary تضاد داشت، Rule جدید مبنا قرار گرفت.
- [x] رفع ابهام R — در قوانین فعال، R مبهم حذف و `BASE_R_USD=6` از `ACTUAL_STOP_DISTANCE` جدا شد.
- [x] تعریف نهایی Strict Pullback Trend — Current Candle و Same-Bar با Current Price نسبت به Candle Open ارزیاسی می‌شوند.
- [x] تعریف TP Extension — Extension یک‌مرحله‌ای، Restore قبل از TP اولیه و Market Close بعد از عبور TP اولیه مشخص شد.
- [x] تعریف Pre-Zone Trigger — Baseline برابر 1 دلار و Crossing-based تعیین شد؛ Optimization انجام نمی‌شود.

---

## 2) Contract Testهای سریع در Python

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
- [x] Free Space definition — فرمول Buy/Sell و Zone مجاور تثبیت شد؛ فاصله `<=3` Block و فقط `>3` مجاز است.
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

## 3) Regression هدفمند MVP

- [x] Trend Bootstrap — رفتار Sticky تاریخی رد و مقایسه مجدد از Gate MVP حذف شد.
- [x] Normal/High — هر دو Priority جزء ثابت Strategy هستند؛ PnL تفکیکی معیار حذف هیچ‌کدام نیست و از Gate MVP حذف شد.
- [x] FreeSpace 3 — Rule فعال `<=3 Block / >3 Allow` در Python و MQL اعمال شد؛ مقایسه با 15 دلار به Post-MVP منتقل شد.
- [x] Signal QA خارجی — Fixture مورد اعتماد مستقل موجود نیست و با تصمیم رهبر از Gate MVP حذف شد؛ گزارش جامع نهایی مرجع پذیرش است.
- [x] Strict Trend examples — Same-Bar/Multi-Bar/Doji/opposing candle با fixtureهای deterministic و runtime TP ledger بررسی شد؛ Chart گیت فعال نیست.
- [x] TP Extension A/B — اجرای قبل/بعد روی همان روز و Config بدون Optimization مقایسه شد: شمار attempt/fill ثابت و net هر Profile فقط `+0.14 USD` تغییر کرد.
- [x] Safety regression — تغییر TP هیچ‌یک از Daily/GROSS15/Session/Restart gateها را دور نزد؛ Full gate و restart runtime PASS شد.

Gate: اختلاف اجرایی بدون توضیح = صفر.

---

## 4) Python ↔ MT5 Equivalence

- [x] Freeze test vectors — schema و 19 vector، شامل lifecycle و causal Tick order، در Python و isolated MQL Strategy Tester با tolerance صریح و generated-header drift gate PASS شد.
- [x] Python replay — causal runner، UTC export/normalization، time-basis correlation، Zone-day attachment و fixture-driven Market/Pending Fill/Reject/Close/Modify/Cancel با atomic recovery برای Scope MVP PASS شد.
- [x] MT5 Real Tick acceptance — اجرای جاری روی یک روز، Restart و 23 روز با Every Tick Based on Real Ticks PASS شد؛ مقایسه Native چندروزه Python و Finalist تاریخی Gate MVP نیست.
- [x] MQL multi-day lifecycle robustness — تمام 23 روز Zone با Real Ticks و max3 اجرا شد؛ صفر failure/SL-loosen/exposure و TP Market Close بومی مشاهده شد.
- [x] اختلاف‌های Scope فعال در صورت وجود با `RULE / CODE / DATA / TEST_CONFIG` طبقه‌بندی می‌شوند؛ اختلاف توضیح‌نداده‌شده در Evidence جاری ثبت نشده است.

Gate: صفر اختلاف توضیح‌نشده.

---

## 5) Final MT5 Acceptance

- [x] Broker/Symbol specification — Contract size، Tick size/value، Stops/Freeze level، Session و Cost model روز مرجع ثبت شد.
- [x] سناریوی 200 دلار — real ticks، 0.01/max3: 10 attempt، 8 accepted، 2 known native reject، 3 Breakout accepted، max position=1 و failed=0.
- [x] سناریوی 300 دلار — real ticks، 0.01/max5: 17 attempt، 15 accepted، 2 known native reject، 5 Breakout accepted، max position=1 و failed=0.
- [x] Technical QA — صفر SL-loosen، صفر exposure بعد Session و same-day restart با صفر attempt/position/exposure PASS شد.
- [x] Deal PnL audit — نتیجه bounded یک‌روزه از Deal History و هزینه Native محاسبه شد؛ این Evidence ادعای سودآوری نیست.

Gate: Technical Acceptance PASS.

---

## 6) گزارش جامع نهایی تست

- [x] Evidence ساختاریافته هر اجرای Acceptance شامل نسخه Code/Config/Data و تمام Counterهای فنی و عددی ذخیره شد.
- [x] `docs/FINAL_TEST_REPORT.md` نتایج همه Profile/Dayهای اجراشده، Gateها، اختلاف‌ها، محدودیت‌ها و روش بازتولید را یکجا ثبت کرد.
- [x] گزارش با آخرین Compile، 139 تست Python، parity، restart، Breakout/TP lifecycle و MT5 real-tick acceptance همگام شد.
- [x] هر گزارش خلاصه بعدی فقط از Evidence ذخیره‌شده تولید می‌شود و MT5 را دوباره اجرا نمی‌کند.

---

## 7) Freeze MVP

- [x] Freeze Rulebook — نسخه تأییدشده با Tag نسخه MVP بدون Overwrite قفل شد.
- [x] Freeze Code — سورس تأییدشده با Hash و Tag نسخه MVP قفل شد.
- [x] Freeze Test Evidence — خلاصه Evidence بازتولیدپذیر نگه‌داری و خروجی حجیم خارج Git ماند.
- [x] آماده Shadow/Broker Acceptance — بسته MVP فقط برای ورود به گیت جداگانه Demo/Shadow آماده است؛ هیچ Live فعال نیست.
