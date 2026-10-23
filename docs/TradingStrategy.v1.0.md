# Trading Strategy

- Versio: 1.0

## Table of Contents

- [Trading Strategy](#trading-strategy)
  - [Table of Contents](#table-of-contents)
  - [Input data](#input-data)
    - [Trading Zones](#trading-zones)
    - [Tick](#tick)
    - [5min, and 15mn Candles](#5min-and-15mn-candles)
  - [Signal generation](#signal-generation)
    - [Expected Signals](#expected-signals)
      - [Direction](#direction)
      - [Cause](#cause)
        - [Reversal](#reversal)
        - [Pull Back](#pull-back)
      - [تأیید RSI](#تأیید-rsi)
      - [تأیید Zero Lag MACD](#تأیید-zero-lag-macd)
  - [Risk](#risk)
    - [TradingCapital](#tradingcapital)
    - [PerOrderRiskableMoney](#perorderriskablemoney)
    - [RemainingDailyLose](#remainingdailylose)
    - [RemainingConsequentialLose](#remainingconsequentiallose)
  - [Order](#order)
    - [SL-Distance](#sl-distance)
    - [TP](#tp)
    - [SL and TP Gates](#sl-and-tp-gates)
      - [SL-Distance Risk](#sl-distance-risk)
      - [TP \> SL](#tp--sl)
    - [Entry limit](#entry-limit)

## Input data

### Trading Zones

- High price
- Low price
- Importance (ufloat16): 0-0.3 low, 0.3-0.7~0.5 normal, 0.7-1 High
- Direction (float 16): zero = neutral

### Tick

use: class Tick(TickMultiBrokerSymbolTimeseries) defined in src\domain\schemas\tick.py

### 5min, and 15mn Candles

- multi-timeframe OHLC
  - (MultiTimeframeOHLC defined in src\domain\schemas\common\ohlcv.py)
- Timeframes
  - 5min
  - 15min

## Signal generation

### Expected Signals

#### Direction

- Long
- Short

#### Cause

##### Reversal

- تیک وارد ناحیه بشود
- تضاد در ترند فیلتر / دیسکارد بشود
  - اگر از بالا وارد بشود برای اینکه ریورسال باشد باید در زمان ورود به ناحیه ترند نزولی باشد و برعکس
  - ورود از بالا و ترند در نقطه ورود نزولی =
    - دنبال Buy می گردیم
- اول RSI و بعد از آن Zero Lag MACD تأیید بدهند.

##### Pull Back

- کلوز کندل 15 دقیقه قبلی به اندازه حداقل حرکت شکست از سطح خارج بشود.
- جداقل خروج برای شکست فعلا 1 دلار ثابت است
- تا N=5 کندل بعد اولین تیک که وارد همان ناحیه بشود می تواند پول بک باشد
- اگر ترند تأیید بناید
  - اگر از بالای سطح روی ترند صعودی کلوز بالاتر از 1 دلار بالاتر از سطح بالای ناحیه بدهد و تا 5 کندل بعد ترند هنوز صعودی باشد و تیک وارد همان ناحیه بشود
- ورود از بالا و ترند در نقطه ورود صعودی =
    - دنبال Buy می گردیم
- یکی از RSI یا Zero Lag MACD تأیید بدهند

#### تأیید RSI

- Look backward in last 3 close 5min candles
- Buy
  - <= 30
- Sell
  - >= 70

#### تأیید Zero Lag MACD

- Look forward until price exits range
  - Range exit = close > 1usd outside or the range
- Buy
  - Signal <= -2
  - H (Histogram):
    - > H[-1]
    - > -0.5
- Sell
  - Signal <= 2
  - H (Histogram):
    - < H[-1]
    - < 0.5

## Risk

### TradingCapital

- BackTest: 1000$
- RealTest: 400$

### PerOrderRiskableMoney

- max(20$, 1% of TradingCapital)

### RemainingDailyLose

- Restart at each TP hit: max(60$, 3x PerOrderRiskableMoney)

### RemainingConsequentialLose

- Restart at each win
- Win: PnL > -1$
  - -1$ ~= sleepage / trading fees
- max(40$, 2x PerOrderRiskableMoney)

## Order

### SL-Distance

- LondonNewYorkOverlap
  - 10 USD
- Other times
  - 6 USD


### TP

Next zone nearest band:

- Buy:
  - Lower band of nearest Upper zone

### SL and TP Gates

#### SL-Distance Risk

- < PerOrderRiskableMoney
- < RemainingConsequentialLose
- < RemainingDailyMaskLose

#### TP > SL

- SL-Distance < TP-Distance

### Entry limit

بازه تا جایی مورد قبول است که اعتبار SL-Distance < TP-Distance معتبر بماند.
- Tolerance: TP - SL-Distance
- نزدیکترین باند سطح مقابل - SL-Distance
- Buy
  - < Lower bound of nearest Upper zone - SL-Distance
- Sell
  - > Upper bound of nearest Lower zone + SL-Distance
