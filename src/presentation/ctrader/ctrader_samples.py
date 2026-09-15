"""Synthetic cTrader messages and sample identifiers used by the CLI."""

from __future__ import annotations

from typing import Any

from ctrader_open_api import Protobuf

SIM_SYMBOL_ID = 100
SIM_ACCOUNT_ID = 9011925
SIM_TICKER = "XAUUSD"
SIM_DIGITS = 5
SIM_PIP_POSITION = 4


def _make_account_list(account_id: int = SIM_ACCOUNT_ID, login: int = SIM_ACCOUNT_ID, is_live: bool = False) -> Any:
    msg = Protobuf.get("ProtoOAGetAccountListByAccessTokenRes")
    msg.accessToken = "fake_token"
    acct = msg.ctidTraderAccount.add()
    acct.ctidTraderAccountId = account_id
    acct.traderLogin = login
    acct.isLive = is_live
    return msg


def _symbols_list_message(symbol_id: int = SIM_SYMBOL_ID, name: str = SIM_TICKER) -> Any:
    msg = Protobuf.get("ProtoOASymbolsListRes")
    msg.ctidTraderAccountId = SIM_ACCOUNT_ID
    sym = msg.symbol.add()
    sym.symbolId = symbol_id
    sym.symbolName = name
    sym.enabled = True
    sym.description = "Gold vs USD"
    sym.baseAssetId = 1
    sym.quoteAssetId = 2
    return msg


def _symbol_by_id_message(symbol_id: int = SIM_SYMBOL_ID, name: str = SIM_TICKER, digits: int = SIM_DIGITS) -> Any:
    msg = Protobuf.get("ProtoOASymbolByIdRes")
    msg.ctidTraderAccountId = SIM_ACCOUNT_ID
    raw = msg.symbol.add()
    raw.symbolId = symbol_id
    raw.digits = digits
    raw.pipPosition = SIM_PIP_POSITION
    return msg
