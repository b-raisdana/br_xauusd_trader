# XAUUSD AR-OPS-01 Restart Safety — FAST v2

این نسخه جایگزین v1 قبلی است. v1 را اجرا نکن.

## چرا سریع‌تر است؟

نسخه قبلی 10 سناریو را هر کدام روی کل 23 روز اجرا می‌کرد:
تقریباً `230 zone-days` Real Tick.

این نسخه:
- فقط 2 Control را روی کل 23 روز اجرا می‌کند؛
- 4 Restart case را فقط روی پنجره‌ی لازم برای وقوع Restart و اثبات Resume روز بعد اجرا می‌کند.

Workload تقریبی:
`56 zone-days`، یعنی حدود **76% کمتر** از v1.

هیچ کاهش کیفیتی در Tick Model انجام نشده؛ تمام Runها همچنان MT5 Real Tick هستند.

## 6 Run

- `$200 GROSS15` full control
- `$300 GROSS15` full control
- `$200` restart while open exposure — 2026.07.29..07.30
- `$300` multi-position restart — 2026.08.07 + later active day
- `$200` flat-after-loss restart — همان پنجره هدفمند
- `$300` Forward restart — 2026.08.20..08.21

Gate:
- دو Control باید GROSS15 قبلی را دقیقاً بازتولید کنند.
- Restart باید همان روز Fail-Closed شود.
- بعد از Restart هیچ Fill جدیدی در همان broker day نباشد.
- روز بعد/روز فعال بعدی Trading باید Resume شود.
- 0 flatten failure / pending cancel failure / risk overflow.
- Regression QA PASS.

## از این مرحله به بعد

روش پیش‌فرض پروژه:
- Full-range Real Tick فقط برای Control/Finalist/Acceptance.
- Edge caseها فقط Targeted-window.
- بعد از PASS من خودکار وارد مرحله بعد می‌شوم و برای تأییدهای از قبل تحت Governance سؤال جداگانه نمی‌پرسم.

## اجرا

فقط:
`RUN_AR_OPS_01_FAST.cmd`

اگر FAIL شد فقط ZIP Evidence را بفرست.
