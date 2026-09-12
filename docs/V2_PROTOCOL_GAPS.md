# V2 Protocol Gaps — Leader Decision Required

تاریخ: 2026-09-11
مبنا: `mvp-v1-stabilized` / `e7c26e2`

پروتکل Dataset، بازه، هزینه، Baseline، منع Optimization و معیارهای گزارش قفل است؛ اما موارد زیر هنوز تعریف اجرایی یکتا ندارند و حدس‌زدن آن‌ها نتیجه Batch را تغییر می‌دهد:

1. `Reversal shadow-touch`: آیا Candidate فقط counterfactual ثبت شود یا Order واقعی Tester بسازد؟ Touch دقیق همان directional crossing جاری است یا هر حضور wick داخل Zone؟
2. cap برابر `1.5R` برای High Reversal و High Pullback: cap روی فاصله SL، فاصله TP، ریسک نقدی یا تعداد/مصرف اعمال می‌شود؟ `R` ثابت 6 دلار است یا Actual `R0`؟
3. Merge فاصله `<=3` و کنترل عرض Zone: حداکثر عرض مجاز و رفتار Zone پهن (رد، split یا clamp) مشخص نشده است.
4. Trend با Body: مرز مرجع دقیق `max(open,close)/min(open,close)` است، اما تعداد Candle مرجع، bootstrap و رفتار Doji باید صریحاً تأیید شود.
5. directional consumption برای همه خانواده‌ها: سقف هر Direction برای Breakout، Reversal و Pullback و زمان مصرف (Candidate، Attempt یا Fill) مشخص نشده است.
6. momentum context مستقل از Position: زمان ایجاد، کلید هویت، انقضا و شرایط ابطال context پس از بسته‌شدن/لغو Position مشخص نشده است.
7. concurrent-risk بدون realized gross و Daily Loss `40$`: Daily Loss بر net realized و به‌صورت inclusive در `<= -40` فرض می‌شود؛ مشخص شود آیا این تعریف مطلوب است و GROSS gate فقط `open + pending + proposed` را نگه می‌دارد.

تا پاسخ این موارد، اجرای Variantها یا Combined Run می‌تواند Data-mining یا تغییر Rule ناخواسته باشد. هیچ نتیجه V2 پیش از قفل این تعریف‌ها تولید نمی‌شود.
