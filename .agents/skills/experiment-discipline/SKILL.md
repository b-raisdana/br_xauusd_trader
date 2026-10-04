---
name: experiment-discipline
description: Use when designing, running or interpreting trading backtests, parameter comparisons, robustness tests or other empirical experiments.
---

# Experiment Discipline

Before run:
1. State hypothesis.
2. Lock dataset/range/version when practical.
3. State cost model.
4. Define variants.
5. Define primary metric and acceptance threshold.
6. Identify leakage/look-ahead risks.

During run:
- preserve configs and artifacts;
- do not silently alter rules after seeing outcomes;
- distinguish exploratory from confirmatory runs.

After run:
- record positive and negative results;
- report effect size, trade/sample count and relevant uncertainty;
- perform sensitivity/robustness checks proportional to decision impact;
- persist complete final metrics, config/data/code provenance, failures and
  interpretation limits as a structured artifact, then reference that artifact
  from `docs/CURRENT_STATE.md` rather than restating it in prose;
- generate later summaries from the stored evidence without rerunning the
  experiment;
- only the Leader promotes behavior to confirmed Rules.

`docs/EXPERIMENTS.md`, `docs/FINAL_TEST_REPORT.md` and
`docs/FINAL_TEST_EVIDENCE.json` do not exist in this checkout. Create an
artifact only when there is experiment evidence to store; do not report a
missing file as a blocker.
