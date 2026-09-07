# قوانین فعال XAUUSD تا MVP

نسخه: v2 — Consolidated Migration  
وضعیت: Baseline تأییدشده توسط رهبر پروژه؛ پیاده‌سازی و تست‌های مشخص‌شده در `TODO.md` هنوز باید انجام شوند.

## 1) اصل سند

این فایل فقط می‌گوید سیستم هدف MVP **چه رفتاری باید داشته باشد**. قوانین لغوشده، نسخه‌های قبلی و موارد Post-MVP در `RULES_ARCHIVE_FUTURE.md` هستند. Repository مرجع رسمی پروژه است و گفتگو فقط Evidence مهاجرت محسوب می‌شود.

اولویت در صورت تعارض:
1. تصمیم مستقیم جدید رهبر پروژه
2. قوانین ثانویه تاییدشده
3. قوانین اولیه تاییدشده‌ای که با موارد بالا تضاد ندارند

هیچ قانون معاملاتی جدید بدون تایید رهبر پروژه وارد کد نمی‌شود.

قاعده نگارش:
- عنوان فارسی Rule قبل از شناسه فنی Semantic نمایش داده شود.
- شناسه فنی تا حد ممکن شبیه نام Function و قابل فهم باشد.
- Legacy ID فقط به‌عنوان Alias برای Traceability حفظ شود و هویت اصلی Rule نباشد.

---

## 2) ثابت‌های پایه

### واحد پایه استراتژی (`BASE_R_USD`)
- `BASE_R_USD = 6.00 USD`
- این مقدار یک ثابت تجربی Strategy است و **از فاصله واقعی Entry تا Stop محاسبه نمی‌شود**.
- در قوانین فعال هیچ `R` مستقل و مبهمی استفاده نمی‌شود؛ تمام ضرایب صریحاً بر پایه `BASE_R_USD` نوشته می‌شوند.

### فاصله واقعی حدضرر (`ACTUAL_STOP_DISTANCE`)
- تعریف: فاصله واقعی بین Entry و Initial SL.
- این مقدار ممکن است کمتر یا مساوی `BASE_R_USD` باشد و با آن یکی نیست.

### فاصله تصمیم قبل از ناحیه (`PRE_ZONE_TRIGGER_DISTANCE`)
- `PRE_ZONE_TRIGGER_DISTANCE = 1.00 USD`
- این عدد Baseline ثابت برای تست MVP است و به‌عنوان مقدار بهینه فرض نمی‌شود.

### نفوذ لازم برای Pullback (`PULLBACK_PENETRATION`)
- `PULLBACK_PENETRATION = 0.20 USD`
- این عدد مربوط به ورود Conservative Pullback است و با `PRE_ZONE_TRIGGER_DISTANCE` فرق دارد.

---

## 3) تعریف کندل و بازار

### کندل صعودی (`CANDLE_BULLISH`)
کندل بسته‌شده صعودی است اگر `Close > Open`.

### کندل نزولی (`CANDLE_BEARISH`)
کندل بسته‌شده نزولی است اگر `Close < Open`.

### Doji
اگر `Close == Open` باشد کندل نه صعودی است و نه نزولی. در قانون روند اکید، Doji شرط اکید را نقض می‌کند.

### محدوده کندل (`CANDLE_RANGE`)
High تا Low کل دامنه کندل است و بخش خارج از Body، Wick/Shadow است.

### بازار و تایم‌فریم (`MARKET_TIMEFRAME`)
- Symbol: XAUUSD
- منطق کندلی: M15
- Touch، Fill، Spread، SL/TP و Execution داخل کندل: Tick واقعی
- Python برای Research/Screening و QA سریع مجاز است.
- مرجع نهایی پذیرش MVP: MT5 با `Every Tick Based on Real Ticks`.

---

## 4) Zoneها

