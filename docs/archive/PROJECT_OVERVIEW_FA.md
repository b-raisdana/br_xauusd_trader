# بررسی کلی پروژه XAUUSD Price Action (به زبان ساده)

## این پروژه چی کار می‌کند؟

این پروژه یک **سیستم معاملاتی الگوریتمی برای طلا (XAUUSD)** است که بر اساس روش **Price Action** روی تایم‌فریم **M15 (15 دقیقه)** کار می‌کند.

به زبان ساده:
- **ورودی‌ها:** کندل‌های M15 و تیک‌های واقعی (Bid)، زون‌های روزانه (که به صورت دستی/خارجی فراهم می‌شوند)
- **خروجی‌ها:** سیگنال‌های معامله (Breakout، Reversal، Pullback) با مدیریت ریسک کامل (SL/TP، محدودیت پوزیشن، محافظت سود)
- **هدف:** اجرای دقیق و قابلِ أودیت (Audit) قوانین معامله بدون هیچ تفسیر پنهانی، طوری که هم در Python و هم در MT5 رفتار یکسان داشته باشد.

---

## نکات کلیدی (به زبان ساده)

| مورد | توضیح |
|------|-------|
| **نماد** | XAUUSD (طلا) |
| **تایم‌فریم اصلی** | M15 |
| **حجم معامله (MVP)** | ثابت (FIXED_VOLUME_LOTS) - بدون داینامیک سایزینگ |
| **ریسک پایه** | BASE_R_USD = 6.00 دلار (ثابت، با فاصله استاپ‌لاس واقعی یکی نیست) |
| **زون‌ها** | ورودی روزانه از خارج (CSV) - تولید خودکار زون در MVP نیست |
| **مرجع پذیرش نهایی** | MT5 Strategy Tester با حالت "Every Tick Based on Real Ticks" |

---

## نقاط ورود (Entry Points) پروژه

### 1. اسکریپت اصلی اجرا: `scripts/presentations.py`
این **نقطه ورود اصلی** برای اجرای Replay و تولید گزارش است:

```bash
python scripts/presentations.py --ticks data/ticks.csv --zones data/ranges.csv --broker-utc-offset-minutes 180 --format text
```

**چیزی که انجام می‌دهد:**
1. بارگذاری تیک‌های MT5 از فایل CSV (`load_mt5_tick_bars`)
2. بارگذاری زون‌ها از فایل CSV (`load_zone_csv`)
3. ساخت روزهای Replay (`build_replay_days`)
4. اجرای موتور Replay روز به روز (`ReplayRunner.run_day`)
5. تولید گزارش متنی یا JSON خلاصه

### 2. ماژول هسته (Core Modules) - `src/xauusd/`

| ماژول | وظیفه | قابل استفاده مستقیم؟ |
|-------|-------|---------------------|
| `market_state.py` | موتور اصلی توالی رویدادها: Trend → Engagement → Reversal/Pullback | بله - کلاس `MarketState` |
| `replay.py` | رانر Deterministic برای شبیه‌سازی روزانه | بله - کلاس `ReplayRunner` |
| `orchestration.py` | پروژهکتور Audit (حذف تکرار سیگنال‌ها) | بله - کلاس `MarketAuditProjector` |
| `signals.py` | منطق Breakout، Reversal، Pullback | بله - کلاس‌های Trackerها |
| `risk.py` | محاسبه SL/TP، مدیریت پوزیشن، ریسک روزانه | بله - توابع و کلاس‌ها |
| `safety.py` | گاردهای امنیتی: Daily Loss، Session Pre-Close، Restart Fail-Closed | بله - کلاس‌های Guard |
| `execution.py` | دفترچه اجرا (Ledger) برای سفارش‌ها | بله - کلاس `ExecutionLedger` |
| `audit.py` | رویدادهای Immutable برای أودیت کامل | بله - کلاس `AuditJournal` |
| `zones.py` | مدیریت زون‌ها، اولویت‌بندی، Engagement | بله - توابع `build_daily_zones`، `load_zone_csv` |
| `trend.py` | ردیابی ترند روزانه (DailyTrendTracker) | بله - کلاس `DailyTrendTracker` |
| `pullback.py` | منطق Pullback و پنجره‌های ورود | بله - کلاس `PullbackTracker` |
| `momentum.py` | Триگرهای پیش‌زون و مدیریت TP | بله - کلاس `PreZoneTriggerTracker` |
| `tick_data.py` | بارگذاری تیک‌های MT5 و تبدیل به بارهای M15 | بله - تابع `load_mt5_tick_bars` |
| `schemas.py` | انواع داده‌های پایه (Enums، Dataclasses) | بله - تمام تعاریف |

