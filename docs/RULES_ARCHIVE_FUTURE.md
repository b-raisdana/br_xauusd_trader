# قوانین لغوشده، جایگزین‌شده و موارد آینده

نسخه: v2 — Consolidated Migration  
هدف: حفظ کامل حافظه پروژه بدون شلوغ‌کردن Rulebook فعال.

این فایل برای مراجعه تاریخی است. هیچ مورد این فایل نباید صرفاً به علت وجود در Archive وارد کد شود.

---

## 1) قوانین قبلی که جایگزین یا لغو شده‌اند

### Trend چسبنده سه‌کندلی قدیمی
- وضعیت: جایگزین شده.
- توضیح روان: نسخه قدیمی همیشه سه کندل مرجع داشت و Trend روز قبل را به روز جدید Carry می‌کرد.
- علت تغییر: قانون ثانویه تاییدشده، Bootstrap روزانه `NONE → N1 → N2 → N3` را جایگزین کرد.
- قانون فعال جایگزین: `DAY_START_TREND_BOOTSTRAP` و `TREND_DIRECTION`.
- شناسه قدیمی: `trend-1` / Evidence تاریخی `E-TREND`.
- نکته مهم: آزمایش قبلی Progressive تعداد 18 Reversal مثبت با مجموع حدود +41.30 را حذف کرده بود؛ به همین علت Regression جدید قبل MVP اجباری است.

### Trend مبتنی بر HH/HL/LH/LL با N=3
- وضعیت: رد شده.
- توضیح روان: این روش برای تأیید ساختار به سه کندل M15 نیاز داشت و تشخیص لگ جاری را حدود 45 دقیقه عقب می‌انداخت.
- علت رد: تأخیر زیاد و ناتوانی در نمایش حرکت جاری برای منطق این Strategy.
- جایگزین فعال: `DAY_START_TREND_BOOTSTRAP` و `TREND_DIRECTION`.

### مرجع پنج‌ و دوکندلی Trend
- وضعیت: جایگزین شده.
- توضیح روان: در مسیر طراحی، مرجع پنج کندل و سپس دو کندل بررسی شد؛ تصمیم نهایی Baseline روزانه `N1 → N2 → N3` است.
- جایگزین فعال: `DAY_START_TREND_BOOTSTRAP`.

### ارزیابی Closed-only و Same-Bar بر مبنای PB Entry
- وضعیت: رد شده.
- توضیح روان: Closed-only برای Momentum سریع بیش از حد محافظه‌کارانه بود. مقایسه Same-Bar با PB Entry نیز تعریف کندل‌ها را دوگانه می‌کرد.
- جایگزین فعال: Current Candle فقط در نقطه تصمیم و برای Buy/Sell به‌ترتیب با `Current Bid > M15 Open` و `Current Ask < M15 Open` ارزیابی می‌شود.
- قوانین فعال: `STRICT_PULLBACK_TREND`, `PRE_ZONE_DECISION_TRIGGER`.

### فاصله‌های قدیمی Pre-Zone برابر 0.20 و 0.50 دلار
- وضعیت: پیشنهادهای جایگزین‌شده.
- توضیح روان: 0.20 و سپس 0.50 دلار برای ایجاد فرصت عملیاتی پیش از Zone پیشنهاد شدند؛ Baseline نهایی MVP برابر 1.00 دلار شد.
- نکته: `PULLBACK_PENETRATION = 0.20 USD` قانون دیگری است و لغو نشده است.
- جایگزین فعال: `PRE_ZONE_TRIGGER_DISTANCE = 1.00 USD`.

### Block دائمی Reversal در Pre-Trigger و TP Extension برگشت‌ناپذیر
- وضعیت: رد شده.
- علت رد: Reversal با Market Order در Touch واقعی Zone ایجاد می‌شود و پس از شکست Momentum، نگه‌داشتن TP دورتر ریسک بی‌دلیل ایجاد می‌کند.
- جایگزین فعال: `BLOCK_OPPOSITE_REVERSAL` فقط در Touch واقعی؛ `EXTEND_PULLBACK_TP` با Restore یا Market Close.