### ورودی Zone (`ZONE_INPUT`)
- Zoneهای روزانه ورودی سیستم هستند و توسط استاد ارائه می‌شوند.
- تولید خودکار Zone جزو MVP نیست.
- Zoneها برای Broker Day مربوطه Load، Normalize و Sort می‌شوند.
- `Enabled` و `Priority` رعایت می‌شوند.
- Hard Cap برای تعداد Zone وجود ندارد.

### نام‌های معادل (`ZONE_ALIAS`)
Zone، ناحیه، محدوده و خط در این پروژه به یک مفهوم اشاره می‌کنند.

### Zone خطی (`ZONE_LINE_ALLOWED`)
اگر `Low = High` باشد Zone همچنان معتبر است.

### Merge Zoneها (`ZONE_MERGE`)
اگر فاصله لبه‌به‌لبه دو Zone متوالی کمتر از `1.5 USD` باشد، Merge به‌صورت زنجیره‌ای انجام می‌شود و محدوده خروجی همه اعضا را پوشش می‌دهد.

### Priority بعد از Merge (`ZONE_PRIORITY`)
اگر حداقل یکی از اعضای Merge شده `High` باشد، Zone نهایی `High` است؛ در غیر این صورت `Normal`.

### طبقه‌بندی Zone (`ZONE_CLASSIFICATION`)
هر Zone فعال یکی از دو نوع `Normal` یا `High` است و این Priority از ورودی روزانه استاد/داده Zone می‌آید.

### ممنوعیت Entry بدون Signal Zone (`ZONE_ONLY_ENTRY`)
Trend به‌تنهایی مجوز معامله نیست. Entry فقط در اثر Signal معتبر مرتبط با Zone مجاز است.

### درگیرشدن Zone (`ZONE_ENGAGEMENT`)
رفتار معتبر Legacy حفظ می‌شود:
- اگر Open کندل M15 داخل Zone باشد، Zone برای Breakout هر دو جهت Engaged است.
- عبور Bid از پایین به `ZoneLow`، سمت Buy Breakout را Engaged می‌کند.
- عبور Bid از بالا به `ZoneHigh`، سمت Sell Breakout را Engaged می‌کند.
- در Tick Gap چند-Zone مسیر مصنوعی ساخته نمی‌شود؛ فقط Zoneای که قیمت Tick جدید واقعاً داخل آن است Engaged می‌شود.
- Engagement در ابتدای هر کندل M15 Reset و از Open همان کندل دوباره مقداردهی می‌شود.

---

## 5) Trend اصلی سیستم

### شروع Trend در ابتدای روز (`DAY_START_TREND_BOOTSTRAP`)
در هر Broker Day Trend از نو Bootstrap می‌شود:
- کندل اول روز: `TREND_NONE`
- از کندل دوم: مرجع `N=1`
- از کندل سوم: مرجع `N=2`
- از کندل چهارم به بعد: مرجع `N=3`

Trend روز قبل به‌عنوان Trend اولیه روز جدید استفاده نمی‌شود.

### تشخیص جهت Trend (`TREND_DIRECTION`)
با استفاده از N کندل بسته‌شده مرجع:
- اگر Bid زنده بالاتر از بالاترین High مرجع برود: `TREND_UP`
- اگر Bid زنده پایین‌تر از پایین‌ترین Low مرجع برود: `TREND_DOWN`
- در محدوده بین این دو، Trend قبلی همان روز حفظ می‌شود.
- تا قبل از تشکیل Trend معتبر، State برابر `TREND_NONE` است.

### ترتیب پردازش Tick (`TICK_EVENT_ORDER`)
ترتیب ثابت در هر Tick:
1. Update Trend
2. بررسی Directional Touch
3. Evaluate Signal

اگر تغییر Trend و Touch در یک Tick رخ دهند، Signal باید Trend جدید را مصرف کند.

---

## 6) Breakout

### Breakout معتبر (`BREAKOUT_VALIDATION`)
Breakout مستقل از وجود یا عدم وجود Reversal ثبت می‌شود.

