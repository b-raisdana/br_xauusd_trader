# TODO تا MVP

وضعیت هر مورد: `TODO → IMPLEMENTED → TESTED → PRODUCT OWNER ACCEPTED → FROZEN`

---

## 1) Baseline و مستندات
- [x] Consolidate قوانین اولیه و ثانویه
- [x] اعمال اولیت Secondary
- [x] رفع ابهام R — `BASE_R_USD=6` از `ACTUAL_STOP_DISTANCE` جدا شد
- [x] تعریف نهایی Strict Pullback Trend
- [x] تعریف TP Extension یک‌مرحله‌ای
- [x] تعریف Pre-Zone Trigger — Baseline 1 دلار، Crossing-based

## 2) Contract Testهای سریع در Python
- [x] Trend bootstrap — `NONE → N1 → N2 → N3` بدون Carry روز قبل
- [x] Tick event order — Coordinator Trend و Touch را به‌ترتيب به‌روزرسانی می‌کند
- [x] Breakout strict buffer — `Close > High+1` و `Close < Low-1`
- [x] Breakout engagement — Open داخل Zone، Touch جهت‌دار، Reset هر M15، Tick Gap
- [x] Reversal Market Touch — Tick-real، Market-only، Wick penetration، Multi-Zone gap
- [x] Reversal daily usage — Normal max1، High max2
- [x] Reversal usage commit — Signal مصرف نمی‌کند؛ Market Order مصرف می‌کند
- [x] Duplicate reversal — یک Zone/Direction در یک M15 فقط یک Signal
- [x] One new order per candle — اولین تلاش Slot کندل را مصرف می‌کند
- [x] Pullback window — فقط `t+1..t+5`
- [x] Multiple PB per BO — اولین Fill Parent را نمی‌بندد
- [x] Pullback usage — Normal1/High∞، استقلال Consumption از Reversal
- [x] Conservative penetration — نفوذ 0.20، Entry روی Broken Edge، Retry
- [x] Strict Trend closed candles — Doji/مخالف شکست می‌خورد
- [x] Strict Trend current candle — Buy `Bid>Open`، Sell `Ask<Open`
- [x] Same-Bar PB→Trigger
- [x] Pre-Zone Trigger 1$ — نسبت به Zone حامل TP جاری
- [x] Opposite Reversal block — فقط با Strict Trend معتبر
- [x] One-step TP extension — Restore قبل از TP اولیه، Market Close بعد از عبور
- [x] Free Space definition — `<=3` Block، فقط `>3` مجاز
- [x] Initial Stop — Stop Zone، Cap 6 دلار
- [x] Initial Target — اولین Zone حداقل 6 دلار دورتر
- [x] Native RF — Break-even با cash-per-price و هزینه Native
- [x] Profit Protection — Xهای مت بدون سقف، بدون SL loosening
- [x] Capital limits — 0.01 lot، max3/max5 برای 200/300
- [x] Daily/Portfolio Risk — Net Realized guard و GROSS15
- [x] Session safety — پنج دقیقه قبل از پایان Session
- [x] Restart fail-closed — persisted activation day

Gate: همه Contract Testهای بالا PASS.

---

## 3) Regression هدفمند MVP
- [x] Trend Bootstrap — Sticky تاریخی از Gate MVP حذف شد
- [x] Normal/High — هر دو Priority جزء ثابت Strategy
- [x] FreeSpace 3 — `<=3 Block / >3 Allow` در Python و MQL اعمال شد
- [x] Strict Trend examples — fixtureهای deterministic
- [x] TP Extension A/B — attempt/fill ثابت، تغییر net فقط `+0.14 USD`
- [x] Safety regression — TP هیچ‌یک از Daily/GROSS15/Session/Restart gateها را دور نزد

Gate: اختلاف اجرایی بدون توضیح = صفر.

---

## 4) Python ↔ MT5 Equivalence
- [x] Freeze test vectors — 19 vector، lifecycle و causal Tick order
- [x] Python replay — causal runner، UTC export/normalization، fixture-driven Fill/Reject/Close/Modify/Cancel
- [x] MT5 Real Tick acceptance — یک روز، Restart و 23 روز
- [x] MQL multi-day lifecycle robustness — 23 روز، صفر failure/SL-loosen/exposure
- [x] اختلاف‌های Scope فعال با `RULE / CODE / DATA / TEST_CONFIG` طبقه‌بندی می‌شوند

Gate: صفر اختلاف توضیح‌نشده.

---

## 5) Final MT5 Acceptance
- [x] Broker/Symbol specification — Contract size، Tick size/value، Stops/Freeze level، Session، Cost model
- [x] سناریوی 200 دلار — 0.01/max3: 10 attempt، 8 accepted، 3 Breakout accepted، max position=1، failed=0
- [x] سناریوی 300 دلار — 0.01/max5: 17 attempt، 15 accepted، 5 Breakout accepted، max position=1، failed=0
- [x] Technical QA — صفر SL-loosen، صفر exposure بعد Session و same-day restart
- [x] Deal PnL audit — نتیجه bounded یک‌روزه از Deal History

Gate: Technical Acceptance PASS.

---

## 6) گزارش جامع نهایی تست
- [x] Evidence ساختاریافته هر اجرای Acceptance شامل نسخه Code/Config/Data و تمام Counterهای فنی
- [x] `docs/FINAL_TEST_REPORT.md` نتایج Profile/Dayها، Gateها، اختلاف‌ها، محدودیت‌ها و روش بازتولید
- [x] گزارش با Compile، 139 تست Python، parity، restart، Breakout/TP lifecycle و MT5 real-tick acceptance همگام شد
- [x] هر گزارش خلاصه بعدی فقط از Evidence ذخیره‌شده تولید می‌شود

---

## 7) Freeze MVP
- [x] Freeze Rulebook — نسخه تأییدشده با Tag نسخه MVP بدون Overwrite قفل شد
- [x] Freeze Code — سورس تأییدشده با Hash و Tag نسخه MVP قفل شد
- [x] Freeze Test Evidence — خلاصه Evidence بازتولیدپذیر نگه‌داری شد
- [x] آماده Shadow/Broker Acceptance — بسته MVP فقط برای ورود به گیت جداگانه Demo/Shadow آماده است؛ هیچ Live فعال نیست