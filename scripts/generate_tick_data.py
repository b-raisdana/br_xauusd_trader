import csv
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class TickDataConfig:
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    min_price: float = 990.0
    max_price: float = 1000.0
    min_ticks_per_second: int = 10
    max_ticks_per_second: int = 20
    max_price_change_pct_per_second: float = 130.0
    seed: Optional[int] = 42
    output_path: str = "data/tick_data.csv"


def get_yesterday_range() -> tuple[datetime, datetime]:
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    start = datetime.combine(yesterday, datetime.min.time())
    end = datetime.combine(yesterday, datetime.max.time()).replace(microsecond=999999)
    return start, end


def generate_tick_data(config: TickDataConfig) -> str:
    if config.seed is not None:
        random.seed(config.seed)

    if config.start_time is None or config.end_time is None:
        config.start_time, config.end_time = get_yesterday_range()

    total_seconds = int((config.end_time - config.start_time).total_seconds())
    if total_seconds <= 0:
        raise ValueError("end_time must be after start_time")

    rows = []
    current_price = random.uniform(config.min_price, config.max_price)

    for sec in range(total_seconds):
        ticks_this_second = random.randint(config.min_ticks_per_second, config.max_ticks_per_second)

        max_change = (config.max_price_change_pct_per_second / 100.0) * (config.max_price - config.min_price)

        for tick_idx in range(ticks_this_second):
            dt = config.start_time + timedelta(seconds=sec, microseconds=int(1_000_000 * tick_idx / ticks_this_second))

            price_change = random.uniform(-max_change, max_change)
            current_price = max(config.min_price, min(config.max_price, current_price + price_change))

            bid = round(current_price, 5)
            ask = round(current_price + random.uniform(0, 0.01), 5)

            high = max(bid, ask)
            low = min(bid, ask)
            open_ = bid
            close = ask

            high = round(max(open_, close, high), 5)
            low = round(min(open_, close, low), 5)

            rows.append(
                {
                    "Datetime": dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "Open": f"{open_:.5f}",
                    "High": f"{high:.5f}",
                    "Low": f"{low:.5f}",
                    "Close": f"{close:.5f}",
                    "Bid": f"{bid:.5f}",
                    "Ask": f"{ask:.5f}",
                    "Volume": "1",
                }
            )

    with open(config.output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Datetime", "Open", "High", "Low", "Close", "Bid", "Ask", "Volume"])
        writer.writeheader()
        writer.writerows(rows)

    return config.output_path


def main():
    config = TickDataConfig()
    path = generate_tick_data(config)
    print(f"Generated tick data: {path}")
    print(f"Time range: {config.start_time} to {config.end_time}")
    print(f"Price range: {config.min_price} - {config.max_price}")
    print(f"Ticks per second: {config.min_ticks_per_second} - {config.max_ticks_per_second}")
    print(f"Max price change per second: {config.max_price_change_pct_per_second}%")


if __name__ == "__main__":
    main()
