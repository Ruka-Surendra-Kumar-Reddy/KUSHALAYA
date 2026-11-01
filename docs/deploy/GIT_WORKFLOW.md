# Git workflow — KUSHALAYA repo

Repo: https://github.com/Ruka-Surendra-Kumar-Reddy/KUSHALAYA (created 2026-11-01, replaces
`krishnaposa/SafeHomeOps`). Shared package stays at `krishnaposa/workforceos-core`.

## Branches

| Branch | Deploys to | Who pushes |
|---|---|---|
| `develop` | test box (`test-ops.kushalaya.com`) | everyone, by push or PR |
| `main` | production | nobody directly — only PRs from `develop` |

Each production release is tagged `vYYYY.MM.DD` (add `-2` for a second one the same day).
No permanent `testing` branch: test already runs `develop`. For a frozen candidate, branch
`release/<date>` from `develop`, fix on it, merge to `main` and back to `develop`.

## Rules to set in GitHub (repo owner, one-time)

Settings → Branches → Add branch ruleset (or classic protection rule):

**`main`**
- Require a pull request before merging, 1 approval, dismiss stale approvals.
- Require status checks to pass: `Kushalaya CI / backend`, `Kushalaya CI / frontend`.
- Require linear history. Block force pushes. Block deletions. Include administrators.

**`develop`**
- Require status checks to pass (same two). Block force pushes. Block deletions.

Settings → Actions → Secrets: add `WORKFORCEOS_CORE_PAT` — a fine-grained token with read
access to `krishnaposa/workforceos-core`, otherwise CI cannot fetch the shared package.

Settings → Deploy keys: add the test box's read-only key (see `TEST_INSTANCE.md`), and the
production box's existing deploy key once prod is switched to this repo.

## Never in git

`backend/.env`, `frontend/.env.local`, `_ssh/`, `*.db`, `uploads/`, `mobile/android/keystore.properties`,
`*.jks`. `.gitignore` covers all of them. The previous repo tracked `backend/.env` with real
provider keys; those keys must be rotated.

## Day to day

```bash
git checkout develop && git pull
# work, run: cd frontend && npx tsc --noEmit && npx vitest run ; cd backend && pytest -q
git commit -am "..." && git push            # CI runs; test box pulls develop
# release: open PR develop -> main, merge, then
git tag v2026.11.01 main && git push --tags  # prod deploy uses this tag
```

The local working folder on the owner's PC was converted to a clone of this repo on
2026-11-01; before that pushes went through a scratch clone.
