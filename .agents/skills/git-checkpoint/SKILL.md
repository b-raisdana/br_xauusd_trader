---
name: git-checkpoint
description: Use when a coherent verified unit of work is ready to save or sync. Create safe Git checkpoints and keep the remote synchronized without destructive history operations.
---

# Git Checkpoint

1. Inspect `git status` and diff.
2. Ensure generated data, secrets and credentials are not staged.
3. Run relevant verification.
4. Stage only coherent intended changes.
5. Commit with a concise conventional message.
6. Push normally when remote exists and network is authorized.
7. Update `CURRENT_STATE.md` with the verified commit if required.
8. Do not force-push, rewrite important history, delete important remote refs, or change repository visibility without Leader approval.
