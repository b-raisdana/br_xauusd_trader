# قوانین لغوشده، جایگزین‌شده و موارد آینده

هدف: حفظ قوانین و موارد آینده بدون شلوغ‌کردن Rulebook فعال.

این فایل شامل قوانینی است که در Active Rulebook فعال نیستند.

---

## 1) قوانینی که جایگزین یا لغو شده‌اند

### Trend چسبنده سه‌کندلی قدیمی
- وضعیت: جایگزین شده.
- تعریف روان: نسخه قدیمی همیشه سه کندل مرجع داشت و Trend روز قبل را به روز جدید Carry می‌کرد.
- قانون فعال جایگزین: `DAY_START_TREND_BOOTSTRAP` و `TREND_DIRECTION`.

### Trend مبتنی بر HH/HL/LH/LL با N=3
- وضعیت: رد شده.
- تعریف روان: این روش برای تأیید ساختار به سه کندل M15 نیاز داشت و تشخیص لگ جاری را حدود 45 دقیقه عقب می‌انداخت.
- جایگزین فعال: `DAY_START_TREND_BOOTSTRAP` و `TREND_DIRECTION`.

### مرجع پنج‌ و دوکندلی Trend
- وضعیت: جایگزین شده.
- تعریف روان: در مسیر طراحی، مرجع پنج کندل و سپس دو کندل بررسی شد؛ تصمیم نهایی Baseline روزانه `N1 → N2 → N3` است.
- جایگزین فعال: `DAY_START_TREND_BOOTSTRAP`.

### ارزیاسی Closed-only و Same-Bar بر مبنای PB Entry
- وضعیت: رد شده.
- تعریف روان: Closed-only برای Momentum سریع بیش از حد محافظه‌کارانه بود. مقایسه Same-Bar با PB Entry نیز تعریف کندل‌ها را دوگانه می‌کرد.
- جایگزین فعال: Current Candle فقط در نقطه تصمیم و برای Buy/Sell به‌ترتیب با `Current Bid > M15 Open` و `Current Ask < M15 Open` ارزیاسی می‌شود.
- قوانین فعال: `STRICT_PULLBACK_TREND`, `PRE_ZONE_DECISION_TRIGGER`.

### فاصله‌های قدیمی Pre-Zone برابر 0.20 و 0.50 دلار
- وضعیت: پیشنهادهای جایگزین‌شده.
- تعریف روان: 0.20 و سپس 0.50 دلار برای ایجاد فرصت عملیاتی پیش از Zone پیشنهاد شدند؛ Baseline نهایی MVP برابر 1.00 دلار شد.
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
- تعریف روان: Finalist قبلی Normal Reversal را عملاً Block می‌کرد و Reversal را روی High متمرکز کرده بود.
- علت تغییر: رهبر پروژه صریحاً تایید کرد Normal Reversal دوباره فعال شود؛ Normal حداکثر 1 و High حداکثر 2 بار در روز.
- قوانین فعال جایگزین: `NORMAL_REVERSAL_DAILY_LIMIT` و `HIGH_REVERSAL_DAILY_LIMIT`.

### High Reversal با Initial Risk برابر 1.5 × Base R
- وضعیت: Historical F2 overlay؛ در Rulebook فعال جدید حفظ نشده است.
- تعریف روان: Finalist تاریخی برای High Reversal فاصله ریسک اولیه تا `1.5 × BASE_R_USD = 9 USD` را مجاز می‌کرد.
- نتیجه Migration: به علت اولویت `RULES.md`، multiplier تاریخی وارد Active Rule نمی‌شود؛ فقط برای Regression و Attribution حفظ می‌شود.

