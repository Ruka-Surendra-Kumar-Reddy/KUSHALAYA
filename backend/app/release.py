"""Release identity for this deployed tree.

`scripts/release.sh` rewrites RELEASE_ID when it builds a deploy tarball
(`rel-YYYYMMDD-HHMM`), and the same id is written to
`frontend/public/release.txt`. `/health`, `/health/ready` and `/health/live`
report it as "release" so a smoke test can prove which build is live.

"dev" means an unstamped working tree. Do not edit by hand.
"""

RELEASE_ID = "rel-test-full"
