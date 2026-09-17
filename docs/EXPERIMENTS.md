# Experiment Registry

نتایج این فایل Evidence هستند، نه Rule و نه مجوز Live. جزئیات Ruleهای جایگزین‌شده در `RULES_ARCHIVE_FUTURE.md` است.

## نتایج جاری قابل‌بازتولید

### EXP-PARITY-02-SIGNAL-20260828

- Scope: فقط تولید candidate سیگنال؛ بدون Order outcome، هزینه، PnL یا ادعای Strategy acceptance.
- Input: 541,333 Tick بومی `XAUUSD` در UTC/Broker Day `2026-08-28`؛ cache محلی و ignored با SHA-256 برابر `3715b7dc7161d81123725eb381a1d407423e1d23f86c0935892c75295cd665f9`.
- Time basis: تطبیق مستقل پنج Tick، offset دقیق `UTC+00:00`؛ هویت حساب ذخیره یا ثبت نشد.
- Config: M15، Zoneهای canonical با hash ثبت‌شده بالا، merge gap برابر 1.5، current Rules بدون execution outcome.
- Result: Python و MQL برای `88` کندل روی Breakout=`28`، Reversal=`62` و Pullback candidate=`410904` دقیقاً برابر بودند؛ صفر اختلاف شمارشی.
- Interpretation limit: شمار زیاد Pullback ناشی از حالت audit-only بدون broker attempt است؛ Rule می‌گوید candidate بدون request ظرفیت کندل/pending را مصرف نمی‌کند. این نتیجه فقط ترتیب علّی و parity شمارشی را پشتیبانی می‌کند.
- Reproduce: اجرای inert `scripts/run_mt5_contract_smoke.ps1` برای summary MQL، export با `scripts/export_mt5_ticks.py`، سپس `scripts/compare_signal_parity.py` با offset و سه count مورد انتظار.

### EXP-MT5-LIFECYCLE-20260828

- Scope: پذیرش مهندسی bounded برای request، Broker acceptance/rejection، Native binding/outcome، Deal-history risk، profit protection و Session flatten؛ بدون ادعای سودآوری یا مجوز Live.
- Input/config: `XAUUSD` در 2026-08-28، Every Tick Based on Real Ticks، M15، volume ثابت 0.01، profileهای versioned سرمایه 200/max3 و 300/max5؛ local tester only و live/remote/cloud خاموش.
- Result 200: 14 attempt، 12 accepted، 2 invalid-price reject، net realized `-4.11`، gross loss `28.68`، max positions `1`، protection modify=`9`، TP extend/restore=`1/1`، margin/other/modify/TP reject=`0`، SL loosen=`0`، final zero exposure و lifecycle `failed=0`.
- Result 300: 16 attempt، 14 accepted، 2 invalid-price reject، net realized `-16.03`، gross loss `40.60`، max positions `1`، protection modify=`9`، TP extend/restore=`1/1`، margin/other/modify/TP reject=`0`، SL loosen=`0`، final zero exposure و lifecycle `failed=0`.
- Defect found/fixed: stop سربه‌سر یا بهتر ابتدا در exposure snapshot نامعتبر محسوب می‌شد؛ اکنون با ریسک باز صفر ثبت می‌شود و regression source test آن را قفل می‌کند.
- Same-day restart runtime: صفر attempt، صفر position، صفر exposure و `failed=0`؛ Symbol specification و Session روز مرجع نیز ثبت شد.
- Interpretation limit: این فقط یک Broker Day است؛ نتایج PnL برای سنجش عملکرد کافی نیستند. Multi-day parity و targeted regression جدا باقی‌اند؛ گزارش جامع Stage 7 ثبت شده است.
- Reproduce: ابتدا `scripts/compile_mt5.ps1`، سپس `scripts/run_mt5_tester_acceptance.ps1 -ConfigPath .\\config\\mt5\\tester_200.ini` و همان فرمان با `tester_300.ini`.

### EXP-TP-01-20260828

- Hypothesis: TP Extension یک‌مرحله‌ای فقط lifecycle خروج را مطابق Rule تغییر دهد و شمار Entry، Safety gate یا SL monotonicity را تغییر ندهد.
- Locked comparison: همان Dataset/روز 2026-08-28، Configهای 200/300، Real Ticks و هزینه Native؛ Control از Evidence ذخیره‌شده پیش از wiring TP و Variant از اجرای فعلی گرفته شد.
- Result: attempt/accepted/rejected در هر دو Profile ثابت ماند؛ net realized در 200 از `-4.25` به `-4.11` و در 300 از `-16.17` به `-16.03` رسید (اثر `+0.14 USD` در هر Profile). هر اجرا extension=1 و restore=1 داشت؛ market-close=0 و TP reject=0 بود.
- Safety: max position، gross loss، final exposure، broker reject و SL-loosen تغییر نامطلوب نداشتند؛ restart مستقل نیز با صفر attempt/position/exposure پاس شد.
- Interpretation limit: این A/B یک‌روزه فقط attribution مهندسی است، نه شواهد سودآوری یا robustness؛ شاخه Market Close در این روز فعال نشد.

### EXP-MT5-MULTIDAY-20260729-20260828

- Protocol: 23 روز Zone canonical، Real Ticks، سرمایه 200/max3، Cost model بومی، بدون Optimization و با Live/Remote/Cloud خاموش.
- Result: 302 attempt، 188 accepted، 114 invalid-price reject، max position=3، cancel/session close=`2/2`، protection modify=164، TP extend/restore/market-close=`10/3/2`؛ صفر unknown/TP reject، SL-loosen، exposure نهایی و lifecycle failure.
- Defects found/fixed: Pending-order risk اکنون با جهت Market معادل محاسبه می‌شود؛ Fill و Cancel callback/immediate races idempotent و fill state قابل recovery شدند.
- Limit: این PASS فقط MQL lifecycle robustness است؛ PnL summary فعلی آخرین Broker Day را نشان می‌دهد و برای عملکرد کل بازه استفاده نمی‌شود. Python↔MT5 multi-day parity هنوز جداست.

### EXP-ATTRIBUTION-20260729-20260828

- Same-run counters (attempt/accepted/rejected): Reversal Normal `86/86/0`، Reversal High `26/26/0`، Pullback Normal `146/56/90` و Pullback High `44/20/24`.
- QA 2026-07-29: `16/9/7`، net realized `+16.33`، Reversal Normal `5/5/0` و Pullback Normal `11/4/7`؛ High در این روز attempt نداشت.
- Limit: این داده attribution شمارشی است. PnL گروهی و مقایسه signal-by-signal با Fixture بیرونی طبق D-062 معیار پذیرش MVP نیستند.