Buy Breakout:
- Zone در Candidate/Bar معتبر Engaged شده باشد.
- Trend در Close کندل `UP` باشد.
- `Close > ZoneHigh + 1.00`.

Sell Breakout:
- Zone در Candidate/Bar معتبر Engaged شده باشد.
- Trend در Close کندل `DOWN` باشد.
- `Close < ZoneLow - 1.00`.

Open داخل Zone معتبر است. شرط Buffer به‌صورت Strict اجرا می‌شود.

اگر Reversal مخالف باز باشد و Breakout معتبر همان Zone/جهت تشکیل شود، Reversal مخالف طبق منطق Breakout بسته می‌شود.

### شناسه والد Breakout (`BREAKOUT_LINEAGE`)
هر Breakout یک `BO#` روزانه می‌گیرد. تمام Pullbackهای وابسته باید `parent_breakout_id` همان Breakout را تا پایان چرخه حفظ کنند.

---

## 7) Reversal

### ورود Reversal با Market Order (`REVERSAL_DIRECTIONAL_TOUCH`)
Reversal با **Market Order** و بر اساس Touch جهت‌دار Tick واقعی فعال می‌شود؛ Pending Order از قبل کاشته نمی‌شود.

- اگر Trend `UP` باشد و قیمت از پایین به `ZoneLow` برسد: Candidate برای `Sell Reversal`.
- اگر Trend `DOWN` باشد و قیمت از بالا به `ZoneHigh` برسد: Candidate برای `Buy Reversal`.
- در Tick Gap چند-Zone مسیر مصنوعی بین دو Tick ساخته نمی‌شود.

### Wick Penetration (`REVERSAL_WICK_VALIDITY`)
عبور Shadow/Wick از Zone به‌تنهایی Reversal را باطل نمی‌کند. Breakout فقط با قانون Close + Buffer خودش سنجیده می‌شود.

### سقف Reversal روزانه Normal (`NORMAL_REVERSAL_DAILY_LIMIT`)
هر Normal Zone در هر Broker Day حداکثر **یک Reversal معتبر** دارد؛ مجموع Buy و Sell با هم این ظرفیت را مصرف می‌کنند.

### سقف Reversal روزانه High (`HIGH_REVERSAL_DAILY_LIMIT`)
هر High Zone در هر Broker Day حداکثر **دو Reversal معتبر** دارد؛ مجموع Buy و Sell با هم این ظرفیت را مصرف می‌کنند.

### زمان مصرف سهمیه Reversal (`REVERSAL_USAGE_COMMIT`)
- Signal معتبر که فقط ثبت شده و هیچ Market Order برای آن ارسال نشده است، سهمیه را مصرف نمی‌کند.
- به‌محض ارسال Market Order، سهمیه مصرف می‌شود؛ چه Order/Fill موفق باشد و چه درخواست Market Order ناموفق بماند.
- نتیجه نهایی معامله، سود یا زیان، سهمیه مصرف‌شده را برنمی‌گرداند.

### جلوگیری از Signal تکراری (`REVERSAL_DUPLICATE_GUARD`)
برای ترکیب `Day + M15 Bar + Zone + Direction` بیش از یک Reversal Signal ساخته نمی‌شود.

Buy و Sell در تشخیص Duplicate مستقل‌اند، اما این استقلال **سهمیه روزانه Zone را دور نمی‌زند**. مثال: اگر Normal Zone قبلاً یک Reversal Buy مصرف کرده باشد، Reversal Sell بعدی همان روز نیز به علت پایان ظرفیت روزانه مجاز نیست.

---

## 8) Pullback محافظه‌کارانه

### ورود Pullback (`PULLBACK_CONSERVATIVE_ENTRY`)
- Aggressive Pullback در MVP فعال نیست.
- بعد از Breakout معتبر، قیمت باید حداقل `0.20 USD` داخل Zone نفوذ کند.
- بعد از ثبت Penetration، Entry روی لبه شکسته‌شده Zone انجام می‌شود.
- اگر قیمت دقیق Entry در آن لحظه به علت شرایط Native Broker قابل ثبت نباشد، سیستم می‌تواند در همان Window برای همان قیمت Retry کند.
- Trend Flip به‌تنهایی Cycle را Cancel نمی‌کند.
- Maximum Penetration جداگانه در MVP تعریف نشده است.
- Cycle به روز بعد منتقل نمی‌شود.

