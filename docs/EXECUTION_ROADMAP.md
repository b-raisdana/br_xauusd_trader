# Autonomous MVP Execution Roadmap

این سند مرز وظایف رهبر پروژه و Codex را مشخص می‌کند. گزارش، تست یا Commit میانی درخواست «ادامه بده» ایجاد نمی‌کند.

## V1 Stabilized

### Codex

1. چهار Defect قطعی Runtime/Audit را بدون تغییر Rule اصلاح و با تست قفل کند.
2. Full quality gate و MetaEditor compile را اجرا کند.
3. پس از آزادشدن MT5، smoke ایزوله و Acceptance کامل 23روزه Real-Tick را اجرا کند.
4. Journal، block ledger، Fill/Reject/Cancel، exposure نهایی و نتایج مالی را استخراج و گزارش‌های ساختاریافته را همگام کند.
5. در صورت PASS، یک checkpoint محلی منسجم برای V1 بسازد و بلافاصله وارد V2 شود.

### Project Leader

- فقط همهٔ پنجره‌ها و فرآیندهای MT5 را هنگام درخواست اجرای ایزوله ببندد؛ نیازی به اجرای فرمان یا بررسی Log ندارد.
- برای تست، Compile، رفع Defect، مستندسازی یا Commit محلی پاسخ «ادامه بده» لازم نیست.
- فعال‌سازی Demo/Shadow و مخصوصاً پول واقعی تصمیمی جدا از PASS فنی است.

## V2 Experimental

### Codex

1. شاخهٔ آزمایشی را فقط از V1 Freeze‌شده ایجاد کند.
2. Dataset، بازه، هزینه، Baseline، Variantها و معیارها را پیش از مشاهدهٔ نتیجه قفل کند.
3. همهٔ Variantهای تأییدشده را در یک Batch خودکار پیاده، تست و اجرا کند؛ نتیجهٔ منفی حذف نشود.
4. گزارش کامل اثر مستقل و ترکیبی، PnL، PF، Drawdown، تعداد معامله، Fill/Reject/Block، Tail loss و پایداری روزانه تولید کند.
5. تا تحویل گزارش تصمیم V2 بدون توقف روتین ادامه دهد.

### Project Leader

- فقط پس از دریافت گزارش، مشخص کند کدام Variantها به Rule فعال Production V2 ارتقا پیدا کنند.
- پس از Promotion، Codex پیاده‌سازی نهایی و Full Acceptance را بدون تأییدهای میانی انجام می‌دهد.

## V3 Independent Research

### Codex این Repository

- پس از Freeze V1، Handoff کم‌حجم شامل commit مبنا، hash داده، محدودیت‌ها، معیار OOS و فرمان‌های بازتولید بسازد.

### Account دوم

- روی شاخهٔ مستقل کار کند؛ Astra برای طراحی/Audit، Terra برای پیاده‌سازی و Luna برای استخراج مکانیکی.
- هدف را Robust Out-of-Sample performance قرار دهد، نه بیشینه‌سازی سود In-Sample.

### Project Leader

- فقط دسترسی Account دوم به Repository خصوصی را فراهم کند؛ نتایج V3 بدون Promotion صریح وارد MVP یا Live نمی‌شوند.

## توقف‌های مجاز

Codex فقط برای تعارض Rule تأییدشده، اقدام مخرب، دسترسی/هزینه، آزادکردن برنامهٔ کاربری، Promotion قوانین V2، Demo/Live یا افزایش ریسک متوقف می‌شود.