### 3. اسکریپت‌های کمکی (Utility Scripts) - `scripts/`

| اسکریپت | کار | نقطه ورود مستقیم؟ |
|----------|-----|------------------|
| `presentations.py` | **بله** - اجرای اصلی Replay و گزارش | ✅ بله |
| `export_mt5_ticks.py` | صادر کردن تیک‌ها از MT5 به CSV | ✅ بله |
| `generate_mql_zones.py` | تولید فایل زون برای MQL5/MT5 | ✅ بله |
| `generate_mql_vectors.py` | تولید وکتورهای مقایسه Python/MT5 | ✅ بله |
| `compare_signal_parity.py` | مقایسه سیگنال‌های Python با MT5 | ✅ بله |
| `match_mt5_time_basis.py` | تطبیق اساس زمانی بکر | ✅ بله |
| `project_status.py` | گزارش وضعیت پروژه | ✅ بله |

---

## قابلیت‌هایی که **نقطه ورود ندارند** (Not Reachable / بدون Entry Point)

### 1. ماژول‌های داخلی که فقط از طریق `MarketState` یا `ReplayRunner` صدا زده می‌شوند:
| ماژول | دلیل عدم دسترسی مستقیم |
|-------|------------------------|
| `xauusd.trend.DailyTrendTracker` | فقط از `MarketState.trend` قابل استفاده است |
| `xauusd.signals.ReversalTracker` | فقط از `MarketState.reversals` قابل استفاده است |
| `xauusd.signals.BreakoutTracker` | فقط از `MarketState.breakouts` قابل استفاده است |
| `xauusd.signals.OrderAttemptLedger` | داخلی - برای ردیابی تلاش سفارش |
| `xauusd.pullback.PullbackTracker` | فقط از `MarketState.pullbacks` قابل استفاده است |
| `xauusd.zones.ZoneEngagementTracker` | فقط از `MarketState.engagement` قابل استفاده است |
| `xauusd.execution.ExecutionLedger` | فقط از `ReplayRunner.execution` قابل استفاده است |
| `xauusd.audit.AuditJournal` | فقط از `MarketAuditProjector` و `ReplayRunner` قابل استفاده است |

> **نکته:** این ماژول‌ها **public API ندارند** و از طریق کلاس‌های fachada (`MarketState`، `ReplayRunner`) به کار می‌روند. این **طراحی عمدی** برای اطمینان از توالی صحیح رویدادها (TICK_EVENT_ORDER) است.

### 2. توابع/کلاس‌های کمکی داخلی (Internal Helpers):
| آیتم | در فایل | وضعیت |
|------|---------|-------|
| `blocks_opposite_reversal` | `momentum.py` | فقط داخلی |
| `strict_pullback_trend` | `momentum.py` | فقط داخلی |
| `pre_zone_trigger_price` | `momentum.py` | فقط داخلی |
| `pullback_window_active` | `pullback.py` | فقط داخلی |
| `pullback_usage_allowed` | `pullback.py` | فقط داخلی |
| `concurrency_allows_entry` | `risk.py` | فقط داخلی |
| `native_margin_allows_entry` | `risk.py` | فقط داخلی |
| `has_minimum_free_space` | `risk.py` | فقط داخلی |
| `directional_free_space` | `risk.py` | فقط داخلی |
| `evaluate_entry_safety` | `safety.py` | فقط داخلی |
| `evaluate_portfolio_risk` | `safety.py` | فقط داخلی |
| `session_end_actions` | `safety.py` | فقط داخلی |

