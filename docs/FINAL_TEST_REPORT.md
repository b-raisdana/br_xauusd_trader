# گزارش جامع نتایج تست MVP

وضعیت: **مرحله ۷ تکمیل؛ Freeze نهایی هنوز وابسته به Gateهای مرحله ۴ و ۵ است**
منبع عددی ماشین‌خوان: `docs/FINAL_TEST_EVIDENCE.json`
قاعده استفاده: هر گزارش خلاصه بعدی باید از این فایل و Evidence همراه آن تولید شود؛ برای گزارش‌گیری مجدد نباید MetaTrader 5 اجرا شود.

## 1) محدوده و Provenance

| مورد | مقدار ثبت‌شده |
|---|---|
| Repository checkpoint موجود | `871189ae632af525361f0041cd08c9206216eaa4` |
| SHA-256 سورس EA | `78970C137D2FA580981026BDBF3413902AC1F55E8B3EC12264F4C58100501AFC` |
| SHA-256 فایل کامپایل‌شده | `4C204E3DC861FFABE0FD9B7BA4BFFFCF042A3A0135810D1BB70FC5252F81490D` |
| MT5 / MetaEditor | build 6151 |
| Python | 3.11.15 |
| Dataset Zone | `data/ranges.csv` |
| Dataset SHA-256 | `D146FE4650EA52DA64B585A7A0EE15D874E68801F12764481E9EF8C773C9F4F3` |
| Zone input | 444 ردیف، 23 Broker Day، 421 Zone ادغام‌شده |
| Contract vectors | 19 مورد، Decimal-string، tolerance در MQL برابر `1e-9` |

Checkpoint بالا والدِ تغییرات این گزارش است؛ Hashهای محتوایی، Config، Dataset و خروجی کامپایل امکان تطبیق دقیق Evidence را فراهم می‌کنند.

## 2) آزمون‌های خودکار موجود

| آزمون | نتیجه | Evidence |
|---|---|---|
| Python suite | PASS | 139 تست |
| Legacy Python syntax | PASS | 9/9 AST parse |
| MQL compile | PASS | صفر Error و صفر Warning |
| قرارداد مشترک Python/MQL | PASS | 19 vector |
| Signal-count parity | PASS | 541,333 Tick و 88 کندل M15 در 2026-08-28؛ اختلاف شمارش صفر |

شمارش برابر Python و MQL در روز مرجع: Breakout=`28`، Reversal=`62` و Pullback=`410,904`. این شمارش Candidate است و به‌تنهایی Fill یا سودآوری را اثبات نمی‌کند.

## 3) نتایج عددی MT5 Real-Tick

| معیار | سرمایه 200 دلار | سرمایه 300 دلار |
|---|---:|---:|
| Lot ثابت | 0.01 | 0.01 |
| سقف Position | 3 | 5 |
| Entry attempt | 14 | 16 |
| Accepted | 12 | 14 |
| Rejected | 2 | 2 |
| Invalid-price reject | 2 | 2 |
| سایر Broker reject | 0 | 0 |
| Net realized PnL | -4.11 USD | -16.03 USD |
| Realized gross loss | 28.68 USD | 40.60 USD |
| بیشترین Position هم‌زمان مشاهده‌شده | 1 | 1 |
| Profit-protection modify | 9 | 9 |
| TP extension / restore / market close | 1 / 1 / 0 | 1 / 1 / 0 |
| Modify reject | 0 | 0 |
| SL-loosen violation | 0 | 0 |
| Exposure نهایی | 0 | 0 |
| Lifecycle failure | 0 | 0 |

Configها به‌ترتیب `tester_200.ini` و `tester_300.ini`، با Real Ticks، Local agent، Remote/Cloud/Live خاموش اجرا شده‌اند. Hash دقیق Configها در Evidence JSON ثبت است.

## 4) Risk، Safety و Execution