### Grid Search زودهنگام برای Pre-Zone Distance
- وضعیت: رد شده در داده فعلی.
- علت رد: Sample محدود است و جست‌وجوی گسترده روی 0.1/0.2/0.3/0.5 و مقادیر مشابه احتمال Overfit را بالا می‌برد.
- تصمیم فعلی: تست Failure Caseهای مشخص با Baseline یک دلار، بدون ادعای Optimal بودن.

### محدودیت قدیمی Reversal فقط روی High Zone
- وضعیت: لغو شده.
- توضیح روان: Finalist قبلی Normal Reversal را عملاً Block می‌کرد و Reversal را روی High متمرکز کرده بود.
- علت تغییر: رهبر پروژه صریحاً تایید کرد Normal Reversal دوباره فعال شود؛ Normal حداکثر 1 و High حداکثر 2 بار در روز.
- قوانین فعال جایگزین: `NORMAL_REVERSAL_DAILY_LIMIT` و `HIGH_REVERSAL_DAILY_LIMIT`.
- شناسه‌های تاریخی مرتبط: `b-24`, `EXP-REV-HIGH-01`, `MVP-BL-01`.
- Evidence تاریخی: Normal Forward حدود -108.46 / PF0.794 و High Forward حدود +18.96 / PF1.297؛ بنابراین Attribution جداگانه در Regression لازم است.

### High Reversal با Initial Risk برابر 1.5 × Base R
- وضعیت: Historical F2 overlay؛ در Rulebook فعال جدید حفظ نشده است.
- توضیح روان: Finalist تاریخی برای High Reversal فاصله ریسک اولیه تا `1.5 × BASE_R_USD = 9 USD` را مجاز می‌کرد.
- تعارض: `INITIAL_STOP` فعال فعلی سقف پایه 6 دلار را برای Stop تعریف می‌کند و استثنای High را تکرار نکرده است.
- نتیجه Migration: به علت اولویت `RULES.md`، multiplier تاریخی وارد Active Rule نمی‌شود؛ فقط برای Regression و Attribution حفظ می‌شود.
- مرجع تاریخی: F2 / `XAUUSD_EA_MVP_F2_AR_OPS_01_v0_1.mq5`.

### Consumption قدیمی Pullback/Reversal
- وضعیت: بازتعریف شده.
- توضیح روان: نسخه‌های قبلی بین «Window»، «مصرف روزانه Zone» و «Cycle فعال» تفکیک روشنی نداشتند؛ در یک مرحله نیز Pullback عملاً مصرف روزانه نداشت.
- قانون فعال جدید: Reversal و Pullback Counterهای مستقل دارند؛ Normal PB حداکثر 1/day و High PB نامحدود است؛ Window همچنان 5 کندل است.
- شناسه‌های قدیمی: `b-25`, `b-26`, `SEC-PB-02`, `SEC-PB-03`.

### بستن Parent Breakout بعد از اولین Pullback
- وضعیت: لغو شده.
- توضیح روان: کد قبلی بعد از اولین PB Fill، Parent Cycle را Complete می‌کرد و Pullback دوم همان Breakout را از بین می‌برد.
- قانون فعال جایگزین: `PULLBACK_MULTI_PER_BREAKOUT`.

### PB Priority / Conflict قدیمی
- وضعیت: نسخه قدیمی رد شده؛ تعریف جدید جایگزین شده.
- توضیح روان: آزمایش قدیمی یک Priority عمومی برای Pullback نسبت به Reversal داشت و در نمونه محدود نتیجه ضعیف/نامطمئن بود.
- Evidence قدیمی: 9 Reversal اجراشده در Conflictهای سخت، حدود -21.11 / PF0.417؛ Forward conflict کافی نبود.
- علت تغییر: قانون جدید فقط در Momentum اکید، در نقاط تصمیم مشخص و با بررسی Current Candle عمل می‌کند.
- قوانین فعال: `STRICT_PULLBACK_TREND`, `BLOCK_OPPOSITE_REVERSAL`.
- شناسه تاریخی: `EXP-CONFLICT-01`, `SEC-CONFLICT-01`.