### Window پولبک (`PULLBACK_WINDOW`)
Pullback فقط در پنج کندل M15 بعد از Breakout معتبر، یعنی `t+1` تا `t+5`، قابل بررسی است.

### چند Pullback از یک Breakout (`PULLBACK_MULTI_PER_BREAKOUT`)
اولین Pullback Fill باعث بسته‌شدن خودکار Parent Breakout نمی‌شود. تا پایان Window پنج‌کندلی، Pullback معتبر بعدی نیز می‌تواند بررسی شود.

### مصرف روزانه Pullback (`PULLBACK_DAILY_USAGE`)
- Normal Zone: حداکثر یک Pullback Fill در روز.
- High Zone: بدون سقف مصرف روزانه Pullback.
- برای یک `Zone + Direction` هم‌زمان فقط یک Pending/Cycle فعال مجاز است.

### استقلال مصرف Signalها (`SIGNAL_USAGE_INDEPENDENCE`)
Reversal Consumption و Pullback Consumption دو Counter مستقل هستند. مصرف یک خانواده، ظرفیت خانواده دیگر را کم نمی‌کند.

---

## 9) حرکت اکید Pullback، تعارض Reversal و TP Extension

این سه قانون از یک تعریف مشترک استفاده می‌کنند.

### روند اکید پس از Pullback (`STRICT_PULLBACK_TREND`)
هدف این قانون تشخیص Momentum شدید بعد از Pullback است.

برای Pullback Buy روی `Ri` تا Zone بالاتر `Ri+1`:
- اگر Trigger در کندلی بعد از کندل PB رخ دهد، تمام کندل‌های **بسته‌شده بعد از کندل PB** باید Bullish باشند.
- کندل جاری در لحظه تصمیم نیز باید Bullish باشد: `Current Bid > Current M15 Open`.
- اگر Trigger در همان کندل PB رخ دهد، همان کندل جاری با همین معیار `Current Bid > Open` ارزیابی می‌شود.
- Doji یا هر کندل مخالف، Strict Trend را نقض می‌کند.

برای Pullback Sell قواعد متقارن است:
- تمام کندل‌های بسته‌شده بعد از PB باید Bearish باشند.
- کندل جاری در لحظه تصمیم: `Current Ask < Current M15 Open`.

وضعیت کندل جاری فقط در نقاط تصمیم لازم ارزیابی می‌شود؛ نه اینکه در تمام Tickها یک State نویزی روشن/خاموش شود.

### نقطه تصمیم قبل از Zone (`PRE_ZONE_DECISION_TRIGGER`)
Pre-Zone Trigger نسبت به **Zoneای که TP جاری روی آن قرار دارد** تعریف می‌شود؛ شماره Zone ورود یا تعداد Zoneهای ردشده قبل از Target اهمیتی ندارد.

برای Buy با TP جاری روی `TargetZone`:
`Trigger = LowerEdge(TargetZone) - 1.00 USD`

برای Sell با TP جاری روی `TargetZone`:
`Trigger = UpperEdge(TargetZone) + 1.00 USD`

Trigger با اولین Crossing فعال می‌شود؛ Equality لازم نیست. اگر Tick Gap از سطح عبور کند، Trigger رخ‌داده محسوب می‌شود.

این Trigger به‌تنهایی Reversal را Block نمی‌کند؛ فقط نقطه تصمیم برای بررسی Momentum و TP Extension است.

### جلوگیری از Reversal مخالف (`BLOCK_OPPOSITE_REVERSAL`)
Reversal مخالف فقط **هنگام Touch واقعی مرز Zone بعدی** تصمیم‌گیری می‌شود.

