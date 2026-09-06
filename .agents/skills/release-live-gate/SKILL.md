---
name: release-live-gate
description: Use before demo deployment, live deployment, enabling real-money trading, increasing live risk, or declaring a release ready.
---

# Release / Live Gate

1. Read `LIVE_GATES.md`, Rules, Test Status and current risk constraints.
2. Verify the required stage evidence.
3. Check configuration/secrets are externalized.
4. Verify disable/rollback/kill path.
5. Verify observability and reconciliation appropriate to the execution venue.
6. Produce GO/NO-GO recommendation with evidence.
7. Never enable real-money trading or increase material live risk without explicit Project Leader approval.
