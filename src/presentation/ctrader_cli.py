"""Manual test CLI for the cTrader Open API client."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import typer
from ctrader_open_api import Protobuf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infrastructure.ctrader_client import (  # noqa: E402
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
from infrastructure.ctrader_client.models import CTraderError, TickPage  # noqa: E402
from infrastructure.ctrader_client.streams import (  # noqa: E402
    parse_accounts,
    parse_depth_event,
    parse_error,
    parse_spot_event,
    parse_symbol,
    parse_symbols_list,
    parse_tick_data_page,
)
from presentation.ctrader_oauth import oauth_app  # noqa: E402
from presentation.ctrader_samples import (  # noqa: E402
    SIM_ACCOUNT_ID,
    SIM_DIGITS,
    SIM_SYMBOL_ID,
    _make_account_list,
    _symbol_by_id_message,
    _symbols_list_message,
)
from presentation.ctrader_simulation import simulate  # noqa: E402

app = typer.Typer(
    help="Manual test CLI for the cTrader Open API client (infrastructure.ctrader_client).",
    add_completion=False,
)

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
        typer.echo(
            f"[build] {name}: payloadType={msg.payloadType} full_name={msg.DESCRIPTOR.full_name}"
        )
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


app.command()(simulate)
app.add_typer(oauth_app, name="oauth")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