در همان لحظه Strict Pullback Trend دوباره بررسی می‌شود:
- اگر هنوز معتبر باشد: Reversal مخالف آن Zone Block می‌شود.
- اگر نقض شده باشد: Reversal طبق قوانین عادی خودش بررسی می‌شود.

برای Buy PB روی `Ri`، این Rule جلوی Sell Reversal روی مرز پایین `Ri+1` را در صورت حفظ Strict Trend می‌گیرد. برای Sell متقارن است.

### تمدید یک‌مرحله‌ای TP (`EXTEND_PULLBACK_TP`)
این Rule باید قبل از MVP پیاده و تست شود.

- فقط زمانی اعمال می‌شود که Zone در حال نزدیک‌شدن، همان Zone مربوط به **TP اولیه فعلی** باشد.
- هر Zoneای که TP جاری روی آن باشد، وقتی قیمت به `PRE_ZONE_DECISION_TRIGGER` همان Zone رسید و Strict Trend معتبر بود، TP به **Zone بلافاصله بعدی در جهت معامله** منتقل می‌شود. محل Zone ورود و شماره Target قبلی در این تصمیم نقشی ندارد.
- Extension برای MVP فقط **یک مرحله** است؛ Recursive Extension جزو MVP نیست.
- اگر Zone بعدی برای Extension وجود نداشته باشد، TP قبلی حفظ می‌شود.

اگر بعد از Extension، Strict Trend نقض شود:
1. اگر قیمت هنوز TP اولیه را لمس/عبور نکرده باشد: TP به مقدار اولیه برگردد.
2. اگر قیمت TP اولیه را قبلاً لمس/عبور کرده باشد: Position فوراً با Market Close بسته شود.

اگر Broker/MT5 نتواند TP جدید را به شکل معتبر Modify کند، TP موجود نباید بدون جایگزین معتبر حذف شود.

---

## 10) Free Space

### تعریف Free Space (`FREE_SPACE_DEFINITION`)
برای Buy روی Zone `Ri`:
`Free Space = LowerEdge(Ri+1) - UpperEdge(Ri)`

برای Sell روی Zone `Ri`:
`Free Space = LowerEdge(Ri) - UpperEdge(Ri-1)`

یعنی فاصله خالی بین لبه Zone ورود و نزدیک‌ترین لبه Zone بعدی در جهت معامله.

### حداقل Free Space (`FREE_SPACE_MINIMUM`)
Rule ثانویه هدف MVP:
`Minimum Free Space = 0.5 × BASE_R_USD = 3.00 USD`

اگر Free Space کمتر از 3 دلار باشد، Entry جدید Reversal/Pullback Block می‌شود و هیچ درخواست Order ارسال نمی‌شود. فاصله دقیقاً 3 دلار مجاز است (`FreeSpace >= 3.00`). این مرز در Python و MQL با تست‌های قطعی Validate شده است.

---

## 11) Initial SL و Initial TP

### حدضرر اولیه (`INITIAL_STOP`)
`BASE_R_USD = 6` سقف فاصله پایه Stop است؛ فاصله واقعی Stop می‌تواند با ساختار Zone کمتر شود.

برای Buy:
- Stop Zone = نزدیک‌ترین Zone پایین‌تر.
- `InitialSL = max(StopZoneHigh, Entry - BASE_R_USD)`

برای Sell:
- Stop Zone = نزدیک‌ترین Zone بالاتر.
- `InitialSL = min(StopZoneLow, Entry + BASE_R_USD)`

اگر Stop Zone لازم وجود نداشته باشد، Trade رد می‌شود.

### حد سود اولیه (`INITIAL_TARGET`)
Target اولین Zone در جهت معامله است که نزدیک‌ترین مرزش حداقل `BASE_R_USD = 6 USD` از Entry فاصله داشته باشد.

Buy:
- Zoneهای بالاتر از Entry به‌ترتیب بررسی می‌شوند.
- Target روی `LowerEdge` اولین Zone واجد شرایط قرار می‌گیرد.