### Profit Protection قدیمی بر اساس R0
- وضعیت: لغو و جایگزین شده.
- توضیح روان: مدل قدیمی `R0 = |Entry - InitialSL|` تعریف می‌کرد و مراحل `+1R → BE`, `+1.5R → +0.5R`, `+2R → Structural Trail` داشت.
- علت تغییر: در Strategy فعلی `BASE_R_USD` یک ثابت تجربی 6 دلاری است و رهبر پروژه مدل عمومی پله‌ای را تایید کرد.
- قانون فعال جایگزین: `PROFIT_PROTECTION` با `BASE_R_USD = 6` و مراحل نامحدود X.
- شناسه قدیمی: `b-29`, `SEC-RISK-01`.

### Free Space ثابت 15 دلار
- وضعیت: `POST-MVP`؛ برای Baseline جدید جایگزین شده و Gate Freeze نیست.
- توضیح روان: Finalist قبلی از `FreeSpace >= 15 USD` استفاده می‌کرد.
- قانون هدف جدید: `FREE_SPACE_MINIMUM = 0.5 × BASE_R_USD = 3 USD`.
- علت: قانون ثانویه جدید اولویت دارد؛ هر مقایسه هدفمند با Space15 فقط پس از MVP و بدون Grid Search انجام می‌شود.
- شناسه‌های تاریخی: `EXP-ZONE-CONTEXT-01`, `MVP-BL-01`, `SEC-FS-01`.

### TP Runnerهای قدیمی
- وضعیت: برای MVP رد شده بودند؛ با TP Extension جدید یکی نیستند.
- توضیح روان: 80 ترکیب Runner/Exit قبلی تست شد و Complexity آن‌ها نسبت به Edge اثبات‌شده زیاد بود.
- قانون جدید: Extension فقط یک مرحله، وابسته به Strict Pullback Trend، با قابلیت Restore/Market Close در صورت شکست Momentum.
- شناسه تاریخی: `EXP-PB-RUNNER-01`, `e-6`.

### مدل‌های قدیمی SL/TP
- وضعیت: بازنشسته.
- موارد:
  - `b-12`: SL=6$, TP=6$.
  - `b-13`: SL=6$, TP=9$.
  - `b-14`: SL=6$, TP=12$.
  - `b-15`: Dynamic Aggressive.
  - `b-16`: Dynamic Conservative.
  - `b-17`: برنامه انتخاب برنده بین پنج مدل.
- علت لغو: چند Exit موازی باعث پیچیدگی و Selection Bias می‌شد.
- جایگزین فعال: `INITIAL_STOP`, `INITIAL_TARGET`, `PROFIT_PROTECTION`.

### هزینه مصنوعی ثابت 1 دلار
- وضعیت: لغو شده.
- توضیح روان: هزینه ثابت با واقعیت Broker و Spread هم‌خوان نبود و می‌توانست دوباره‌شماری ایجاد کند.
- جایگزین: `NATIVE_COSTS`.
- شناسه تاریخی: `b-20`, `e-9`.

### Carry کردن Position از Session به Session بعدی
- وضعیت: لغو شده.
- توضیح روان: Tail loss بزرگ عمدتاً از عبور Exposure از انتهای Session می‌آمد.
- جایگزین: `SESSION_END_FLATTEN`.
- Evidence: Carry حدود -91.35؛ ALL_FLAT حدود +72.13 و lossهای >2R از 6 به 0 رسید.
- شناسه: `AR-SESSION-01`, `E-R2`.

