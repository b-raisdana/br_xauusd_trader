import csv
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import typer

from br_pre_commit import pandera_validate
from config import app_config

app = typer.Typer()


@dataclass
class TickDataConfig:
    start_time: datetime | None = None
    end_time: datetime | None = None
    min_price: float = 990.0
    max_price: float = 1000.0
    min_ticks_per_second: int = 10
    max_ticks_per_second: int = 20
    max_price_change_pct_per_second: float = 130.0
    max_volume: float = 0
    max_volume_change_pct_per_second: float = 130.0
    seed: int | None = 42
    output_path: Path = app_config.path_of_data / Path("tick_data.zip")


def get_yesterday_range() -> tuple[datetime, datetime]:
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)

    start = datetime.combine(yesterday, datetime.min.time())
    end = datetime.combine(yesterday, datetime.max.time()).replace(microsecond=999999)

    return start, end


@pandera_validate(allow_pandas_dataframe=True)
def generate_tick_data(config: TickDataConfig) -> pd.DataFrame:
    if config.seed is not None:
        random.seed(config.seed)

    start_time = config.start_time
    end_time = config.end_time

    if start_time is None or end_time is None:
        start_time, end_time = get_yesterday_range()

    total_seconds = int((end_time - start_time).total_seconds())

    if total_seconds <= 0:
        raise ValueError("end_time must be after start_time")

    rows = []
    current_price = random.uniform(config.min_price, config.max_price)
    current_volume = random.uniform(0, config.max_volume)

    max_price_change_per_second = (config.max_price_change_pct_per_second / 100.0) * (
        config.max_price - config.min_price
    )

    for sec in range(total_seconds):
        ticks_this_second = random.randint(
            config.min_ticks_per_second,
            config.max_ticks_per_second,
        )

        for tick_idx in range(ticks_this_second):
            dt = start_time + timedelta(
                seconds=sec,
                microseconds=int(1_000_000 * tick_idx / ticks_this_second),
            )

            price_changes = np.random.uniform(
                -max_price_change_per_second,
                max_price_change_per_second,
                size=6,
            )
            assert isinstance(price_changes, np.ndarray)
            new_prices = [
                (
                    current_price + price_change
                    if config.min_price < current_price + price_change < config.max_price
                    else current_price - price_change
                )
                for price_change in price_changes
            ]
            assert all(config.min_price <= price <= config.max_price for price in new_prices)

            ohlc = sorted(new_prices[:4])

            high = ohlc[-1]
            low = ohlc[0]
            open_index = np.random.randint(1, 2)
            assert isinstance(open_index, int)
            open_ = ohlc[open_index]
            close = ohlc[-open_index]

            bid = max(new_prices[-2:])
            ask = min(new_prices[-2:])

            volume_change = np.random.uniform(-max_price_change_per_second, max_price_change_per_second)

            volume = (
                current_volume + volume_change
                if 0 <= current_volume + volume_change <= config.max_volume
                else current_volume - volume_change
            )
            rows.append(
                {
                    "Datetime": dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "Open": f"{open_:.5f}",
                    "High": f"{high:.5f}",
                    "Low": f"{low:.5f}",
                    "Close": f"{close:.5f}",
                    "Bid": f"{bid:.5f}",
                    "Ask": f"{ask:.5f}",
                    "Volume": f"{volume:.5f}",
                }
            )
            current_price = close
            current_volume = volume
    df = pd.DataFrame(rows)
    df.to_csv(
        (config.output_path if config.output_path.suffix.lower() == "zip" else config.output_path.with_suffix("zip")),
        compression="zip",
        index=False,
    )

    with open(config.output_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "Datetime",
                "Open",
                "High",
                "Low",
                "Close",
                "Bid",
                "Ask",
                "Volume",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    return df


@app.command()
def generate_tick_data_command(
    start_time: datetime | None = typer.Option(
        None,
        "--start-time",
        help="Start datetime, e.g. 2026-09-16T00:00:00.",
    ),
    end_time: datetime | None = typer.Option(
        None,
        "--end-time",
        help="End datetime, e.g. 2026-09-16T23:59:59.",
    ),
    min_price: float = typer.Option(
        990.0,
        "--min-price",
        help="Minimum allowed price.",
    ),
    max_price: float = typer.Option(
        1000.0,
        "--max-price",
        help="Maximum allowed price.",
    ),
    min_ticks_per_second: int = typer.Option(
        10,
        "--min-ticks-per-second",
        help="Minimum ticks generated per second.",
    ),
    max_ticks_per_second: int = typer.Option(
        20,
        "--max-ticks-per-second",
        help="Maximum ticks generated per second.",
    ),
    max_price_change_pct_per_second: float = typer.Option(
        130.0,
        "--max-price-change-pct-per-second",
        help="Maximum price change as a percentage of the configured price range per second.",
    ),
    max_volume: float = typer.Option(
        0.0,
        "--max-volume",
        help="Maximum volume.",
    ),
    max_volume_change_pct_per_second: float = typer.Option(
        130.0,
        "--max-volume-change-pct-per-second",
        help="Maximum volume change as a percentage of the configured max-volume per second.",
    ),
    seed: int | None = typer.Option(
        42,
        "--seed",
        help="Random seed. Use --seed with a value for reproducible output; omit with --no-seed.",
    ),
    output_path: str = typer.Option(
        "data/tick_data.zip",
        "--output-path",
        help="Output ZIP path.",
    ),
) -> None:
    config = TickDataConfig(
        start_time=start_time,
        end_time=end_time,
        min_price=min_price,
        max_price=max_price,
        min_ticks_per_second=min_ticks_per_second,
        max_ticks_per_second=max_ticks_per_second,
        max_price_change_pct_per_second=max_price_change_pct_per_second,
        max_volume=max_volume,
        max_volume_change_pct_per_second=max_volume_change_pct_per_second,
        seed=seed,
        output_path=Path(output_path),
    )

    try:
        path = generate_tick_data(config)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    resolved_start = start_time
    resolved_end = end_time

    if resolved_start is None or resolved_end is None:
        resolved_start, resolved_end = get_yesterday_range()

    typer.echo(f"Generated tick data: {path}")
    typer.echo(f"Time range: {resolved_start} to {resolved_end}")
    typer.echo(f"Price range: {min_price} - {max_price}")
    typer.echo(f"Ticks per second: {min_ticks_per_second} - {max_ticks_per_second}")
    typer.echo(f"Max price change per second: {max_price_change_pct_per_second}%")


if __name__ == "__main__":
    app()