Sell:
- Zoneهای پایین‌تر از Entry به‌ترتیب بررسی می‌شوند.
- Target روی `UpperEdge` اولین Zone واجد شرایط قرار می‌گیرد.

اگر Target واجد شرایط وجود نداشته باشد، Trade رد می‌شود.

مثال Buy: Entry=3400، Zone بعدی از 3404 شروع می‌شود و Zone بعد از آن از 3408. چون فاصله 3404 فقط 4 دلار است، Target نیست؛ 3408 با فاصله 8 دلار اولین Target معتبر است.

---

## 12) محافظت پله‌ای از سود

### Break-even خالص (`RISK_FREE_PRICE`)
`RF` یا Risk-Free Price قیمتی است که بستن معامله در آن، پس از هزینه‌های Native قابل محاسبه Broker/Tester، PnL خالص را تقریباً صفر می‌کند.

### محافظت پله‌ای از سود (`PROFIT_PROTECTION`)
برای هر عدد صحیح `X = 1, 2, 3, ...`:

Buy:
- اگر `Bid >= Entry + X × BASE_R_USD`
- آنگاه `SL = RF + (X - 1) × BASE_R_USD`

Sell:
- اگر `Ask <= Entry - X × BASE_R_USD`
- آنگاه `SL = RF - (X - 1) × BASE_R_USD`

نمونه با `BASE_R_USD = 6`:
- `+1 × BASE_R_USD`: SL به RF
- `+2 × BASE_R_USD`: SL به `RF + 1 × BASE_R_USD`
- `+3 × BASE_R_USD`: SL به `RF + 2 × BASE_R_USD`
- `+4 × BASE_R_USD`: SL به `RF + 3 × BASE_R_USD`
- و به همین شکل ادامه می‌یابد.

SL هیچ‌وقت نباید شل‌تر شود یا به عقب برگردد.

---

## 13) Execution، هزینه و سرمایه

### Order محافظت‌شده از لحظه ایجاد (`ORDER_PROTECTED_FROM_CREATION`)
هر Order باید از زمان ایجاد دارای SL و TP معتبر باشد. نوع Entry (Market/Limit/Stop) نیز در Journal ثبت می‌شود و از Rule همان Signal می‌آید؛ Reversal طبق قانون خودش Market Order است.

### هزینه‌های Native (`NATIVE_COSTS`)
- هزینه مصنوعی ثابت وجود ندارد.
- Spread از Bid/Ask واقعی.
- PnL نهایی از Deal History.
- Commission/Swap/Fee از مقادیر Native Broker/Tester.

### تقریب آموزشی PnL (`PNL_APPROXIMATION_ONLY`)
برای فهم سریع Strategy، در 0.01 lot حرکت 1 دلاری XAUUSD تقریباً معادل 1 دلار PnL ناخالص است؛ این فقط تقریب آموزشی است و Accounting واقعی همیشه از Deal History و مشخصات Native Broker می‌آید.

### حجم ثابت و سقف Position (`FIXED_LOT_AND_CONCURRENCY`)
- حساب مبنا 200 دلار: `0.01 lot` و حداکثر 3 Position هم‌زمان.
- حساب مبنا 300 دلار: `0.01 lot` و حداکثر 5 Position هم‌زمان.
- Dynamic Lot Sizing جزو MVP نیست.

### حداکثر یک Entry جدید در هر کندل (`ONE_NEW_ORDER_PER_CANDLE`)
- در هر کندل M15، EA حداکثر مجاز به ایجاد یک Entry جدید است؛ چه Entry به‌صورت Market Order باشد و چه Pending Order.
- اولین تلاش ایجاد Order در کندل، سهمیه همان کندل را مصرف می‌کند؛ موفق یا ناموفق بودن درخواست اجازه تلاش برای Entry دوم در همان کندل نمی‌دهد.
- Signalهای دیگر همان کندل می‌توانند برای Audit ثبت شوند، اما نباید Order/Position دوم ایجاد کنند.
- این محدودیت جایگزین سهمیه‌های اختصاصی Zone/Signal نیست؛ همه محدودیت‌ها باید هم‌زمان رعایت شوند.