### Restart با ادامه State ناقص
- وضعیت: برای MVP رد شده.
- توضیح روان: Recovery کامل State در نسخه قبلی پیچیده و شکننده بود.
- جایگزین MVP: `RESTART_FAIL_CLOSED`.
- نسخه بهتر آینده: Persistent State Recovery.

---

## 2) موارد تاییدنشده یا منتقل‌شده به بعد از MVP

### Pullback جسورانه
- وضعیت: Post-MVP.
- توضیح: Pullback با منطق Aggressive/Limit جدا از Conservative Baseline.
- شناسه‌های قدیمی: `b-7`, `b-27`, بخشی از `b-28`.

### تولید یا پیش‌بینی Zone
- وضعیت: Post-MVP / پروژه مستقل Research.
- توضیح: MVP فقط Zone استاد را Input می‌گیرد.
- شناسه: `e-2`, `EXP-ZONE-REACTION-01`.

### Buffer پویا برای Breakout
- وضعیت: Post-MVP.
- توضیح: مقایسه Buffer ثابت 1$ با ATR/MTR/Zone-width فقط بعد از داده بیشتر.
- شناسه: `e-4`, `EXP-BO-01`, `EXP-CONSTANT-FORMULA-01`.

### Buffer مستقل برای Reversal / Penetration پویا
- وضعیت: Post-MVP.
- توضیح: بررسی normalization با ATR/MTR/Zone width و Deep Invalidation.
- شناسه: `e-3`, `EXP-PB-PENETRATION-01`.

### Breakout carry/retest چندکندلی
- وضعیت: Post-MVP.
- توضیح: Breakout فعلاً Event والد است و Window اصلی روی Pullback تعریف شده.
- شناسه: `e-5`, `EXP-BO-01`.

### Recursive TP Extension
- وضعیت: Post-MVP.
- توضیح: MVP فقط یک مرحله Extension دارد؛ Zone-to-Zone recursive نیاز به Evidence بیشتر دارد.

### بازیابی Persistent State پس از Restart
- وضعیت: Post-MVP.
- توضیح: هدف این است که در Production واقعی بدون Flatten غیرضروری، Day state، Zone usage، BO lineage، PB state و Risk state بازیابی شوند.

### Indicator Filters
- وضعیت: Post-MVP.
- توضیح: RSI/MACD/ADX/EMA فقط پس از Freeze MVP و به‌صورت incremental challenger.
- شناسه: `POST-IND-01`.

### Dynamic Risk / Lot Sizing / Capital Optimization
- وضعیت: Post-MVP.
- توضیح: MVP حجم ثابت دارد؛ sizing پویا فقط بعد از اثبات Edge.
- شناسه‌ها: `EXP-CAPITAL-01`, بخشی از `e-10/e-11`.

### Session-specific R / Volatility-adaptive R
- وضعیت: Post-MVP.
- توضیح: Base R فعلاً ثابت 6$ است؛ تغییر براساس Session/Volatility بدون داده بیشتر ریسک overfit دارد.
- شناسه: `e-15`, `EXP-SESSION-R-01`.

### Time-window ثابت برای معامله
- وضعیت: Post-MVP.
- توضیح: منع عمومی ابتدای بازار رد شد؛ تحلیل ساعت‌های مناسب فقط بعد از Broker mapping و داده بیشتر.
- شناسه‌ها: `e-12`, `e-13`.

### Daily Profit Giveback Guard
- وضعیت: Post-MVP.
- توضیح: قبل از داده Live/Shadow کافی وارد Strategy نمی‌شود.
- شناسه: `POST-GIVEBACK-01`.

### Failure Atlas کامل
- وضعیت: Post-MVP.
- توضیح: clustering، counterfactual و تحلیل همه Failureها بعد از تثبیت MVP.
- شناسه: `POST-FAILURE-01`.

### Strategy 2 و Strategy 3
- وضعیت: خارج از Scope MVP فعلی.
- توضیح: در صورت شروع، Project Charter و Rulebook مستقل لازم دارند.
- شناسه‌ها: `e-1`, `e-8`.

