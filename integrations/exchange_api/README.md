# Exchange / Broker API Profile

Use this for crypto, equities or other venues accessed by API.

## Adapter boundary
Keep trading logic separate from the venue client.

Typical boundary:
- market data adapter;
- order adapter;
- account/position adapter;
- clock/session adapter;
- reconciliation/logging.

## Environments
Prefer:
1. historical/replay;
2. testnet/paper if available;
3. shadow mode;
4. limited live;
5. scale after evidence.

## Record explicitly
- rate limits;
- precision/minimum order rules;
- fee tiers;
- time synchronization;
- retry/idempotency behavior;
- partial fills;
- order state transitions;
- reconnect/recovery behavior.

Never commit API secrets.
