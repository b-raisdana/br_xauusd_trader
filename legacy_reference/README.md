# Historical reference — not current strategy authority

This directory preserves technical migration provenance:

- `PREVIOUS_TECHNICAL_BUNDLE/`: extracted historical RAR5 bundle containing validated historical MQL5 predecessors, Python/PowerShell research tools, `.ini/.set` profiles, reference datasets and result artifacts.

Authority rules:

1. Current explicit Project Leader instruction and `docs/RULES.md` control active behavior.
2. Files here are used for Regression, reproducibility and forensic comparison only.
3. Historical code is known not to implement all current Rules.
4. Do not edit historical Evidence merely to make a checksum or current test pass.

Integrity notes:

- RAR inventory: 173 entries, 168 extracted files.
- `SHA256_KIT.txt`: all 16 listed files PASS.
- `SHA256_PATCH.txt`: historical inconsistency retained—`README_FA.md` hash mismatch and two missing `reversal_portfolio_reference/*` paths.
