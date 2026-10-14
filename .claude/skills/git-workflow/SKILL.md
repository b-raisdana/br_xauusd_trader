---
name: git-workflow
description: Use for Git/GitHub setup, commits, synchronization, branches or pull requests. Keep solo workflow simple while preserving rollback and remote backup.
---

# Git Workflow

## Solo Standard default
- Keep `main` in a verified state.
- Small coherent work may commit directly to `main` after gates pass.
- Use a short-lived branch for risky, multi-commit or experimental changes.
- Push verified checkpoints to private GitHub remote.
- PR is optional for solo work unless change risk justifies review.

## Rapid MVP mode
- Keep local Git and the configured remote; they provide rollback and provenance at negligible runtime cost.
- Batch local commits at major verified boundaries instead of committing each implementation slice.
- Defer routine pushes, PRs and remote CI. Push only when the Leader requests it or a remote recovery/release checkpoint materially justifies it.
- Git optimization must not weaken required strategy, risk, execution, compile or final acceptance checks.

## Team/Advanced
Use branches + PR + CI as the normal path.

## GitHub setup
When authenticated and authorized:
- initialize Git;
- create private repo via GitHub CLI if needed;
- set `origin`;
- push verified baseline.

Never:
- commit secrets;
- force-push important history without approval;
- change repository visibility without approval.
