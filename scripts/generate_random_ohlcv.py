import csv
import random
from datetime import datetime, timedelta


def generate_random_ohlcv(
    output_path: str = "data/random_ohlcv.csv",
    bars: int = 50,
    price_start: float = 2350.0,
    price_min: float = 2300.0,
    price_max: float = 2400.0,
    volume_min: int = 50,
    volume_max: int = 500,
    start_time: str = "2026-09-16T00:00:00+00:00",
) -> str:
    random.seed(42)
    dt_start = datetime.fromisoformat(start_time)
    rows = []
    current_price = price_start
    for i in range(bars):
        dt = dt_start + timedelta(minutes=15 * i)
        if i == 10:
            open_ = current_price
            high_ = current_price
            low_ = current_price
            close_ = current_price
            volume_ = 0
        elif i == 20:
            open_ = current_price + random.uniform(-0.5, 0.5)
            high_ = open_
            low_ = open_
            close_ = open_
            volume_ = random.randint(volume_min, volume_max)
        elif i == 35:
            open_ = current_price
            close_ = current_price + random.uniform(10, 20)
            high_ = close_ + random.uniform(0, 2)
            low_ = open_ - random.uniform(0, 2)
            volume_ = random.randint(volume_min, volume_max)
        else:
            drift = random.gauss(0, 2.0)
            open_ = current_price
            close_ = max(price_min, min(price_max, open_ + drift))
            high_ = max(open_, close_) + random.uniform(0, 3)
            low_ = min(open_, close_) - random.uniform(0, 3)
            volume_ = random.randint(volume_min, volume_max)
            high_ = round(high_, 2)
            low_ = round(max(price_min, low_), 2)
            open_ = round(open_, 2)
            close_ = round(close_, 2)

        if i not in (10, 20, 35):
            high_ = round(high_, 2)
            low_ = round(max(price_min, low_), 2)
            open_ = round(open_, 2)
            close_ = round(close_, 2)

        rows.append(
            {
                "Datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "Open": f"{open_:.2f}",
                "High": f"{high_:.2f}",
                "Low": f"{low_:.2f}",
                "Close": f"{close_:.2f}",
                "Volume": str(volume_),
            }
        )
        current_price = close_

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Datetime", "Open", "High", "Low", "Close", "Volume"])
        writer.writeheader()
        writer.writerows(rows)

    return output_path


if __name__ == "__main__":
    path = generate_random_ohlcv()
    print(f"Generated: {path}")