### LIVE_SELECTIVE / SHADOW_FULL Production Modes
- وضعیت: جهت معماری تایید شده؛ Broker-Live certification بعد از MVP.
- توضیح: Research و Execution باید جدا بمانند؛ جزئیات Mode switch و Telemetry در Broker Acceptance تکمیل می‌شود.
- شناسه: `AR-MVP-01`.

### Signal Quality scoreهای پیچیده
- وضعیت: Post-MVP.
- توضیح: High/Normal و Free Space ساده اولویت دارند؛ scoreهای ترکیبی با sample کم می‌توانند overfit شوند.
- شناسه: `EXP-SIGNAL-QUALITY-01`.

### تحلیل Stacking چند Pullback
- وضعیت: QA/Post-MVP؛ Rule معاملاتی فعال نیست.
- توضیح: اگر چند Pullback روی یک Zone+Direction هم‌زمان یا پشت‌سرهم رخ دهند، فعلاً فقط برای Audit تگ می‌شوند؛ Block عمومی بدون Evidence اضافه نمی‌شود.
- شناسه: `QA-PB-STACK`.

### Sensitivity مدل Profit Protection قدیمی
- وضعیت: لغو شده.
- توضیح: آزمایش nearby ratioهای مدل `b-29` دیگر ارزش مستقیم ندارد چون خود مدل R0 جایگزین شده است. هر Sensitivity آینده باید روی `PROFIT_PROTECTION` جدید و فقط با داده بیشتر انجام شود.
- شناسه: `EXP-B29-01`.

---

## 3) آزمایش‌های تاریخی که بسته شده‌اند ولی نتیجه‌شان باید حفظ شود

### Trend Initialization Screen (`EXP-TREND-01`)
Sticky قدیمی در تست قبلی بهتر از Progressive بود؛ 18 Reversal مثبت حذف نشدند. با وجود این، قانون ثانویه جدید Bootstrap روزانه را تایید و Sticky را رد کرده است؛ نتیجه تاریخی فقط آرشیوی است و Regression جدید Gate MVP نیست.

### Pullback Window (`EXP-PB-WINDOW-01`)
N=5 حفظ شد. N3 در All بهتر به نظر می‌رسید ولی Forward ضعیف بود؛ N7/N9 نیز بدتر شدند.

### Pullback Reuse (`EXP-PB-REUSE-01`)
Normal1/High∞ همراه Context قبلی نتیجه مثبت‌تری داشت. بخش مصرف Normal1/High∞ در Rule جدید حفظ شده، اما FreeSpace15 جایگزین شده و باید دوباره Validate شود.

### Reversal High Reuse (`EXP-REV-HIGH-01`)
Later touchها در داده قدیمی از first-touch بهتر بودند؛ max2 برای High تایید شد. Rule جدید Normal1/High2 باید Attribution مستقل بگیرد.

### Zone Context (`EXP-ZONE-CONTEXT-01`)
High و FreeSpace15 در داده محدود Edge بهتری نشان دادند؛ Normal ضعیف بود. این Evidence به معنی ممنوعیت Normal در Rule جدید نیست، ولی Regression قبل MVP را ضروری می‌کند.

### Python / MT5 Architecture (`EXP-EXEC-ARCH-01`)
Policy حفظ می‌شود: Python برای Screening/Replay، MT5 Real Tick برای Final Acceptance.

### Session schedule تاریخی MetaQuotes-Demo
در شاخه تاریخی، Session دوشنبه تا جمعه `00:00 → 23:00` و cutoff برابر `22:55` گزارش شده بود. این فقط Evidence محیط تاریخی است؛ Rule فعال باید Session را از Symbol/Broker بخواند و ساعت را Hard-code نکند.

---

## 4) خلاصه Evidenceهای مهم قدیمی

