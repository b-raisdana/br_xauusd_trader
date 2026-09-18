# قوانین لغوشده، جایگزین‌شده و موارد آینده

نسخه: v2 — Consolidated Migration
هدف: حفظ کامل حافظه پروژه بدون شلوغ‌کردن Rulebook فعال.

این فایل برای مراجعه تاریخی است. هیچ مورد این فایل نباید صرفاً به علت وجود در Archive وارد کد شود.

---

## نگاشت شناسه‌های قدیمی به نام‌های جدید قابل فهم

| شناسه قدیمی | نام جدید / وضعیت |
|---|---|
| a-1 | `CANDLE_BULLISH` |
| a-2 | `CANDLE_BEARISH` |
| a-3 | `CANDLE_RANGE` |
| a-4 | `MARKET_TIMEFRAME` |
| a-5 | `ZONE_INPUT` |
| a-6 | `ZONE_ALIAS` |
| a-7 | `ZONE_LINE_ALLOWED` |
| a-8 | `ZONE_MERGE` |
| a-9 | `ZONE_PRIORITY` |
| a-10 | `ZONE_ONLY_ENTRY` |
| trend-1 / SEC-TREND-01 | `DAY_START_TREND_BOOTSTRAP`, `TREND_DIRECTION` |
| trend-2 | `TICK_EVENT_ORDER` |
| b-1 | `REVERSAL_DIRECTIONAL_TOUCH` |
| b-2 | `REVERSAL_WICK_VALIDITY` |
| b-3 / b-4 | `BREAKOUT_VALIDATION` |
| b-8 / SEC-PB-01..03 | `PULLBACK_CONSERVATIVE_ENTRY`, `PULLBACK_WINDOW`, `PULLBACK_MULTI_PER_BREAKOUT`, `PULLBACK_DAILY_USAGE` |
| b-24 / SEC-REV-01/02 | `NORMAL_REVERSAL_DAILY_LIMIT`, `HIGH_REVERSAL_DAILY_LIMIT` |
| b-26 | `SIGNAL_USAGE_INDEPENDENCE` |
| b-29 / SEC-RISK-01 | `PROFIT_PROTECTION` |
| b-30 | `INITIAL_STOP`, `INITIAL_TARGET` |
| b-31 | `REVERSAL_DUPLICATE_GUARD` |
| journal-2 | `BREAKOUT_LINEAGE` |
| SEC-CONFLICT-01 | `STRICT_PULLBACK_TREND`, `BLOCK_OPPOSITE_REVERSAL` |
| SEC-TP-01 | `EXTEND_PULLBACK_TP` |
| SEC-FS-01 | `FREE_SPACE_DEFINITION`, `FREE_SPACE_MINIMUM` |
| AR-SESSION-01 | `SESSION_END_FLATTEN` |
| AR-RISK-01 | `PORTFOLIO_RISK_BUDGET` |
| AR-OPS-01 | `RESTART_FAIL_CLOSED` |
