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
| Entry attempt | 10 | 17 |
| Accepted | 8 | 15 |
| Rejected | 2 | 2 |
| Invalid-price reject | 2 | 2 |
| سایر Broker reject | 0 | 0 |
| Net realized PnL | -12.27 USD | -5.47 USD |
| Realized gross loss | 25.87 USD | 44.82 USD |
| بیشترین Position هم‌زمان مشاهده‌شده | 1 | 1 |
| Profit-protection modify | 4 | 10 |
| Breakout accepted | 3 | 5 |
| TP extension / restore / market close | 0 / 0 / 0 | 1 / 1 / 0 |
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

قراردادهای pure مربوط به Pre-Zone crossing، Strict Momentum، Extension، Restore و Market Close پاس شده‌اند. پروفایل 300 یک Extension/Restore داشت و اجرای 23روزه Market Close را نیز فعال کرد؛ صفر Modify/Close reject رخ داد.

## 6) Gateهای باقی‌مانده

Gate فنی MVP باز باقی نمانده است. Demo/Shadow و هرگونه Live گیت‌های جداگانه با مجوز رهبر هستند.

Full Quality Gate در 2026-09-08 پاس شد: Ruff، format، mypy، 139 تست Python، `git diff --check`، کامپایل MT5 با صفر خطا/هشدار، سه اجرای پذیرش تک‌روزه، اجرای ۲۳روزه و Evidence ساختاریافته حاضر.

اجرای نهایی ۲۳روزه PASS شد: 308 attempt، 244 accepted، 64 known native reject، 109 Breakout accepted، 14 بستن Reversal مخالف، max position=2، cancel/session-close=`2/3`، protection modify=167، TP=`8/2/2` و صفر failure، unknown reject، SL-loosen و exposure نهایی.

Attribution همان اجرا: Breakout Normal=`100/100/0` و High=`9/9/0`، Reversal Normal=`70/69/1` و High=`19/19/0`، Pullback Normal=`91/39/52` و High=`19/8/11`. QA نهایی 2026-07-29 با `17/15/2`، net=`+67.87 USD` و صفر failure پاس شد.

A/B ازپیش‌محدود TP روی همان روز/Config نشان داد شمار Entryها ثابت ماند و Net هر دو Profile فقط `+0.14 USD` تغییر کرد؛ این یک attribution مهندسی یک‌روزه است، نه شواهد سودآوری. Strict Trend و Safety regression پاس‌اند. Sticky و PnL تفکیکی Priority از Scope حذف و FreeSpace15 به Post-MVP منتقل شده است؛ QA خارجی و multi-day Native parity نیز به‌دلیل نبود مرجع مستقل Gate نیستند.

## 7) محدودیت تفسیر

نتایج عددی فعلی فقط یک Broker Day را پوشش می‌دهند و Evidence مهندسی هستند؛ از آنها نباید سودآوری، پایداری آماری یا آمادگی Live نتیجه‌گیری شود. هیچ مقدار ناموجودی در گزارش‌های بعدی تخمین زده نمی‌شود. بررسی بصری Chart و تأیید چشمی رهبر پروژه Gate فعال MVP نیست.

## 8) قرارداد گزارش‌دهی بعدی

Codex برای پاسخ‌های «خیلی کوتاه»، «مدیریتی»، «فنی»، «ریسک»، «عددی» یا «مقایسه Profileها» باید همین گزارش و JSON همراه آن را بخواند و قالب خواسته‌شده را تولید کند. اجرای MT5 فقط وقتی مجاز است که خود Evidence جدید لازم باشد، نه برای بازنویسی یا خلاصه‌سازی نتایج موجود.
