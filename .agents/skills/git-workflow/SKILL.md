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
