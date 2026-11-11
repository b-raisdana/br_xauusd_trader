# راهبرد معاملاتی

- نسخه: 1.0؛ قواعد معاملاتی بر اساس پاسخ‌های راهبر تا 2026-11-10 بازبینی شده‌اند؛ اصول پردازش و انتقال داده در 2026-11-11 افزوده شدند.
- این اسناد قواعد موردنظر طرح‌اند؛ مطابقت Python/EA اثبات نشده است.

## جریان مراحل

```text
StrategyContext (bootstrap) → سیگنال → SignalResult → سفارش/اوردر → OrderResult → مدیریت پوزیشن → PositionResult ↺ سیگنال بعدی
```

| مرحله | تنها ورودی | تنها خروجی | بخش‌های کلیدی |
| --- | --- | --- | --- |
| تولید سیگنال | آغاز: `StrategyContext`؛ سپس فقط `PositionResult` قبلی | `SignalResult` | [روند](TradingStrategy.Signals.v1.0.md#روند)، [ریورسال و پولبک](TradingStrategy.Signals.v1.0.md#تولید-سیگنال)، [RSI/MACD](TradingStrategy.Signals.v1.0.md#تأیید-rsi) |
| تولید سفارش/اوردر | فقط `SignalResult` | `OrderResult` | [بودجه و حجم](TradingStrategy.Orders.v1.0.md#بودجه-و-حجم)، [SL/TP و LIMIT](TradingStrategy.Orders.v1.0.md#قواعد-سفارش)، [سشن‌ها](TradingStrategy.Orders.v1.0.md#همپوشانی-سشنها-بر-پایه-utc) |
| مدیریت پوزیشن | فقط `OrderResult` | `PositionResult` | [ورود معکوس](TradingStrategy.PositionManagement.v1.0.md#تنها-پوزیشن-و-ورود-معکوس)، [زمان‌بندی و بستن](TradingStrategy.PositionManagement.v1.0.md#زمانبندی-و-بستن)، [حفاظت و ثبت نتیجه](TradingStrategy.PositionManagement.v1.0.md#sl-tp-و-نتیجه) |

## قرارداد جریان داده

پس از `StrategyContext` اولیه، هر مرحله فقط خروجی مرحلهٔ بلافصل قبل را می‌گیرد؛ خواندن موازی از بازار، حساب، ذخیره‌سازی یا مرحله‌های دیگر مجاز نیست. `SignalResult` و `OrderResult` باید snapshot تغییرناپذیر زمینهٔ لازم برای مرحلهٔ بعد را حمل کنند. دادهٔ مفقود یا نامعتبر به رد همان مرحله می‌انجامد؛ واکشی پنهانی ممنوع است.

`StrategyContext` فقط برای bootstrap زنجیره ساخته می‌شود؛ سپس `PositionResult` به ورودی چرخهٔ بعدی سیگنال تبدیل می‌شود. snapshotهای جدید بازار/کندل و رویدادهای fill/زمان باید به همان artifact جاری افزوده شوند، نه اینکه stage دادهٔ دیگری بخواند. سازوکار اجرایی انتقال این به‌روزرسانی‌ها هنوز تعیین/تأیید نشده است.

## اصول محاسبات و انتقال داده

- محاسبات راهبرد فقط با عملیات کامل و برداری پایه در pandas روی DataFrame/Series انجام شوند؛ عملیات ستونی، `shift` و `eval` مجازند. NumPy و هر نوع Python iterator/loop/comprehension، پیمایش ردیفی، callback ردیفی و محاسبهٔ جایگزین خارج از pandas ممنوع است.
- همهٔ پارامترهای عددی و تعداد ستون/پنجرهٔ لازم برای محاسبه، از جمله تعداد کندل‌ها یا ستون‌های روند، در پوشهٔ اختصاصی `config/` و مطابق مدل تنظیمات پایه تعریف و اعتبارسنجی شوند. اعداد فعلی defaultهای قابل تنظیم/بهینه‌سازی‌اند؛ هیچ عددی در منطق محاسبه hardcode نشود.
- داده‌های حجیم بین ماژول‌ها با manifest ارجاعی منتقل شوند، نه با کپی DataFrame؛ payload روی دیسک بماند و manifest هویت، schema، index و بخش/مسیر artifact را معرفی کند تا I/O و کپی حافظه کمینه شود.
- DataFrameهای موقت فقط ستون‌های محاسبه‌شدهٔ جدید را به‌شکل incremental نگه دارند؛ ستون‌های DataFrameهای موجود را در آن‌ها کپی نکنید. هنگام نیاز، frameها با index هم‌تراز و به هم نگاشت شوند.

## اسناد تخصصی

- [تولید سیگنال](TradingStrategy.Signals.v1.0.md): ورودی بازار، روند، ریورسال/پولبک، اندیکاتورها و تصمیم‌های باز.
- [تولید سفارش و اوردر](TradingStrategy.Orders.v1.0.md): بودجهٔ ریسک، حجم، LIMIT، SL/TP، سشن و تحویل artifact سفارش.
- [مدیریت پوزیشن](TradingStrategy.PositionManagement.v1.0.md): پوزیشن یگانه، بستن، ورود معکوس، حفاظت و ثبت نتیجه.

## محدودیت پذیرش

این جریان قرارداد طراحی است، نه مدرک parity یا رفتار زنده. روند فعلی EA با روند High/Low کندل‌های بسته‌شدهٔ این طرح معادل نیست. شواهد پذیرش در [ردیاب MT5/Python](todo/MT5-Python.Divergence.md) ثبت می‌شوند.

## منابع پایه

[Zero Lag MACD](https://www.mql5.com/en/code/9993)، [OrderCalcProfit](https://www.mql5.com/en/docs/trading/ordercalcprofit)، [ساعات OANDA](https://www.oanda.com/us-en/trading/hours-of-operation/)، [تغییر ساعت GOV.UK](https://www.gov.uk/when-do-the-clocks-change) و [تغییر ساعت NIST](https://www.nist.gov/pml/time-and-frequency-division/popular-links/daylight-saving-time-dst).
