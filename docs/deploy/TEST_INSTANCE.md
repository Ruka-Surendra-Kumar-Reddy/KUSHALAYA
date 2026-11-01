# Test instance (separate VM)

Owner decision 2026-11-01: a **separate** server for testing, not a second copy on
the production box. Every change goes to test first, the owner checks it on the
three screens (phone 390 / tablet 768 / laptop 1440), then the identical release
goes to production.

## Servers

| | Production | Test |
|---|---|---|
| OCI instance | `instance-eldercareops` (AD-1) | `instance-kushalaya-test` (AD-1) |
| Public IP | `129.213.45.105` | `150.136.230.200` |
| Shape | A1.Flex 1 OCPU / 6 GB | A1.Flex 2 OCPU / 12 GB (10 GB usable) |
| OS | Oracle Linux 9 | Oracle Linux 9.8 (fresh, created 2026-11-01 14:29 UTC) |
| SSH | `ssh -i _ssh/oracle_safehome_vm opc@129.213.45.105` | `ssh -i _ssh/oracle_safehome_vm opc@150.136.230.200` (same key) |
| VCN / subnet | `vcn-20260531-1942`, public subnet | same |
| Sites | www / ops / family `.kushalaya.com` | `test` / `test-ops` / `test-family` `.kushalaya.com` |
| Ports | API 8010, web 3010 | API 8010, web 3010 (own box, same ports) |
| Database | `safehomeops` on the box | `safehomeops` on the test box, **demo seed, no prod data** |
| Watch broker / ingestor | runs here (`ops.kushalaya.com`) | **not installed** — test can never receive a real SOS |
| Mobile apps | point here | not pointed here (test build later if wanted) |

The third free-tier instance, `instance-20260511-0906` (`129.158.220.48`, AD-2), is
**not** the broker and is not referenced anywhere in the repo. Nobody has its SSH key.
Leave it alone or terminate it to free quota; it is not used by anything we know of.

## What the test box gets

- Same install path as prod: `scripts/deploy/deploy-safehome.sh` with
  `/etc/workforceos/safehome.env` written from `scripts/deploy/deploy.test.env.example`.
- Own secrets: new `SECRET_KEY`, new DB password, **Razorpay test keys only**, SMS and
  email providers set to `log` so no real family is ever contacted.
- `ENVIRONMENT=test`, `noindex` header on every host, a yellow "TEST SYSTEM" band.
- Code comes from GitHub (`Ruka-Surendra-Kumar-Reddy/KUSHALAYA` + `krishnaposa/workforceos-core`,
  branch `develop`) via a **read-only deploy key generated on the test box**. Day-to-day
  test deploys are `git pull` + `start-livewell.sh`; production stays on the tarball method.

## Owner actions (one-time)

1. **DNS** — three A records at the registrar, all → `150.136.230.200`:
   `test.kushalaya.com`, `test-ops.kushalaya.com`, `test-family.kushalaya.com`.
2. **GitHub deploy key** — add the public key printed during setup as a *read-only*
   Deploy key on both repos: Settings → Deploy keys → Add deploy key
   (`Ruka-Surendra-Kumar-Reddy/KUSHALAYA` and `krishnaposa/workforceos-core`).
3. **Razorpay test keys** (optional) — from the Razorpay dashboard in Test mode; without
   them the wallet uses the built-in stub.

## Release flow after setup

1. Push the change to `develop` (git-push recipe in memory).
2. On test: `sudo -u safehomeops -i bash -lc 'cd /opt/safehomeops/app && git pull && bash scripts/start-livewell.sh'`
3. Owner verifies on test at three widths.
4. Promote to prod with the usual tarball (`scripts/release.sh`) — same files, no rebuild of the decision.

## Status log

- 2026-11-01 — instance created by the owner from the OCI console; SSH with the prod key
  confirmed; box is clean (only Python 3.9, firewalld allows ssh only, outbound HTTPS works).
- Next: deploy key → owner adds to GitHub → DNS → `deploy-safehome.sh` → TLS → seed demo → smoke test.
