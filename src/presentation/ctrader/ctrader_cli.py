"""Manual test CLI for the cTrader Open API client."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

import typer
from ctrader_open_api import Protobuf
from twisted.internet import reactor as _reactor

from infrastructure.ctrader_client import (
    CTraderClient,
    CTraderSettings,
    build_account_auth_request,
    build_application_auth_request,
    build_get_account_list_request,
    build_get_tick_data_request,
    build_subscribe_depth_request,
    build_subscribe_spots_request,
    build_symbol_by_id_request,
    build_symbols_list_request,
    decode_price,
    pip_size,
    point,
)
from infrastructure.ctrader_client.models import CTraderError, TickPage
from infrastructure.ctrader_client.streams import (
    parse_accounts,
    parse_depth_event,
    parse_error,
    parse_spot_event,
    parse_symbol,
    parse_symbols_list,
    parse_tick_data_page,
)
from presentation.ctrader.ctrader_oauth import load_live_settings, oauth_app
from presentation.ctrader.ctrader_samples import (
    SIM_ACCOUNT_ID,
    SIM_DIGITS,
    SIM_SYMBOL_ID,
    _make_account_list,
    _symbol_by_id_message,
    _symbols_list_message,
)
from presentation.ctrader.ctrader_simulation import simulate

app = typer.Typer(
    help="Manual test CLI for the cTrader Open API client (infrastructure.ctrader_client).",
    add_completion=False,
)
reactor: Any = _reactor

_ENV_KEYS = (
    "CTRADER_CLIENT_ID",
    "CTRADER_CLIENT_SECRET",
    "CTRADER_REFRESH_TOKEN",
    "CTRADER_ACCESS_TOKEN",
    "CTRADER_ACCOUNT_LOGIN",
    "CTRADER_SYMBOL",
    "CTRADER_HOST",
    "CTRADER_PORT",
)


@app.command()
def settings() -> None:
    try:
        cfg = CTraderSettings.from_env()
    except CTraderError as exc:
        typer.echo(f"[settings] {exc}")
        typer.echo("Environment variable status:")
        for key in _ENV_KEYS:
            typer.echo(f"  {key} = {'set' if os.getenv(key) else 'unset'}")
        raise typer.Exit(code=1) from None
    typer.echo(
        json.dumps(
            {
                "client_id": cfg.client_id,
                "refresh_token": "<set>" if cfg.refresh_token else None,
                "access_token": "<set>" if cfg.access_token else None,
                "account_login": cfg.account_login,
                "symbol": cfg.symbol,
                "host": cfg.host,
                "port": cfg.port,
                "is_live": cfg.is_live,
                "has_token": cfg.has_token,
            },
            indent=2,
        )
    )


@app.command()
def decode(
    raw: int = typer.Argument(..., help="Raw integer price from cTrader (e.g. 260340000)"),
    digits: int = typer.Argument(..., help="Symbol digits (e.g. 5 for XAUUSD)"),
) -> None:
    typer.echo(f"decode_price(raw={raw}, digits={digits}) = {decode_price(raw, digits)}")


@app.command()
def rate(
    pip_position: int = typer.Argument(..., help="Pip decimal position (e.g. 4 -> 0.0001)"),
    digits: int = typer.Argument(..., help="Digits for point size (e.g. 5 -> 0.00001)"),
) -> None:
    typer.echo(f"pip_size(pip_position={pip_position}) = {pip_size(pip_position)}")
    typer.echo(f"point(digits={digits}) = {point(digits)}")


@app.command(name="build")
def build_msgs() -> None:
    account_id = SIM_ACCOUNT_ID
    symbol_id = SIM_SYMBOL_ID
    messages = {
        "application_auth": build_application_auth_request("cid", "secret"),
        "get_account_list": build_get_account_list_request("access_token"),
        "account_auth": build_account_auth_request(account_id, "access_token"),
        "symbols_list": build_symbols_list_request(account_id),
        "symbol_by_id": build_symbol_by_id_request(account_id, symbol_id),
        "subscribe_spots": build_subscribe_spots_request(account_id, [symbol_id]),
        "subscribe_depth": build_subscribe_depth_request(account_id, symbol_id),
        "get_tick_data": build_get_tick_data_request(account_id, symbol_id, 1700000000, 1700003600),
    }
    for name, msg in messages.items():
        typer.echo(f"[build] {name}: payloadType={msg.payloadType} full_name={msg.DESCRIPTOR.full_name}")
        typer.echo(f"  {msg}")


@app.command(name="parse")
def parse_msgs() -> None:
    digits = SIM_DIGITS

    accounts = parse_accounts(_make_account_list())
    typer.echo(f"[parse] accounts -> {accounts}")

    lights = parse_symbols_list(_symbols_list_message())
    typer.echo(f"[parse] symbols_list -> {lights}")

    sym = parse_symbol(_symbol_by_id_message(), lights[0])
    if sym is None:
        raise CTraderError("synthetic symbol response did not contain the requested symbol")
    typer.echo(f"[parse] symbol_by_id -> {sym}")
    typer.echo(
        f"        price_scale={sym.price_scale} pip_size={sym.pip_size} point={sym.point} "
        f"decode(260340000)={sym.decode_price(260340000)}"
    )

    spot = Protobuf.get("ProtoOASpotEvent")
    spot.ctidTraderAccountId = SIM_ACCOUNT_ID
    spot.symbolId = SIM_SYMBOL_ID
    spot.bid = 260340000
    spot.ask = 260360000
    spot.timestamp = int(__import__("time").time())
    typer.echo(f"[parse] spot -> {parse_spot_event(spot, digits)}")

    depth = Protobuf.get("ProtoOADepthEvent")
    depth.ctidTraderAccountId = SIM_ACCOUNT_ID
    depth.symbolId = SIM_SYMBOL_ID
    q = depth.newQuotes.add()
    q.id = 1
    q.size = 100000
    q.bid = 260330000
    q.ask = 260370000
    depth.deletedQuotes.append(2)
    typer.echo(f"[parse] depth -> {parse_depth_event(depth, digits)}")

    tick = Protobuf.get("ProtoOAGetTickDataRes")
    tick.ctidTraderAccountId = SIM_ACCOUNT_ID
    sample = tick.tickData.add()
    sample.timestamp = 1700000000
    sample.tick = 260340000
    tick.hasMore = False
    page: TickPage = parse_tick_data_page(tick, SIM_SYMBOL_ID)
    typer.echo(f"[parse] tick_page -> {page}")
    typer.echo(f"        decoded prices -> {page.decode_prices(digits)}")

    err = Protobuf.get("ProtoOAErrorRes")
    err.errorCode = "TEST_ERROR"
    err.description = "demo error"
    typer.echo(f"[parse] error -> {parse_error(err)}")


# =============================================================================
# New CLI commands for market data
# =============================================================================


def _report_live_error(command: str, stage: str) -> Callable[[Any], None]:
    def report(failure: Any) -> None:
        typer.echo(f"[{command}] {stage}: {failure}")
        reactor.stop()

    return report


def _parse_timerange(spec: str) -> tuple[int, int]:
    """Parse timerange string like '17-01-01.0-01TO17-12-31.23-59' into Unix timestamps.

    Format: YY-MM-DD.HH-MMTOYY-MM-DD.HH-MM (year assumed 2000+YY)
    """
    if "TO" not in spec:
        raise ValueError("Timerange must contain 'TO' separator")
    start_str, end_str = spec.split("TO", 1)

    def parse_part(part: str) -> int:
        # Format: YY-MM-DD.HH-MM
        if "." not in part:
            raise ValueError(f"Invalid timerange part: {part}")
        date_part, time_part = part.split(".", 1)
        yy, mm, dd = date_part.split("-")
        hh, mn = time_part.split("-")
        year = 2000 + int(yy)
        dt = datetime(year, int(mm), int(dd), int(hh), int(mn))
        return int(dt.timestamp())

    return parse_part(start_str), parse_part(end_str)


def _parse_timeframe(tf: str) -> timedelta:
    """Parse timeframe string like '1min', '5min', '1h', '1d' into timedelta."""
    tf = tf.lower().strip()
    if tf.endswith("min") or tf.endswith("m"):
        return timedelta(minutes=int(tf.rstrip("min").rstrip("m")))
    if tf.endswith("h"):
        return timedelta(hours=int(tf.rstrip("h")))
    if tf.endswith("d"):
        return timedelta(days=int(tf.rstrip("d")))
    # Default to minutes if just a number
    return timedelta(minutes=int(tf))


def _aggregate_ticks_to_candles(ticks: list[tuple[int, float]], timeframe: timedelta) -> list[dict]:
    """Aggregate tick data into OHLC candles for the given timeframe."""
    if not ticks:
        return []

    tf_seconds = int(timeframe.total_seconds())
    candles: dict[int, dict] = {}

    for ts, price in ticks:
        bucket = (ts // tf_seconds) * tf_seconds
        if bucket not in candles:
            candles[bucket] = {
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "timestamp": bucket,
            }
        else:
            c = candles[bucket]
            c["high"] = max(c["high"], price)
            c["low"] = min(c["low"], price)
            c["close"] = price

    return [candles[ts] for ts in sorted(candles.keys())]


@app.command(name="fetch-candles")
def fetch_candles(
    symbol: str = typer.Option("XAUUSD", "--symbol", "-s", help="Symbol name (e.g. XAUUSD)"),
    timeframe: str = typer.Option("1min", "--timeframe", "-t", help="Timeframe (e.g. 1min, 5min, 1h, 1d)"),
    timerange: Optional[str] = typer.Option(
        None,
        "--timerange",
        "-r",
        help=(
            "Time range in format YY-MM-DD.HH-MMTOYY-MM-DD.HH-MM "
            "(e.g. 17-01-01.0-01TO17-12-31.23-59). Defaults to last 1 hour."
        ),
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file (JSON). Prints to stdout if omitted."
    ),
) -> None:
    """Fetch historical tick data and aggregate into OHLC candles for the given timeframe.

    Note: cTrader Open API provides tick data, not candles directly. This command
    fetches ticks and aggregates them locally.
    """
    try:
        cfg = load_live_settings("fetch-candles")
    except CTraderError as exc:
        typer.echo(f"[fetch-candles] {exc}")
        raise typer.Exit(code=1) from None

    # Parse timerange
    if timerange:
        from_ts, to_ts = _parse_timerange(timerange)
    else:
        # Default: last 1 hour
        to_ts = int(time.time())
        from_ts = to_ts - 3600

    tf_delta = _parse_timeframe(timeframe)

    # Create client and connect
    client = CTraderClient(cfg)
    deferred_ready = client.wait_ready()

    def on_ready(account_id: int) -> None:
        typer.echo(f"[fetch-candles] Authenticated account={account_id}")
        # Resolve symbol
        resolve_deferred = client.resolve_symbol(symbol)

        def on_symbol(symbol_info) -> None:
            if symbol_info is None:
                typer.echo(f"[fetch-candles] Symbol '{symbol}' not found")
                reactor.stop()
                return
            typer.echo(f"[fetch-candles] Resolved {symbol} -> id={symbol_info.symbol_id}, digits={symbol_info.digits}")
            # Fetch tick data
            tick_deferred = client.fetch_tick_data(symbol_info.symbol_id, from_ts, to_ts)

            def on_ticks(page: TickPage) -> None:
                typer.echo(f"[fetch-candles] Received {len(page.ticks)} ticks")
                # Decode and aggregate
                ticks_data = page.decode_prices(symbol_info.digits)
                candles = _aggregate_ticks_to_candles(ticks_data, tf_delta)

                result = {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "from": datetime.fromtimestamp(from_ts).isoformat(),
                    "to": datetime.fromtimestamp(to_ts).isoformat(),
                    "candles": candles,
                }

                output_json = json.dumps(result, indent=2)
                if output:
                    with open(output, "w", encoding="utf-8") as f:
                        f.write(output_json)
                    typer.echo(f"[fetch-candles] Written {len(candles)} candles to {output}")
                else:
                    typer.echo(output_json)

                reactor.stop()

            tick_deferred.addCallback(on_ticks)
            tick_deferred.addErrback(_report_live_error("fetch-candles", "Fetch error"))

        resolve_deferred.addCallback(on_symbol)
        resolve_deferred.addErrback(_report_live_error("fetch-candles", "Resolve error"))

    deferred_ready.addCallback(on_ready)
    deferred_ready.addErrback(_report_live_error("fetch-candles", "Auth error"))

    client.connect()
    reactor.run()


@app.command(name="stream-orderbook")
def stream_orderbook(
    symbol: str = typer.Option("XAUUSD", "--symbol", "-s", help="Symbol name (e.g. XAUUSD)"),
    side: str = typer.Option("bid", "--side", help="Side to display: bid, ask, or both"),
    duration: int = typer.Option(0, "--duration", "-d", help="Duration in seconds (0 = run until Ctrl+C)"),
) -> None:
    """Stream order book (depth) updates for the given symbol.

    Subscribes to ProtoOADepthEvent and prints bid/ask level updates.
    """
    if side not in ("bid", "ask", "both"):
        typer.echo("[stream-orderbook] Side must be 'bid', 'ask', or 'both'")
        raise typer.Exit(code=1)

    try:
        cfg = load_live_settings("stream-orderbook")
    except CTraderError as exc:
        typer.echo(f"[stream-orderbook] {exc}")
        raise typer.Exit(code=1) from None

    client = CTraderClient(cfg)
    deferred_ready = client.wait_ready()

    def on_ready(account_id: int) -> None:
        typer.echo(f"[stream-orderbook] Authenticated account={account_id}")
        resolve_deferred = client.resolve_symbol(symbol)

        def on_symbol(symbol_info) -> None:
            if symbol_info is None:
                typer.echo(f"[stream-orderbook] Symbol '{symbol}' not found")
                reactor.stop()
                return
            typer.echo(
                f"[stream-orderbook] Resolved {symbol} -> id={symbol_info.symbol_id}, digits={symbol_info.digits}"
            )
            typer.echo(f"[stream-orderbook] Subscribing to order book (side={side})...")

            def on_depth(update) -> None:
                # Filter by side
                for quote in update.new_quotes:
                    if side in ("bid", "both") and quote.bid is not None:
                        typer.echo(f"  [BID] id={quote.quote_id} size={quote.size} price={quote.bid}")
                    if side in ("ask", "both") and quote.ask is not None:
                        typer.echo(f"  [ASK] id={quote.quote_id} size={quote.size} price={quote.ask}")
                for qid in update.deleted_quote_ids:
                    typer.echo(f"  [DEL] quote_id={qid}")

            client.on("depth", on_depth)
            client.subscribe_orderbook(symbol_info.symbol_id)

            if duration > 0:

                def stop_after_duration() -> None:
                    typer.echo(f"[stream-orderbook] Duration {duration}s reached, stopping...")
                    client.close()
                    reactor.stop()

                reactor.callLater(duration, stop_after_duration)

        resolve_deferred.addCallback(on_symbol)
        resolve_deferred.addErrback(_report_live_error("stream-orderbook", "Resolve error"))

    deferred_ready.addCallback(on_ready)
    deferred_ready.addErrback(_report_live_error("stream-orderbook", "Auth error"))

    client.connect()
    reactor.run()


@app.command(name="stream-trades")
def stream_trades(
    symbol: str = typer.Option("XAUUSD", "--symbol", "-s", help="Symbol name (e.g. XAUUSD)"),
    side: str = typer.Option("bid", "--side", help="Side to display: bid, ask, or both"),
    duration: int = typer.Option(0, "--duration", "-d", help="Duration in seconds (0 = run until Ctrl+C)"),
) -> None:
    """Stream trade/quote updates (ProtoOASpotEvent) for the given symbol.

    Subscribes to live spot ticks and prints bid/ask price updates.
    """
    if side not in ("bid", "ask", "both"):
        typer.echo("[stream-trades] Side must be 'bid', 'ask', or 'both'")
        raise typer.Exit(code=1)

    try:
        cfg = load_live_settings("stream-trades")
    except CTraderError as exc:
        typer.echo(f"[stream-trades] {exc}")
        raise typer.Exit(code=1) from None

    client = CTraderClient(cfg)
    deferred_ready = client.wait_ready()

    def on_ready(account_id: int) -> None:
        typer.echo(f"[stream-trades] Authenticated account={account_id}")
        resolve_deferred = client.resolve_symbol(symbol)

        def on_symbol(symbol_info) -> None:
            if symbol_info is None:
                typer.echo(f"[stream-trades] Symbol '{symbol}' not found")
                reactor.stop()
                return
            typer.echo(f"[stream-trades] Resolved {symbol} -> id={symbol_info.symbol_id}, digits={symbol_info.digits}")
            typer.echo(f"[stream-trades] Subscribing to trade stream (side={side})...")

            def on_spot(tick) -> None:
                if side in ("bid", "both") and tick.bid is not None:
                    typer.echo(f"  [BID] {tick.bid} @ {datetime.fromtimestamp(tick.timestamp).isoformat()}")
                if side in ("ask", "both") and tick.ask is not None:
                    typer.echo(f"  [ASK] {tick.ask} @ {datetime.fromtimestamp(tick.timestamp).isoformat()}")

            client.on("spot", on_spot)
            client.subscribe_tick_stream(symbol_info.symbol_id)

            if duration > 0:

                def stop_after_duration() -> None:
                    typer.echo(f"[stream-trades] Duration {duration}s reached, stopping...")
                    client.close()
                    reactor.stop()

                reactor.callLater(duration, stop_after_duration)

        resolve_deferred.addCallback(on_symbol)
        resolve_deferred.addErrback(_report_live_error("stream-trades", "Resolve error"))

    deferred_ready.addCallback(on_ready)
    deferred_ready.addErrback(_report_live_error("stream-trades", "Auth error"))

    client.connect()
    reactor.run()


app.command()(simulate)
app.add_typer(oauth_app, name="oauth")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