### Daily Realized Loss Guard (`DAILY_REALIZED_LOSS_GUARD`)
برای Strategy Capital زیر 300 دلار، اگر زیان خالص Realized روزانه به 20% سرمایه مبنا برسد:
- Entry جدید تا روز بعد متوقف می‌شود.
- Pendingهای EA Cancel می‌شوند.
- Position باز صرفاً به علت این Rule Force-Close نمی‌شود.

### Portfolio Risk Budget (`PORTFOLIO_RISK_BUDGET`)
Risk تجمعی با محاسبات Native کنترل می‌شود.

Budget هدف MVP: `GROSS_DAILY = 15%` از Strategy Capital Basis.

در محاسبه لحاظ شود:
- Realized gross loss
- Open-position risk تا SL فعلی
- Pending-order reserved risk
- Risk سفارش جدید

Cash Risk با `OrderCalcProfit` و Margin با `OrderCalcMargin` محاسبه می‌شود.

---

## 14) Session و Restart Safety

### پایان Session (`SESSION_END_FLATTEN`)
پنج دقیقه قبل از پایان Session معاملاتی XAUUSD طبق زمان Broker:
- Entry جدید Block شود.
- Pendingها Cancel شوند.
- Pullback Cycleها Cancel شوند.
- تمام Positionهای متعلق به EA بسته شوند.

Session از اطلاعات Symbol/Broker خوانده می‌شود و ساعت محلی Hard-code نمی‌شود.

### Restart امن (`RESTART_FAIL_CLOSED`)
اگر EA در همان Broker Day Restart/Reattach شود:
- Day Lock فعال شود.
- Pendingهای EA Cancel شوند.
- Positionهای EA Flatten شوند.
- تا Broker Day بعدی Fill جدید مجاز نباشد.

این رفتار Baseline MVP برای Demo/Shadow است. بازیابی کامل Persistent State یک موضوع Post-MVP است.

---

## 15) Audit و Evidence نهایی تست

### Journal قابل Trace (`AUDIT_JOURNAL`)
هر Signal/Order/Fill/Close حداقل باید این موارد را ثبت کند:
- Event ID
- نام/ID قانون مرتبط
- Time
- Zone ID
- Signal Type و Direction
- Entry / SL / TP
- Parent Breakout ID برای Pullback
- دلیل Reject/Block در صورت عدم ورود

### گزارش نهایی قابل بازاستفاده (`FINAL_TEST_REPORT`)
- نتیجه هر اجرای نهایی باید به Evidence ساختاریافته و گزارش جامع انسانی منتقل شود.
- گزارش حداقل Dataset/Date range، Config و Hash، Build، Symbol/Session/Cost specification، شمارش Signal/Attempt/Fill/Reject/Close، PnL و Drawdown موجود، Risk/Safety/TP counters، خطاها، Gateها و محدودیت تفسیر را نگه دارد.
- نتیجه مثبت و منفی هر دو ثبت شوند و هیچ مقدار ناموجودی تخمین زده نشود.
- گزارش و Evidence باید برای تولید هر خلاصه بعدی کافی باشند؛ درخواست گزارش مجدد نباید باعث اجرای دوباره MT5 شود.
- بررسی بصری Chart یا تایید چشمی رهبر، Gate فعال MVP نیست.

---

## 16) مواردی که عمداً در Active MVP نیستند

Aggressive Pullback، تولید خودکار Zone، Dynamic Breakout Buffer، Indicator Filters، Dynamic Lot Sizing، Session-specific `BASE_R_USD`، Daily Profit Giveback، Recursive TP Extension، Strategy 2 و Strategy 3 در این فایل Rule فعال نیستند. جزئیاتشان در Archive/Future آمده است.
