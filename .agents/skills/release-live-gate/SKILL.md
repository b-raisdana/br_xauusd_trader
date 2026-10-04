---
name: release-live-gate
description: Use before demo deployment, live deployment, enabling real-money trading, increasing live risk, or declaring a release ready.
---

# Release / Live Gate

1. Read `docs/CURRENT_STATE.md` for the evidence baseline, plus
   [docs/todo/MT5-Python.Divergence.md](../../../docs/todo/MT5-Python.Divergence.md)
   for outstanding parity gaps. `LIVE_GATES.md`, `RULES.md` and `TEST_STATUS.md`
   do not exist in this checkout.
2. Verify the required stage evidence exists, and name its class: offline
   regression, recorded comparison, MQ5 compile, or native runtime parity.
   These are not interchangeable.
3. Check configuration/secrets are externalized and that no literal credential
   is committed.
4. Verify disable/rollback/kill path.
5. Verify observability and reconciliation appropriate to the execution venue.
6. Produce a GO/NO-GO recommendation with evidence.
7. Never enable real-money trading or increase material live risk without
   explicit Project Leader approval. A passing backtest is not that approval.
