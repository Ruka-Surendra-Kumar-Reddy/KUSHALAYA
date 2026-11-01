# Deploy and operations documents

| Document | Read it when |
|---|---|
| [OPERATIONS.md](OPERATIONS.md) | you need the server list, service list, reboot checklist or incident history |
| [DEPLOY_UPDATE.md](DEPLOY_UPDATE.md) | you are shipping a change to production (tarball method, rollback) |
| [GIT_WORKFLOW.md](GIT_WORKFLOW.md) | branches, protection rules, CI secret, deploy keys, release tags |
| [TEST_INSTANCE.md](TEST_INSTANCE.md) | anything about the test server: install, DNS, flow test → prod |
| [PROD_RESET.md](PROD_RESET.md) | wiping production data while keeping configuration and named staff |
| [POSTGRES_BACKUP.md](POSTGRES_BACKUP.md) | backups and restore |

Scripts referenced by these documents live in `scripts/` and `scripts/deploy/`.
The repository-level rules for agents and new engineers are in the root `CLAUDE.md`.
