# Fast Test Policy — effective immediately

برای مراحل باقی‌مانده پروژه:

1. Python/static/cache screen قبل از MT5، هر جا از نظر causal execution معتبر باشد.
2. Full-range MT5 Real Tick فقط برای:
   - equivalence controls،
   - finalist واقعی،
   - final acceptance.
3. Failure/restart/edge cases روی date-window هدفمند اجرا می‌شوند، نه کل 23 روز.
4. یک User Run باید تا حد ممکن چند Gate مرتبط را با هم ببندد.
5. بعد از PASS، AI بدون گرفتن تأیید جداگانه وارد Stage مجاز بعدی می‌شود.
6. فقط اگر Strategy/Risk rule جدیدی خارج از Governance قبلی لازم باشد سؤال مطرح می‌شود.
7. هیچ کاهش کیفیت Model مجاز نیست: Final execution همچنان MT5 Real Tick است.

AR-OPS v2 FAST workload:
- v1: 10 × 23 = حدود 230 zone-day execution
- v2: 2 × 23 full controls + targeted 2/3/3/2-day windows = حدود 56 zone-day execution
- کاهش workload تقریبی: 75.7%