- Daily Loss و GROSS15 در قراردادهای Python پاس شده‌اند.
- Session flatten برای هر دو Profile پاس و Exposure نهایی صفر بوده است.
- تمام خواندن‌های Native به Symbol/Magic پروژه محدود بوده‌اند.
- Profit Protection در اجرای ثبت‌شده SL را شل نکرده است.
- مسیر Live Trading در کد جاری عمداً بسته است.
- Same-day Restart پاس شد: صفر Entry attempt، صفر Position مشاهده‌شده، صفر Exposure نهایی و صفر Lifecycle failure.
- مشخصات Tester ثبت شد: digits=2، point/tick-size=0.01، contract=100، tick-value=0.10، min/step volume=0.01، Stops/Freeze=0 و Session روز مرجع 00:00 تا 23:00.

## 5) TP Extension و Lifecycle

قراردادهای pure مربوط به Pre-Zone crossing، Strict Momentum، Extension یک‌مرحله‌ای، Restore و Market Close پاس شده‌اند. در هر دو اجرای بومی، Extension=1 و Restore=1 و Market Close=0 ثبت شد؛ صفر Modify/Close reject رخ داد. صفر بودن Market Close یعنی مسیر در این روز فعال نشده، نه اینکه آن رفتار آماری اثبات شده باشد.

## 6) Gateهای باقی‌مانده

- Regression هدفمند و Multi-day lifecycle parity.
- Metrics کامل عملکرد مانند Drawdown و توزیع Trade، در صورت تولید توسط اجرای نهایی.

Full Quality Gate در 2026-09-08 پاس شد: Ruff، format، mypy، 139 تست Python، `git diff --check`، کامپایل MT5 با صفر خطا/هشدار، سه اجرای پذیرش تک‌روزه، اجرای ۲۳روزه و Evidence ساختاریافته حاضر.

اجرای مهندسی ۲۳روزه 2026-07-29 تا 2026-08-28 نیز PASS شد: 302 attempt، 188 accepted، 114 invalid-price reject، max position=3، cancel/session-close=`2/2`، protection modify=164، TP extend/restore/market-close=`10/3/2` و صفر lifecycle failure، TP reject، SL-loosen و exposure نهایی. این اجرا robustness فنی است و مقایسه کامل Python/MT5 یا ادعای سودآوری نیست.

Attribution همان اجرا: Reversal Normal=`86/86/0` و High=`26/26/0`، Pullback Normal=`146/56/90` و High=`44/20/24` به‌ترتیب attempt/accepted/rejected. QA روز 2026-07-29 نیز با `16/9/7`، net=`+16.33 USD` و صفر failure پاس شد. PnL مستقل هر Priority هنوز ثبت نشده است.

A/B ازپیش‌محدود TP روی همان روز/Config نشان داد شمار Entryها ثابت ماند و Net هر دو Profile فقط `+0.14 USD` تغییر کرد؛ این یک attribution مهندسی یک‌روزه است، نه شواهد سودآوری. Strict Trend و Safety regression پاس‌اند؛ Trend/Normal/FreeSpace attribution و multi-day parity باقی‌اند.

## 7) محدودیت تفسیر

نتایج عددی فعلی فقط یک Broker Day را پوشش می‌دهند و Evidence مهندسی هستند؛ از آنها نباید سودآوری، پایداری آماری یا آمادگی Live نتیجه‌گیری شود. هیچ مقدار ناموجودی در گزارش‌های بعدی تخمین زده نمی‌شود. بررسی بصری Chart و تأیید چشمی رهبر پروژه Gate فعال MVP نیست.

## 8) قرارداد گزارش‌دهی بعدی

Codex برای پاسخ‌های «خیلی کوتاه»، «مدیریتی»، «فنی»، «ریسک»، «عددی» یا «مقایسه Profileها» باید همین گزارش و JSON همراه آن را بخواند و قالب خواسته‌شده را تولید کند. اجرای MT5 فقط وقتی مجاز است که خود Evidence جدید لازم باشد، نه برای بازنویسی یا خلاصه‌سازی نتایج موجود.