### Consumption قدیمی Pullback/Reversal
- وضعیت: بازتعریف شده.
- تعریف روان: نسخه‌های قبلی بین «Window»، «مصرف روزانه Zone» و «Cycle فعال» تفکیک روشنی نداشتند؛ در یک مرحله نیز Pullback عملاً مصرف روزانه نداشت.
- قانون فعال جدید: Reversal و Pullback Counterهای مستقل دارند؛ Normal PB حداکثر 1/day و High PB نامحدود است؛ Window همچنان 5 کندل است.

### بستن Parent Breakout بعد از اولین Pullback
- وضعیت: لغو شده.
- تعریف روان: کد قبلی بعد از اولین PB Fill، Parent Cycle را Complete می‌کرد و Pullback دوم همان Breakout را از بین می‌برد.
- قانون فعال جایگزین: `PULLBACK_MULTI_PER_BREAKOUT`.

### PB Priority / Conflict قدیمی
- وضعیت: نسخه قدیمی رد شده؛ تعریف جدید جایگزین شده.
- تعریف روان: آزمایش قدیمی یک Priority عمومی برای Pullback نسبت به Reversal داشت و در نمونه محدود نتیجه ضعیف/نامطمئن بود.
- قوانین فعال: `STRICT_PULLBACK_TREND`, `BLOCK_OPPOSITE_REVERSAL`.

### Profit Protection قدیمی بر اساس R0
- وضعیت: لغو و جایگزین شده.
- تعریف روان: مدل قدیمی `R0 = |Entry - InitialSL|` تعریف می‌کرد و مراحل `+1R → BE`, `+1.5R → +0.5R`, `+2R → Structural Trail` داشت.
- قانون فعال جایگزین: `PROFIT_PROTECTION` با `BASE_R_USD = 6` و مراحل نامحدود X.

### Free Space ثابت 15 دلار
- وضعیت: `POST-MVP`؛ برای Baseline جدید جایگزین شده و Gate Freeze نیست.
- تعریف روان: Finalist قبلی از `FreeSpace >= 15 USD` استفاده می‌کرد.
- قانون هدف جدید: `FREE_SPACE > 0.5 × BASE_R_USD = 3 USD`؛ مقدار مساوی نیز Block است.

### TP Runnerهای قدیمی
- وضعیت: برای MVP رد شده بودند؛ با TP Extension جدید یکی نیستند.
- تعریف روان: 80 ترکیب Runner/Exit قبلی تست شد و Complexity آن‌ها نسبت به Edge اثبات‌شده زیاد بود.
- قانون جدید: Extension فقط یک مرحله، وابسته به Strict Pullback Trend، با قابلیت Restore/Market Close در صورت شکست Momentum.

### مدل‌های قدیمی SL/TP
- وضعیت: بازنشسته.
- موارد: `b-12` تا `b-17` با مدل‌های SL/TP مختلف.
- علت لغو: چند Exit موازی باعث پیچیدگی و Selection Bias می‌شد.
- جایگزین فعال: `INITIAL_STOP`, `INITIAL_TARGET`, `PROFIT_PROTECTION`.

### هزینه مصنوعی ثابت 1 دلار
- وضعیت: لغو شده.
- تعریف روان: هزینه ثابت با واقعیت Broker و Spread هم‌خوان نبود و می‌توانست دوباره‌شماری ایجاد کند.
- جایگزین: `NATIVE_COSTS`.

### Carry کردن Position از Session به Session بعدی
- وضعیت: لغو شده.
- تعریف روان: Tail loss بزرگ عمدتاً از عبور Exposure از انتهای Session می‌آمد.
- جایگزین: `SESSION_END_FLATTEN`.

### Restart با ادامه State ناقص
- وضعیت: برای MVP رد شده.
- تعریف روان: Recovery کامل State در نسخه قبلی پیچیده و شکننده بود.
- جایگزین MVP: `RESTART_FAIL_CLOSED`.
- نسخه بهتر آینده: Persistent State Recovery.

---

## 2) موارد تاییدنشده یا منتقل‌شده به بعد از MVP

