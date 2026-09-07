# Experiment Registry

نتایج این فایل Evidence هستند، نه Rule و نه مجوز Live. جزئیات Ruleهای جایگزین‌شده در `RULES_ARCHIVE_FUTURE.md` است.

## Evidence تاریخی بازیابی‌شده

| ID | موضوع | نتیجه گزارش‌شده | برداشت مجاز | وضعیت Evidence جاری |
|---|---|---|---|---|
| E-R0 | Control baseline | حدود `+45.44`، 37 معامله، PF `1.39`؛ Compile `0/0` | Harness قدیمی قابل اجرا بوده است. | Artifact/Commit باید بازیابی شود |
| E-R2 | Session safety | Carry `-91.35/497 trades`؛ PB_FLAT `+62.90/495`؛ ALL_FLAT `+72.13/PF1.046/495`؛ زیان‌های `>2×Base R` از 6 به 0. در `2026-08-05` دو PB-S با زیان‌های `-26.90` و `-26.79` به Session بعد Carry شده بودند. | Carry عامل Tail Risk مهم بوده است. | MetaQuotes-Demo schedule تاریخی 00:00–23:00 و cutoff 22:55؛ محیط هدف باید دوباره خوانده شود |
| E-ZONE | Zone dataset | 2,343 event، 23/23 روز، High=337، Normal=2006، match=99.3789%؛ یک mismatch حفظ‌شده در `2026-07-30 / R9` | Dataset قدیمی پوشش مناسبی برای QA داشته است؛ mismatch نباید پنهان شود. | Version/Hash مجموعه Event موجود نیست |
| E-EDGE | Normal/High Forward | Combined `-89.50/PF0.848`؛ High `+18.96/PF1.297` | High بهتر بود؛ Normal به Attribution نیاز دارد. | Exploratory |
| E-FAMILY | Unfiltered robustness | Reversal: 207 معامله، `+42.12/PF1.061` و Forward `-54.41/PF0.776`؛ PB: 288، `+30.01/PF1.034` و Forward `-35.09/PF0.899`؛ Combined Forward `-89.50/PF0.848` | خانواده‌های بدون Filter آزمون Forward اولیه را پاس نکردند. | Negative evidence retained |
| E-TREND | Sticky vs Progressive | Sticky همه 2,343 event را حفظ کرد؛ Progressive هجده Reversal با مجموع حدود `+41.30` را حذف کرد | Bootstrap جدید ممکن است Regression بسازد. | هشدار Regression؛ Rule انتخاب‌شده تغییر نمی‌کند |
| E-PBW | PB Window | N5 `+30.01/PF1.034`؛ N3 Forward `-33.27/PF0.897`؛ structure-valid Nmax5 Forward `-58.04/PF0.833`؛ N7/N9 ضعیف‌تر | N5 حفظ می‌شود. | Historical support |
| E-PBC | PB context | Normal1/High∞ + Space15: All `+93.75/PF1.514`؛ Forward `+43.84/PF1.855` | مصرف PB حمایت محدود دارد؛ Space3 باید مقابل Space15 Validate شود. | A/B planned |
| E-REV | Replay parity / repeat | 207/207؛ Actual `+42.12` در برابر Replay `+42.07`. First raw touch: 132 معامله، `-53.38/PF0.880`؛ Later touch: 72، `+102.86/PF1.432` | Parity نزدیک بود و first-touch-only حمایت نشد. | Engine/fixture باید بازیابی شود |
| E-FINAL | Finalist تاریخی | Control `+72.13/PF1.046`؛ F1 `+162.60/PF1.412`، Forward `+35.49/PF1.404`؛ F2 `+143.59/PF1.440`، Forward `+40.18/PF1.483` | F2 به علت Forward/Tail/Concentration انتخاب شد؛ Rulebook فعلی تغییر کرده است. | Historical only |
| E-B23 | Capital scenarios | 200/max3: 109 معامله، `+143.97/PF1.463`؛ 300/max5: 113، `+143.59/PF1.440`؛ Forward هر دو `+40.18/PF1.483`؛ Margin Block صفر؛ max concurrency=3 | سناریوهای پذیرش سرمایه قابل اجرا بوده‌اند. | Config باید بازیابی شود |
| E-RISK | GROSS15 | 22 Real-Tick run؛ 200 دلار `+183.98/PF1.678/DD35.56/103 trades`؛ 300 دلار `+158.72/PF1.535/DD50.61/107 trades`؛ overflow=0 | Budget 15% نیازمند بازتولید روی Rules جدید است. | Historical only |
| E-OPS | Restart safety | 4/4 behavior؛ صفر Fill همان‌روز بعد Restart؛ صفر Flatten/Cancel fail؛ later-day resume PASS؛ یک telemetry mismatch به‌عنوان simulator artifact طبقه‌بندی شد | Fail-closed قدیمی شواهد فنی مثبت دارد. | Commit/environment باید بازیابی شود |

