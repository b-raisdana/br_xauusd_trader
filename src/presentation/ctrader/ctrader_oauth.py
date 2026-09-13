"""Live OAuth commands for the cTrader CLI."""

from __future__ import annotations

import json
from typing import Any

import typer

from infrastructure.ctrader_client import exchange_authorization_code, exchange_refresh_token

oauth_app = typer.Typer(help="OAuth2 token exchange (requires real credentials in .env).")


def _token_summary(token: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "access_token": token.access_token[:8] + "...",
        "expires_in": token.expires_in,
        "token_type": token.token_type,
        "scope": token.scope,
    }
    summary["refresh_token"] = token.refresh_token[:8] + "..." if token.refresh_token else None
    return summary


@oauth_app.command("refresh")
def oauth_refresh(
    client_id: str = typer.Option(..., "--client-id", envvar="CTRADER_CLIENT_ID"),
    client_secret: str = typer.Option(..., "--client-secret", envvar="CTRADER_CLIENT_SECRET"),
    refresh_token: str = typer.Option(..., "--refresh-token", envvar="CTRADER_REFRESH_TOKEN"),
) -> None:
    token = exchange_refresh_token(client_id, client_secret, refresh_token)
    typer.echo(json.dumps(_token_summary(token), indent=2))


@oauth_app.command("auth-code")
def oauth_auth_code(
    client_id: str = typer.Option(..., "--client-id", envvar="CTRADER_CLIENT_ID"),
    client_secret: str = typer.Option(..., "--client-secret", envvar="CTRADER_CLIENT_SECRET"),
    code: str = typer.Option(..., "--code"),
    redirect_uri: str = typer.Option(..., "--redirect-uri"),
) -> None:
    token = exchange_authorization_code(client_id, client_secret, code, redirect_uri)
    typer.echo(json.dumps(_token_summary(token), indent=2))
