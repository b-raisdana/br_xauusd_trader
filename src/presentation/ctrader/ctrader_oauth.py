"""Live OAuth commands for the cTrader CLI."""

from __future__ import annotations

import json
import os
import webbrowser
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import typer

from infrastructure.ctrader_client import (
    CTraderSettings,
    exchange_authorization_code,
    exchange_refresh_token,
)
from infrastructure.ctrader_client.models import CTraderError, TokenResponse
from infrastructure.ctrader_client.settings import DEFAULT_ENV_PATH

oauth_app = typer.Typer(help="OAuth2 token exchange (requires real credentials in .env).")
AUTHORIZATION_URL = "https://id.ctrader.com/my/settings/openapi/grantingaccess/"
DEFAULT_REDIRECT_URI = "http://localhost:8080/callback"


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


class _AuthCodeHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the authorization code from the redirect."""

    def __init__(self, *args: Any, code_holder: dict[str, str], **kwargs: Any) -> None:
        self.code_holder = code_holder
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if "code" in params:
            self.code_holder["code"] = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization successful!</h1><p>You can close this window.</p>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h1>Error: No authorization code received</h1>")

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress default log output
        pass


def _start_local_server(port: int, code_holder: dict[str, str]) -> HTTPServer:
    """Start a local HTTP server to capture the OAuth redirect."""

    def handler(*args: Any, **kwargs: Any) -> _AuthCodeHandler:
        return _AuthCodeHandler(*args, code_holder=code_holder, **kwargs)

    return HTTPServer(("localhost", port), handler)


def _open_browser(url: str) -> bool:
    """Open a URL in the host browser."""
    try:
        return webbrowser.open(url)
    except webbrowser.Error:
        return False


def authorize_interactively(
    client_id: str,
    client_secret: str,
    *,
    redirect_uri: str = DEFAULT_REDIRECT_URI,
    scope: str = "accounts",
    timeout: int = 300,
) -> TokenResponse:
    """Open cTrader authorization and capture its localhost callback."""
    parsed_redirect = urlparse(redirect_uri)
    if parsed_redirect.scheme != "http" or parsed_redirect.hostname not in {
        "localhost",
        "127.0.0.1",
    }:
        raise CTraderError(
            "Automatic OAuth requires an http://localhost redirect URI registered in cTrader.",
            code="CONFIG",
        )
    if parsed_redirect.port is None:
        raise CTraderError("CTRADER_REDIRECT_URI must include a localhost port.", code="CONFIG")
    if scope not in {"accounts", "trading"}:
        raise CTraderError("CTRADER_OAUTH_SCOPE must be 'accounts' or 'trading'.", code="CONFIG")

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "product": "web",
    }
    authorization_url = f"{AUTHORIZATION_URL}?{urlencode(params)}"
    code_holder: dict[str, str] = {}
    server = _start_local_server(parsed_redirect.port, code_holder)
    server.timeout = timeout
    typer.echo(f"[oauth] Opening browser for cTrader {scope!r} authorization.")
    opened = _open_browser(authorization_url)
    if not opened:
        typer.echo("[oauth] Browser launch failed; open this URL manually:")
        typer.echo(authorization_url)
    try:
        server.handle_request()
    finally:
        server.server_close()
    code = code_holder.get("code")
    if not code:
        raise CTraderError("Timed out or authorization callback contained no code.", code="OAUTH")
    return exchange_authorization_code(client_id, client_secret, code, redirect_uri)


def load_live_settings(command: str) -> CTraderSettings:
    """Load live-command settings, running the one-time OAuth grant if needed."""
    settings = CTraderSettings.from_env(require_token=False)
    if settings.has_token:
        return settings

    typer.echo(f"[{command}] No cTrader token found; starting one-time authorization.")
    redirect_uri = os.getenv("CTRADER_REDIRECT_URI", DEFAULT_REDIRECT_URI).strip()
    scope = os.getenv("CTRADER_OAUTH_SCOPE", "accounts").strip()
    token = authorize_interactively(
        settings.client_id,
        settings.client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
    )
    if not token.refresh_token:
        raise CTraderError("cTrader returned no refresh token.", code="OAUTH")
    _update_env_file(DEFAULT_ENV_PATH, "CTRADER_REFRESH_TOKEN", token.refresh_token)
    typer.echo(f"[{command}] Authorization complete; refresh token saved to .env.")
    return replace(
        settings,
        refresh_token=token.refresh_token,
        access_token=token.access_token,
    )


@oauth_app.command("init")
def oauth_init(
    client_id: str = typer.Option(..., "--client-id", envvar="CTRADER_CLIENT_ID"),
    client_secret: str = typer.Option(..., "--client-secret", envvar="CTRADER_CLIENT_SECRET"),
    redirect_port: int = typer.Option(8080, "--port", help="Local port for OAuth redirect"),
    redirect_path: str = typer.Option("/callback", "--path", help="Redirect path"),
    save_to_env: bool = typer.Option(True, "--save/--no-save", help="Save refresh token to .env file"),
    env_file: str = typer.Option(".env", "--env-file", help="Path to .env file"),
    scope: str = typer.Option("accounts", "--scope", help="OAuth scope: accounts or trading"),
) -> None:
    """Automate the one-time OAuth authorization grant.

    Starts a local server, opens the browser to the cTrader authorization URL,
    captures the redirect with the authorization code, exchanges it for tokens,
    and optionally saves the refresh token to .env.
    """
    redirect_uri = f"http://localhost:{redirect_port}{redirect_path}"
    token = authorize_interactively(
        client_id,
        client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
    )
    typer.echo(json.dumps(_token_summary(token), indent=2))
    if save_to_env and token.refresh_token:
        _update_env_file(env_file, "CTRADER_REFRESH_TOKEN", token.refresh_token)
        typer.echo(f"[oauth init] Refresh token saved to {env_file}")


def _update_env_file(env_path: str | os.PathLike[str], key: str, value: str) -> None:
    """Update or add a key=value pair in a .env file."""
    path = Path(env_path)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True) if path.exists() else []

    # Remove existing key
    lines = [line for line in lines if not line.startswith(f"{key}=")]

    # Add new key=value
    lines.append(f"{key}={value}\n")

    path.write_text("".join(lines), encoding="utf-8")
    path.chmod(0o600)
