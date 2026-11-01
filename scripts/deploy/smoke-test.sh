#!/usr/bin/env bash
# Post-deploy smoke test for Kushalaya — runs on the VM or a laptop; only
# needs curl. Read-only GETs, plus one login POST when credentials are given.
#
#   bash scripts/deploy/smoke-test.sh                                  # production hosts
#   bash scripts/deploy/smoke-test.sh --release rel-20260930-0900      # also assert the release id
#   bash scripts/deploy/smoke-test.sh staging-ops.kushalaya.com staging-www.kushalaya.com staging-family.kushalaya.com
#   SMOKE_STAFF_EMAIL=... SMOKE_STAFF_PASSWORD=... bash scripts/deploy/smoke-test.sh
#
# Positional args: [OPS] [WWW] [FAMILY] — hostnames or full base URLs.
# Env defaults:    SMOKE_OPS_BASE / SMOKE_WWW_BASE / SMOKE_FAMILY_BASE,
#                  SMOKE_RELEASE (same as --release), SMOKE_STAFF_EMAIL / _PASSWORD,
#                  SMOKE_TIMEOUT (seconds per request, default 20).
#
# Checks (FAIL = non-zero exit; WARN never fails the run):
#   ops    /health                      200, "release" == expected id (when known)
#   ops    /health/ready                200
#   ops    /release.txt                 == expected id (WARN if missing)
#   www    /                            200 and contains id="founder"
#   ops    /login   (Sec-Fetch-Dest: document)   200
#   family /login                       200
#   family /        no cookie           307 -> /login
#   ops    /dashboard no cookie         307 -> /login?redirect=
#   ops    POST /api/v1/auth/login      access_token  (SKIP when SMOKE_STAFF_* unset)
#   ops    GET  /api/v1/care/incidents/summary  200 with that token (WARN on 404 until it ships)
#   ops    /brand/<header png>?v=<BRAND_ASSET_VERSION from lib/brand-assets.ts>  200 image/png

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT_GUESS="$(cd "$SCRIPT_DIR/../.." && pwd)"

OPS="${SMOKE_OPS_BASE:-ops.kushalaya.com}"
WWW="${SMOKE_WWW_BASE:-www.kushalaya.com}"
FAMILY="${SMOKE_FAMILY_BASE:-family.kushalaya.com}"
EXPECT_RELEASE="${SMOKE_RELEASE:-}"
TIMEOUT="${SMOKE_TIMEOUT:-20}"
STAFF_EMAIL="${SMOKE_STAFF_EMAIL:-}"
STAFF_PASSWORD="${SMOKE_STAFF_PASSWORD:-}"

declare -a POS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --release) EXPECT_RELEASE="${2:?}"; shift 2 ;;
    --timeout) TIMEOUT="${2:?}"; shift 2 ;;
    --help|-h) sed -n '2,27p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "Unknown option: $1" >&2; exit 2 ;;
    *) POS+=("$1"); shift ;;
  esac