| Evidence | خلاصه |
|---|---|
| E-R0 | Compile 0/0؛ Control حدود +45.44، 37 trades، PF 1.39 |
| E-R2 | Carry -91.35؛ PB_FLAT +62.90؛ ALL_FLAT +72.13؛ >2R از 6 به 0 |
| E-ZONE | 2343 event؛ 23/23 روز؛ High 337 / Normal 2006؛ match 99.3789% |
| E-EDGE | Combined Forward -89.50/PF0.848؛ High Forward +18.96/PF1.297 |
| E-TREND | Sticky 2343/2343؛ Progressive حذف 18 Reversal با مجموع +41.30 |
| E-PBW | N5 +30.01/PF1.034؛ N3 Forward -33.27/PF0.897 |
| E-PBC | Normal1/High∞ + Space15: All +93.75/PF1.514؛ Forward +43.84/PF1.855 |
| E-REV | 207/207 replay؛ Actual +42.12 vs replay +42.07 |
| E-FINAL | F2 حدود +143.59/PF1.44 در Finalist قدیمی |
| E-B23 | $200/$300: 0 margin block؛ max concurrency 3 |
| E-RISK | GROSS15: $200 +183.98/PF1.678؛ $300 +158.72/PF1.535 |
| E-OPS | 4/4 restart behavior؛ 0 same-day post-restart fill؛ 0 flatten/cancel fail |

این اعداد Evidence تاریخی‌اند، نه تضمین عملکرد آینده و نه مجوز تغییر Rule بدون فرآیند تایید.

---

## 5) نگاشت شناسه‌های قدیمی به نام‌های جدید قابل فهم

| شناسه قدیمی | نام جدید / وضعیت |
|---|---|
| a-1 | `CANDLE_BULLISH` |
| a-2 | `CANDLE_BEARISH` |
| a-3 | `CANDLE_RANGE` |
| a-4 | `MARKET_TIMEFRAME` |
| a-5 | `ZONE_INPUT` |
| a-6 | `ZONE_ALIAS` |
| a-7 | `ZONE_LINE_ALLOWED` |
| a-8 | `ZONE_MERGE` |
| a-9 | `ZONE_PRIORITY` |
| a-10 | `ZONE_ONLY_ENTRY` |
| trend-1 / SEC-TREND-01 | `DAY_START_TREND_BOOTSTRAP`, `TREND_DIRECTION` |
| trend-2 | `TICK_EVENT_ORDER` |
| b-1 | `REVERSAL_DIRECTIONAL_TOUCH` |
| b-2 | `REVERSAL_WICK_VALIDITY` |
| b-3 / b-4 | `BREAKOUT_VALIDATION` |
| b-8 / SEC-PB-01..03 | `PULLBACK_CONSERVATIVE_ENTRY`, `PULLBACK_WINDOW`, `PULLBACK_MULTI_PER_BREAKOUT`, `PULLBACK_DAILY_USAGE` |
| b-24 / SEC-REV-01/02 | `NORMAL_REVERSAL_DAILY_LIMIT`, `HIGH_REVERSAL_DAILY_LIMIT` |
| b-26 | `SIGNAL_USAGE_INDEPENDENCE` |
| b-29 / SEC-RISK-01 | `PROFIT_PROTECTION` |
| b-30 | `INITIAL_STOP`, `INITIAL_TARGET` |
| b-31 | `REVERSAL_DUPLICATE_GUARD` |
| journal-2 | `BREAKOUT_LINEAGE` |
| SEC-CONFLICT-01 | `STRICT_PULLBACK_TREND`, `BLOCK_OPPOSITE_REVERSAL` |
| SEC-TP-01 | `EXTEND_PULLBACK_TP` |
| SEC-FS-01 | `FREE_SPACE_DEFINITION`, `FREE_SPACE_MINIMUM` |
| AR-SESSION-01 | `SESSION_END_FLATTEN` |
| AR-RISK-01 | `PORTFOLIO_RISK_BUDGET` |
| AR-OPS-01 | `RESTART_FAIL_CLOSED` |
