# گزارش جامع نتایج تست MVP

وضعیت: **V1 Stabilized در 2026-09-11 تأیید شد؛ V2 Experimental در انتظار اجرا است**
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
| Python suite | PASS | 146 تست |
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

Gate فنی V1 باز باقی نمانده است. اجرای Batch قفل‌شده و گزارش تصمیم V2 برای پایان MVP باقی است. Demo/Shadow و هرگونه Live گیت‌های جداگانه با مجوز رهبر هستند.

اجرای تازه V1 روی 23 Broker Day و Real Ticks پاس شد: 249 attempt، 248 accepted، یک Market invalid-stop ثبت‌شده، صفر pending invalid-price، صفر unknown reject، صفر lifecycle failure، صفر SL-loosen و Exposure نهایی صفر. Block ledger شامل 2,425 رکورد بود که با Counter اجرا تطبیق کامل داشت؛ 486 مورد `NATIVE_PENDING_PRICE_WAIT` بدون مصرف Signal/Window ثبت شد. Evidence مستقل در `artifacts/v1_stabilized/evidence.json` قرار دارد. عدد net در Marker ریسک، snapshot روز پایانی است و به‌عنوان PnL کل بازه تفسیر نمی‌شود.

حسابداری کامل همین V1 از Journal بازسازی شد: 248 معامله بسته شامل 54 برد، 188 باخت و 6 سربه‌سر؛ Gross profit=`624.36`، Gross loss=`662.81`، Net=`-38.45 USD`، Profit factor=`0.9420` و Balance محاسباتی از سرمایه 200 دلار برابر `161.55 USD` است. افت سرمایه روی توالی معاملات بسته `150.17 USD` است و معادل equity drawdown داخل معامله در گزارش رسمی MT5 نیست.

مقایسه روزانه توصیفی نشان می‌دهد Final MVP predecessor در همان 23 روز `+74.48 USD` و RISK200_GROSS_15 در 22 روز موجود `+183.98 USD` داشته‌اند. اختلاف V1 با Final MVP برابر `-112.93 USD` است؛ RISK200 برای 2026-08-10 ردیف ندارد و روی 22 روز مشترک V1=`-16.41 USD` و اختلاف V1−Risk=`-200.39 USD` است. چون Rule و Engine نسخه‌ها یکسان نیست، این اعداد A/B کنترل‌شده نیستند. راهنمای نهایی‌سازی، تنظیم تست کوچک، جدول روزانه و inventory کامل فایل‌ها در `docs/V1_FINALIZATION_GUIDE.md` و Workbook خروجی ثبت شده‌اند.

نتیجه Release/Live gate برای V1 برابر **NO-GO** است: مسیر `OrderSend` خارج Strategy Tester عمداً قفل است، نتیجه این بازه منفی و PF کمتر از یک است، Demo/Paper و آزمون disconnect/reconnect/reconciliation/kill-switch اجرا نشده‌اند، parity و هزینه/latency واقعی Broker اثبات نشده و یک Market invalid-stop reject باقی است. هر Limited Live علاوه بر رفع این موارد به حدود rollout/rollback و تأیید صریح رهبر نیاز دارد.

Full Quality Gate در 2026-09-08 پاس شد: Ruff، format، mypy، 139 تست Python، `git diff --check`، کامپایل MT5 با صفر خطا/هشدار، سه اجرای پذیرش تک‌روزه، اجرای ۲۳روزه و Evidence ساختاریافته حاضر.

اجرای نهایی ۲۳روزه PASS شد: 308 attempt، 244 accepted، 64 known native reject، 109 Breakout accepted، 14 بستن Reversal مخالف، max position=2، cancel/session-close=`2/3`، protection modify=167، TP=`8/2/2` و صفر failure، unknown reject، SL-loosen و exposure نهایی.

نتیجه حسابداری همین اجرای Freeze: سرمایه `200.00` به `274.48 USD` رسید؛ Net realized کل ۲۳ روز `+74.48 USD` بود. از 244 درخواست پذیرفته‌شده، 242 Position واقعاً Fill و Close شدند و دو Pending پذیرفته‌شده بدون Fill در پایان Session لغو شدند. جمع PnL روزانه با تغییر Balance و PnL روز 2026-08-28 (`-12.27 USD`) تطبیق کامل دارد.

Attribution همان اجرا: Breakout Normal=`100/100/0` و High=`9/9/0`، Reversal Normal=`70/69/1` و High=`19/19/0`، Pullback Normal=`91/39/52` و High=`19/8/11`. QA نهایی 2026-07-29 با `17/15/2`، net=`+67.87 USD` و صفر failure پاس شد.

A/B ازپیش‌محدود TP روی همان روز/Config نشان داد شمار Entryها ثابت ماند و Net هر دو Profile فقط `+0.14 USD` تغییر کرد؛ این یک attribution مهندسی یک‌روزه است، نه شواهد سودآوری. Strict Trend و Safety regression پاس‌اند. Sticky و PnL تفکیکی Priority از Scope حذف و FreeSpace15 به Post-MVP منتقل شده است؛ QA خارجی و multi-day Native parity نیز به‌دلیل نبود مرجع مستقل Gate نیستند.

## 7) فایل‌های مستقل تحلیل

- `artifacts/final_reporting/final_daily_performance_comparison.csv`: 648 ردیف؛ 23 روز نسخه نهایی و همه 32 سناریوی تاریخی دارای ماتریس روزانه، همراه با اختلاف `final_minus_scenario_usd`. مقایسه Legacy توصیفی است چون Ruleهای آن نسخه‌ها با Rule نهایی یکسان نیست.
- `artifacts/final_reporting/final_event_ledger.csv`: 1,761 رخداد زمان‌دار شامل Attempt، Reject، Fill، Pending trigger/cancel، Modify، Close trigger/request، Close، PnL هر Position و PnL تجمعی روز/کل؛ Request، Rule، Zone و Priority نیز در همان ردیف‌ها موجود است.
- `scripts/build_final_analysis_csv.py`: بازساز Fail-closed؛ فقط وقتی فایل‌های EA/EX5 با Hash نسخه Freeze منطبق باشند و حسابداری `+74.48/-12.27` تطبیق کند خروجی می‌سازد.

## 8) محدودیت تفسیر

نتیجه روزانه نسخه نهایی 23 Broker Day را پوشش می‌دهد و Evidence مهندسی است؛ از آن نباید سودآوری پایدار یا آمادگی Live نتیجه‌گیری شود. سناریوهای Legacy رفتارهای منسوخ دارند، بنابراین Delta روزانه آنها مقایسه توصیفی است و A/B کنترل‌شده محسوب نمی‌شود. هیچ مقدار ناموجودی در گزارش‌های بعدی تخمین زده نمی‌شود. بررسی بصری Chart و تأیید چشمی رهبر پروژه Gate فعال MVP نیست.

## 9) قرارداد گزارش‌دهی بعدی

Codex برای پاسخ‌های «خیلی کوتاه»، «مدیریتی»، «فنی»، «ریسک»، «عددی»، «روزانه»، «معامله‌به‌معامله» یا «مقایسه Profile/Scenario» باید همین گزارش، JSON و دو CSV همراه آن را بخواند و قالب خواسته‌شده را تولید کند. اجرای MT5 فقط وقتی مجاز است که Evidence جدید لازم باشد، نه برای بازنویسی، فیلتر یا خلاصه‌سازی نتایج موجود.