### 3. ماژول‌های Legacy / Reference (قدیمی - در `legacy_reference/`):
این فایل‌ها **بخش از پروژه فعلی نیستند** و فقط برای مرجع تاریخی باقی مانده‌اند:
- `pb_window_replay.py`
- `pb_lifecycle_batch.py`
- `pb_context_batch.py`
- `zone_event_dataset.py`
- `reversal_portfolio_batch.py`
- `pb_finalist_batch.py`
- `research_bootstrap.py`
- `trend_init_screen.py`
- `pb_support.py`

### 4. تست‌ها (`tests/`):
تست‌ها نقطه ورود اجرایی ندارند - فقط از طریق `pytest` اجرا می‌شوند:
```bash
pytest tests/ -q
```

---

## خلاصه: چطور پروژه را اجرا کنید؟

### برای Replay و گزارش (راه اصلی):
```bash
# 1. تیک‌های MT5 را صادر کنید
python scripts/export_mt5_ticks.py --output data/ticks.csv

# 2. زون‌های روزانه را در data/ranges.csv قرار دهید

# 3. Replay اجرا کنید و گزارش بگیرید
python scripts/presentations.py \
    --ticks data/ticks.csv \
    --zones data/ranges.csv \
    --broker-utc-offset-minutes 180 \
    --format text \
    --output report.txt
```

### برای توسعه/تست واحد:
```bash
# اجرای همه تست‌ها
pytest tests/ -q

# اجرای تست خاص
pytest tests/test_market_state.py -q
pytest tests/test_replay.py -q
```

### برای مقایسه Python با MT5 (Parity):
```bash
# تولید وکتورهای مقایسه
python scripts/generate_mql_vectors.py --ticks data/ticks.csv --zones data/ranges.csv

# مقایسه سیگنال‌ها
python scripts/compare_signal_parity.py --python-vectors python_vectors.json --mt5-vectors mt5_vectors.json
```

---

## معماری کلی (نمودار ساده)

```
┌─────────────────────────────────────────────────────────────┐
│                    scripts/presentations.py                   │
│                        (Entry Point)                          │
└──────────────────────────┬────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌────────────────┐ ┌───────────────┐ ┌────────────────┐
│ load_mt5_tick_ │ │ load_zone_csv │ │ build_replay_  │
│ bars()         │ │ ()            │ │ days()         │
└───────┬────────┘ └───────┬───────┘ └───────┬────────┘
        │                  │                 │
        ▼                  ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│                     ReplayRunner                              │
│  ┌─────────────┐ ┌─────────────┐ ┌────────────────────────┐  │
│  │ MarketState │ │AuditJournal │ │ ExecutionLedger        │  │
│  │             │ │             │ │                        │  │
│  │ • Trend     │ │ • Events    │ │ • Submit/Fill/Reject   │  │
│  │ • Engagement│ │ • Dedupe    │ │ • Close/Modify/Cancel  │  │
│  │ • Reversal  │ │ • Immutable │ │                        │  │
│  │ • Pullback  │ │             │ │                        │  │
│  │ • Breakout  │ │             │ │                        │  │
│  └─────────────┘ └─────────────┘ └────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
              ┌───────────────────────┐
              │   Audit Events        │
              │   (JSONL / Report)    │
              └───────────────────────┘
```

---

## نکات مهم برای توسعه‌دهنده

1. **هرگز مستقیماً `ReversalTracker`، `BreakoutTracker`، `PullbackTracker` را instantiate نکنید** - همیشه از طریق `MarketState` کار کنید.

2. **توالی رویدادها (TICK_EVENT_ORDER) حیاتی است:**
   ```
   Trend Update → Engagement Update → Reversal Detect → Pullback Evaluate
   ```

3. **برای اضافه کردن قانون جدید:**
   - اول در `RULES.md` ثبت شود
   - بعد Contract Test نوشته شود
   - بعد در ماژول مربوطه پیاده‌سازی شود
   - بالاخره در `MarketState.process_tick` یا `close_bar` صدا زده شود

4. **هیچ منطق مخفی (Hidden Logic) وجود ندارد** - همه قوانین در `RULES.md` و کد قابل ردیابی هستند.

5. **MT5 Parity الزامی است** - هر تغییری باید در هر دو طرف (Python و MQL5) همزمان اعمال و تست شود.

---

*ساخته شده برای Project Leader - زبان فارسی، ساده و قابل فهم*