## زیرساخت داده بازیابی‌شده

- Python bootstrap v4 موفق: MetaTrader5 package، NumPy `2.5.2` و Polars `1.44.1`.
- اختلاف ساعت مشاهده‌شده: `UTC+00:00`؛ نمونه قیمت 20/20 Match.
- Cache گزارش‌شده: 31 روز Server، 23 روز دارای Tick، 12,262,192 Tick و 2,024 کندل M15 در بازه تقریبی `2026-07-29` تا `2026-08-29`.
- نسخه‌های bootstrap v1 تا v3 ناموفق بودند؛ v4 بدون Admin کار کرد.
- فایل مستقل `ranges.csv` و دو نسخه داخل Bundle از نظر SHA-256 کاملاً یکسان‌اند: `d146fe4650ea52da64b585a7a0ee15d874e68801f12764481e9ef8c773c9f4f3`.

## آزمایش‌های الزامی قبل Freeze

| ID | آزمایش | فرضیه/هدف | معیار پذیرش |
|---|---|---|---|
| EXP-MIG-01 | Repository evidence recovery | PASSهای تاریخی به Artifact/Config/Commit متصل شوند. | هیچ PASS بدون Evidence نماند. |
| EXP-TREND-02 | Daily Bootstrap vs Sticky | اثر حذف/افزودن Signalها روشن شود. | همه اختلاف‌ها Rule-based توضیح داده شوند. |
| EXP-REV-02 | Normal/High attribution | اثر فعال‌بودن Normal و max1/max2 مستقل گزارش شود. | تعداد، PnL و Reject reason جداگانه. |
| EXP-FS-02 | Space3 vs Space15 | Rule جدید بدون Grid Search با Control تاریخی مقایسه شود. | A/B ازپیش‌تعریف‌شده؛ بدون انتخاب پس از دیدن نتیجه. |
| EXP-STRICT-01 | Strict Trend state machine | Same-Bar/Multi-Bar/Doji/opposing candle دقیق اجرا شوند. | همه Contract fixtureها PASS. |
| EXP-TP-01 | One-step TP Extension | Extension/Restore/Market Close مطابق Rule باشد. | صفر State transition نادرست. |
| EXP-PARITY-02 | Python ↔ MT5 | دو Engine روی Vector مشترک هم‌رفتار باشند. | صفر اختلاف توضیح‌نشده. |
| EXP-QA-29JUL | QA روز 2026-07-29 | نقاط شناخته‌شده BO/PB/R با Rule جدید تطبیق یابند. | Ledger کامل Signal-by-Signal. |

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
- Result 200: 14 attempt، 12 accepted، 2 invalid-price reject، net realized `-4.25`، gross loss `28.68`، max positions `1`، protection modify=`8`، margin/other/modify reject=`0`، SL loosen=`0`، final zero exposure و lifecycle `failed=0`.
- Result 300: 16 attempt، 14 accepted، 2 invalid-price reject، net realized `-16.17`، gross loss `40.60`، max positions `1`، protection modify=`8`، margin/other/modify reject=`0`، SL loosen=`0`، final zero exposure و lifecycle `failed=0`.
- Defect found/fixed: stop سربه‌سر یا بهتر ابتدا در exposure snapshot نامعتبر محسوب می‌شد؛ اکنون با ریسک باز صفر ثبت می‌شود و regression source test آن را قفل می‌کند.
- Interpretation limit: این فقط یک Broker Day است؛ نتایج PnL برای سنجش عملکرد کافی نیستند. TP-extension، same-day restart runtime، multi-day parity و Visual acceptance جدا باقی‌اند.
- Reproduce: ابتدا `scripts/compile_mt5.ps1`، سپس `scripts/run_mt5_tester_acceptance.ps1 -ConfigPath .\\config\\mt5\\tester_200.ini` و همان فرمان با `tester_300.ini`.