done
[[ ${#POS[@]} -ge 1 ]] && OPS="${POS[0]}"
[[ ${#POS[@]} -ge 2 ]] && WWW="${POS[1]}"
[[ ${#POS[@]} -ge 3 ]] && FAMILY="${POS[2]}"

base() { case "$1" in http://*|https://*) echo "${1%/}" ;; *) echo "https://${1%/}" ;; esac; }
OPS="$(base "$OPS")"; WWW="$(base "$WWW")"; FAMILY="$(base "$FAMILY")"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PASS=0; FAIL=0; WARN=0; SKIP=0
declare -a ROWS=()
row() { # status name detail
  ROWS+=("$(printf '%-4s  %-42s  %s' "$1" "$2" "$3")")
  case "$1" in PASS) PASS=$((PASS+1));; FAIL) FAIL=$((FAIL+1));; WARN) WARN=$((WARN+1));; SKIP) SKIP=$((SKIP+1));; esac
}

# fetch NAME URL [curl args...] -> sets CODE, HDRS (file), BODY (file), LOCATION, CTYPE
fetch() {
  local name="$1" url="$2"; shift 2
  local safe; safe="$(printf '%s' "$name" | tr -c 'A-Za-z0-9' '_')"
  HDRS="$TMP/$safe.h"; BODY="$TMP/$safe.b"
  CODE="$(curl -sS -o "$BODY" -D "$HDRS" -w '%{http_code}' --max-time "$TIMEOUT" "$@" "$url" 2>"$TMP/$safe.err")" || CODE="000"
  LOCATION="$(grep -i '^location:' "$HDRS" 2>/dev/null | tail -1 | sed 's/^[Ll]ocation:[[:space:]]*//' | tr -d '\r')"
  CTYPE="$(grep -i '^content-type:' "$HDRS" 2>/dev/null | tail -1 | sed 's/^[Cc]ontent-[Tt]ype:[[:space:]]*//' | tr -d '\r')"
  ERR="$(head -c 200 "$TMP/$safe.err" 2>/dev/null | tr -d '\r\n')"
}
json_field() { # file key -> value of "key":"value" (first)
  grep -o "\"$2\":\"[^\"]*\"" "$1" 2>/dev/null | head -1 | sed -E 's/^"[^"]*":"//; s/"$//'
}

# --- ops /health --------------------------------------------------------------
fetch "ops health" "$OPS/health"
live_release="$(json_field "$BODY" release)"
if [[ "$CODE" == "200" ]]; then
  if [[ -n "$EXPECT_RELEASE" ]]; then
    if [[ "$live_release" == "$EXPECT_RELEASE" ]]; then row PASS "ops /health" "200 release=$live_release"
    else row FAIL "ops /health" "200 but release=${live_release:-<none>} expected $EXPECT_RELEASE"; fi
  else
    row PASS "ops /health" "200 release=${live_release:-<none>}"
  fi
else
  row FAIL "ops /health" "HTTP $CODE ${ERR}"
fi

fetch "ops ready" "$OPS/health/ready"
[[ "$CODE" == "200" ]] && row PASS "ops /health/ready" "200 status=$(json_field "$BODY" status)" \
  || row FAIL "ops /health/ready" "HTTP $CODE $(head -c 160 "$BODY" 2>/dev/null | tr -d '\n') ${ERR}"

fetch "ops release txt" "$OPS/release.txt"
web_release="$(tr -d '[:space:]' <"$BODY" 2>/dev/null)"
if [[ "$CODE" == "200" ]]; then
  if [[ -n "$EXPECT_RELEASE" && "$web_release" != "$EXPECT_RELEASE" ]]; then
    row FAIL "ops /release.txt" "web build is $web_release, expected $EXPECT_RELEASE (frontend not rebuilt?)"
  elif [[ -n "$live_release" && "$web_release" != "$live_release" ]]; then
    row WARN "ops /release.txt" "web=$web_release api=$live_release differ"
  else
    row PASS "ops /release.txt" "$web_release"
  fi
else
  row WARN "ops /release.txt" "HTTP $CODE (not deployed yet?)"
fi

# --- www / ---------------------------------------------------------------------
fetch "www root" "$WWW/" -H "Sec-Fetch-Dest: document" -H "Accept: text/html"
if [[ "$CODE" == "200" ]]; then
  if grep -q 'id="founder"' "$BODY"; then row PASS "www /" "200, founder section present"
  else row FAIL "www /" "200 but id=\"founder\" missing (marketing page not served?)"; fi
else
  row FAIL "www /" "HTTP $CODE ${ERR}"
fi

# --- logins --------------------------------------------------------------------
fetch "ops login" "$OPS/login" -H "Sec-Fetch-Dest: document" -H "Accept: text/html"
[[ "$CODE" == "200" ]] && row PASS "ops /login" "200" || row FAIL "ops /login" "HTTP $CODE ${ERR}"

fetch "family login" "$FAMILY/login" -H "Sec-Fetch-Dest: document" -H "Accept: text/html"
[[ "$CODE" == "200" ]] && row PASS "family /login" "200" || row FAIL "family /login" "HTTP $CODE ${ERR}"

# --- redirects (no cookie) -----------------------------------------------------
fetch "family root" "$FAMILY/" -H "Sec-Fetch-Dest: document" -H "Accept: text/html"
if [[ "$CODE" == "307" && "$LOCATION" == */login* ]]; then row PASS "family / (no cookie)" "307 -> $LOCATION"
else row FAIL "family / (no cookie)" "HTTP $CODE location=${LOCATION:-<none>} (want 307 -> /login)"; fi

fetch "ops dashboard" "$OPS/dashboard" -H "Sec-Fetch-Dest: document" -H "Accept: text/html"
if [[ "$CODE" == "307" && "$LOCATION" == */login?redirect=* ]]; then row PASS "ops /dashboard (no cookie)" "307 -> $LOCATION"
else row FAIL "ops /dashboard (no cookie)" "HTTP $CODE location=${LOCATION:-<none>} (want 307 -> /login?redirect=)"; fi

# --- staff login + incidents summary -------------------------------------------
TOKEN=""
if [[ -n "$STAFF_EMAIL" && -n "$STAFF_PASSWORD" ]]; then
  # Build the JSON with python when available so odd characters survive.
  if command -v python3 >/dev/null 2>&1; then
    payload="$(SMOKE_STAFF_EMAIL="$STAFF_EMAIL" SMOKE_STAFF_PASSWORD="$STAFF_PASSWORD" python3 -c 'import json,os;print(json.dumps({"email":os.environ["SMOKE_STAFF_EMAIL"],"password":os.environ["SMOKE_STAFF_PASSWORD"]}))')"
  else
    payload="{\"email\":\"$STAFF_EMAIL\",\"password\":\"$STAFF_PASSWORD\"}"
  fi
  fetch "staff login" "$OPS/api/v1/auth/login" -X POST -H "Content-Type: application/json" --data "$payload"
  TOKEN="$(json_field "$BODY" access_token)"
  if [[ "$CODE" == "200" && -n "$TOKEN" ]]; then row PASS "POST /api/v1/auth/login" "200 token for $STAFF_EMAIL"
  else row FAIL "POST /api/v1/auth/login" "HTTP $CODE $(head -c 120 "$BODY" | tr -d '\n')"; fi

  if [[ -n "$TOKEN" ]]; then
    fetch "incidents summary" "$OPS/api/v1/care/incidents/summary" -H "Authorization: Bearer $TOKEN"
    case "$CODE" in
      200) row PASS "GET /api/v1/care/incidents/summary" "200" ;;
      404) row WARN "GET /api/v1/care/incidents/summary" "404 — endpoint not deployed yet (tolerated)" ;;
      *) row FAIL "GET /api/v1/care/incidents/summary" "HTTP $CODE $(head -c 120 "$BODY" | tr -d '\n')" ;;
    esac
  else
    row SKIP "GET /api/v1/care/incidents/summary" "no token"
  fi
else
  row SKIP "POST /api/v1/auth/login" "SMOKE_STAFF_EMAIL / SMOKE_STAFF_PASSWORD unset"
  row SKIP "GET /api/v1/care/incidents/summary" "no token"
fi

# --- brand asset with the ?v= from lib/brand-assets.ts -------------------------
BRAND_TS=""
for cand in "$APP_ROOT_GUESS/frontend/lib/brand-assets.ts" "/opt/safehomeops/app/frontend/lib/brand-assets.ts"; do
  [[ -f "$cand" ]] && { BRAND_TS="$cand"; break; }
done
if [[ -n "$BRAND_TS" ]]; then
  ver="$(grep -oE 'BRAND_ASSET_VERSION = "[^"]+"' "$BRAND_TS" | sed -E 's/.*"([^"]+)"/\1/')"
  png="$(grep -oE 'header: versioned\("[^"]+"\)' "$BRAND_TS" | sed -E 's/.*"([^"]+)".*/\1/')"
  [[ -n "$png" ]] || png="/brand/kushalaya-header.png"
  if [[ -n "$ver" ]]; then
    fetch "brand png" "$OPS$png?v=$ver"
    if [[ "$CODE" == "200" && "$CTYPE" == image/png* ]]; then row PASS "ops $png?v=$ver" "200 $CTYPE"
    else row FAIL "ops $png?v=$ver" "HTTP $CODE type=${CTYPE:-<none>}"; fi
  else
    row WARN "brand png" "BRAND_ASSET_VERSION not found in $BRAND_TS"
  fi
else
  row WARN "brand png" "lib/brand-assets.ts not found next to this script — skipped"
fi

# --- report --------------------------------------------------------------------
echo ""
echo "Smoke test  ops=$OPS  www=$WWW  family=$FAMILY${EXPECT_RELEASE:+  expect=$EXPECT_RELEASE}"
printf '%-4s  %-42s  %s\n' "----" "------------------------------------------" "----------------------------------------"
printf '%s\n' "${ROWS[@]}"
printf '%-4s  %-42s  %s\n' "----" "------------------------------------------" "----------------------------------------"
echo "PASS=$PASS FAIL=$FAIL WARN=$WARN SKIP=$SKIP"
[[ "$FAIL" -eq 0 ]] || { echo "SMOKE TEST FAILED"; exit 1; }
echo "SMOKE TEST OK"