### Pullback جسورانه
- وضعیت: Post-MVP.
- توضیح: Pullback با منطق Aggressive/Limit جدا از Conservative Baseline.

### تولید یا پیش‌بینی Zone
- وضعیت: Post-MVP / پروژه مستقل Research.
- توضیح: MVP فقط Zone استاد را Input می‌گیرد.

### Buffer پویا برای Breakout
- وضعیت: Post-MVP.
- توضیح: مقایسه Buffer ثابت 1$ با ATR/MTR/Zone-width فقط بعد از داده بیشتر.

### Buffer مستقل برای Reversal / Penetration پویا
- وضعیت: Post-MVP.
- توضیح: بررسی normalization با ATR/MTR/Zone width و Deep Invalidation.

### Breakout carry/retest چندکندلی
- وضعیت: Post-MVP.
- توضیح: Breakout فعلاً Event والد است و Window اصلی روی Pullback تعریف شده.

### Recursive TP Extension
- وضعیت: Post-MVP.
- توضیح: MVP فقط یک مرحله Extension دارد؛ Zone-to-Zone recursive نیاز به Evidence بیشتر دارد.

### بازیابی Persistent State پس از Restart
- وضعیت: Post-MVP.
- توضیح: هدف این است که در Production واقعی بدون Flatten غیرضروری، Day state، Zone usage، BO lineage، PB state و Risk state بازیابی شوند.

### Indicator Filters
- وضعیت: Post-MVP.
- توضیح: RSI/MACD/ADX/EMA فقط پس از Freeze MVP و به‌صورت incremental challenger.

### Dynamic Risk / Lot Sizing / Capital Optimization
- وضعیت: Post-MVP.
- توضیح: MVP حجم ثابت دارد؛ sizing پویا فقط بعد از اثبات Edge.

### Session-specific R / Volatility-adaptive R
- وضعیت: Post-MVP.
- توضیح: Base R فعلاً ثابت 6$ است.

### Time-window ثابت برای معامله
- وضعیت: Post-MVP.
- توضیح: منع عمومی ابتدای بازار رد شد.

### Daily Profit Giveback Guard
- وضعیت: Post-MVP.
- توضیح: قبل از داده Live/Shadow کافی وارد Strategy نمی‌شود.

### Failure Atlas کامل
- وضعیت: Post-MVP.
- توضیح: clustering، counterfactual و تحلیل همه Failureها بعد از تثبیت MVP.

### Strategy 2 و Strategy 3
- وضعیت: خارج از Scope MVP فعلی.
- توضیح: در صورت شروع، Project Charter و Rulebook مستقل لازم دارند.

### LIVE_SELECTIVE / SHADOW_FULL Production Modes
- وضعیت: جهت معماری تایید شده.
- توضیح: Research و Execution باید جدا بمانند.

### Signal Quality scoreهای پیچیده
- وضعیت: Post-MVP.
- توضیح: High/Normal و Free Space ساده اولویت دارند.

### Zone نهایی با عرض بزرگ‌تر از Base R
- وضعیت: Post-MVP.
- توضیح: پس از Freeze بررسی شود.

### تحلیل Stacking چند Pullback
- وضعیت: QA/Post-MVP.
- توضیح: اگر چند Pullback روی یک Zone+Direction هم‌زمان یا پشت‌سرهم رخ دهند، فعلاً فقط برای Audit تگ می‌شوند.

### Sensitivity مدل Profit Protection قدیمی
- وضعیت: لغو شده.
- توضیح: آزمایش nearby ratioهای مدل `b-29` دیگر ارزش مستقیم ندارد.

---

## 3) خلاصه قوانین فعال فعلی

قوانین فعال MVP در `docs/RULES.md` تعریف شده‌اند. این فایل فقط قوانینی را که در فعال نیستند نگه می‌دارد.

Statuses: `PASS`, `FAIL`, `NOT_RUN`, `BLOCKED`, `NOT_APPLICABLE`.
