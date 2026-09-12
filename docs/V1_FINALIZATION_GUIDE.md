# V1 Stabilized — Finalization Guide

تاریخ Evidence: 2026-09-11  
مبنا: `e7c26e2` / `mvp-v1-stabilized`  
وضعیت فنی: **PASS در Strategy Tester**  
وضعیت بازار واقعی: **NO-GO**

## نتیجه V1

- 23 Broker Day، بازه 2026-07-29 تا 2026-08-28، مدل Every Tick Based on Real Ticks.
- سرمایه 200 دلار، حجم 0.01، سقف 3 Position و بیشینه مشاهده‌شده 2.
- 249 تلاش، 248 پذیرش و یک Reversal Market reject با `Invalid stops`.
- 248 معامله بسته: 54 برد، 188 باخت و 6 سربه‌سر.
- Gross profit=`624.36`، Gross loss=`662.81`، Net=`-38.45 USD`، PF=`0.9420` و Balance محاسباتی=`161.55 USD`.
- closed-trade drawdown برابر `150.17 USD` است؛ این عدد equity intratrade drawdown رسمی MT5 نیست.
- صفر Pending invalid-price، unknown reject، lifecycle failure، SL-loosen و final exposure.
- 2,425 Block و 249 Order با Run reconcile شدند؛ 486 مورد `NATIVE_PENDING_PRICE_WAIT` بدون مصرف Signal/Window ثبت شد.
- 146 تست و Full quality gate پاس؛ MetaEditor build 6151 با صفر error/warning.

## مقایسه

Final MVP قبلی در همین 23 روز `+74.48 USD` و RISK200_GROSS_15 در 22 روز موجود `+183.98 USD` ثبت کرده‌اند. V1 نسبت به Final MVP برابر `-112.93 USD` عقب‌تر است. RISK200 برای 2026-08-10 داده ندارد؛ روی 22 روز مشترک، V1=`-16.41` و اختلاف V1−Risk=`-200.39 USD` است.

این مقایسه توصیفی است، نه A/B کنترل‌شده؛ نسخه‌ها Rule/Engine یکسان ندارند. جدول کامل روزبه‌روز و Deltaها در `outputs/v1_final_review/V1_FINAL_REVIEW.xlsx` قرار دارد.

## تست کوچک با تغییر Config

1. یک فایل `config/mt5/*.ini` را با نام جدید کپی کنید؛ Configهای Evidence را overwrite نکنید.
2. برای تست یک‌روزه فقط `FromDate` و `ToDate` را عوض کنید. هر Broker Day باید Zone canonical داشته باشد.
3. این مقادیر را ثابت نگه دارید: `Model=4`, `Optimization=0`, `UseLocal=1`, `UseRemote=0`, `UseCloud=0`, `Visual=0`, `AllowLiveTrading=0`.
4. `InpEnableTrading=false` همیشه بماند. `InpEnableTesterExecution=true` فقط در Strategy Tester مجاز است.
5. سرمایه هماهنگ باشد: `Deposit=200` با `InpStrategyCapital=200.0` یا `300/300.0`. این دو profile به‌ترتیب max3/max5 هستند.
6. Compile: `powershell -ExecutionPolicy Bypass -File .\scripts\compile_mt5.ps1`.
7. تست سریع: `powershell -ExecutionPolicy Bypass -File .\scripts\quality_gate.ps1`.
8. تست MT5: `powershell -ExecutionPolicy Bypass -File .\scripts\run_mt5_tester_acceptance.ps1 -ConfigPath .\config\mt5\YOUR_TEST.ini`.
9. PASS باید `failed=0`، `session_flattened=1`، صفر final exposure/SL-loosen/unknown reject و Journal قابل reconcile داشته باشد.

تغییر تاریخ و profile سرمایه Config ساده است. تغییر Free Space، R، SL/TP، Trend، Signal، Risk یا consumption تغییر Rule است و باید روی شاخه آزمایشی با Protocol قفل‌شده و Full 23-day اجرا شود.

## آیا برای بازار واقعی آماده است؟

خیر. V1 یک baseline فنی Research/Tester است:

- `OrderSend` خارج `MQL_TESTER` عمداً قفل است و EA فعلی Live اجرا نمی‌شود.
- نتیجه 23روزه منفی و PF کمتر از یک است؛ robustness/OOS کافی وجود ندارد.
- G3 Demo/Paper انجام نشده: live feed، lifecycle، disconnect/reconnect، restart، reconciliation و kill switch باید اثبات شوند.
- یک Market invalid-stop reject باید پیش از Demo رفع یا با policy صریح مدیریت شود.
- parity مسیر Live، latency/slippage واقعی Broker و محدودیت‌های venue اثبات نشده است.
- rollout محدود، سقف زیان، rollback و approval صریح رهبر برای G4 لازم است.

## نسخه و نقش فایل‌ها

Sheet `File inventory` در Workbook تحویل، تک‌تک فایل‌های tracked و untracked غیر-ignored را با توضیح دارد. طبقه‌بندی اصلی:

- `src/mt5/`: کد اجرایی V1 Tester؛ `XAUUSD_MVP.mq5` نقطه ورود و `include/*.mqh` ماژول‌های آن هستند.
- `src/xauusd/`: قرارداد، replay و QA پایتون V1/shared؛ ربات Live نیست.
- `tests/`, `scripts/`, `config/mt5/`: آزمون، اتوماسیون و Config جاری V1/shared.
- `artifacts/v1_stabilized/`: Evidence اختصاصی V1.
- `artifacts/final_reporting/`: Evidence Final MVP قبلی برای مقایسه.
- `legacy_reference/`: فقط forensic/regression؛ فعال یا deployable نیست.
- `docs/`: Source of Truth مشترک؛ `.agents/skills/` قرارداد اجرای Codex است، نه Strategy.

هیچ فایل Production V2 در شاخه V1 وجود ندارد. شاخه V2 جدا و از tag تثبیت‌شده V1 مشتق شده است.
