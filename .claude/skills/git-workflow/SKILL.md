---
name: git-workflow
description: Use for Git/GitHub setup, commits, synchronization, branches or pull requests. Keep solo workflow simple while preserving rollback and remote backup.
---

# Git Workflow

The root AGENTS.md authorization and protected-branch policy govern every workflow below. Obtain explicit authorization for commits, branches, pushes and PRs; otherwise leave verified changes unstaged. Never treat connectivity or a verified batch as permission.

## Solo Standard default
- Keep `main` in a verified state.
- Respect configured protected branches; passing gates does not authorize a direct commit to `main`.
- Use a short-lived branch for risky, multi-commit or experimental changes.
- Push verified checkpoints to private GitHub remote.
- PR is optional for solo work unless change risk justifies review.

## Rapid MVP mode
- Keep local Git and the configured remote; they provide rollback and provenance at negligible runtime cost.
- Batch local commits at major verified boundaries instead of committing each implementation slice.
- Defer routine pushes, PRs and remote CI. Push only when explicitly requested by the Leader.
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
