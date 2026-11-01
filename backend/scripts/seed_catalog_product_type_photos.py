"""Replace catalog photos with royalty-free product-type images (Wikimedia Commons).

Searches Commons for each SKU (e.g. grab bar → grab bar photo), downloads a real
photo of that product *type* (not brand-specific), and replaces existing images.

Usage::

    cd backend
    python scripts/seed_catalog_product_type_photos.py --confirm
    python scripts/seed_catalog_product_type_photos.py --dry-run --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.livewell.catalog_image_service import HomeSafetyCatalogImageService
from app.livewell.catalog_service import normalize_catalog
from app.livewell.global_catalog_store import ensure_global_catalog_dict
from app.models.tenant import Tenant
from app.models.user import User
from app.seed_safehome_constants import TENANT_ADMIN_EMAIL, TENANT_NAME, LEGACY_TENANT_NAMES

USER_AGENT = "SafeHomeOps-CatalogSeed/1.1 (product-type photos; https://github.com/local)"

# Curated Commons search queries — tuned so results show the product type.
PRODUCT_QUERIES: dict[str, list[str]] = {
    "SVC-001": ["home health assessment", "doctor visiting patient home"],
    "SVC-002": ["accessible bathroom renovation", "bathroom grab bar installation"],
    "SVC-003": ["bedroom accessibility", "adjustable hospital bed"],
    "SVC-004": ["home inspection", "building inspector clipboard"],
    "SVC-005": ["nurse call button", "emergency call button wall", "panic button red"],
    "BTH-001": ["Grab bar.jpg", "Grab Bar.png", "bathroom grab bar"],
    "BTH-002": ["Grab bar.jpg", "Bathroom Disabled People.jpg", "toilet grab rail"],
    "BTH-003": ["Foldable U Profile Grab Bar.jpg", "folding grab bar"],
    "BTH-004": ["Foldable U Profile Grab Bar.jpg", "bathroom grab bar floor"],
    "BTH-005": ["Bathtub balance seat.jpg", "shower chair", "bath seat"],
    "BTH-011": ["thermostatic mixing valve", "shower mixer valve"],
    "BTH-006": ["raised toilet seat", "elevated toilet seat"],
    "BTH-007": ["toilet safety frame", "toilet support rails"],
    "BTH-008": ["anti-slip bathroom floor", "non-slip bathroom tiles"],
    "BTH-009": ["anti-slip tape bathroom", "non-slip strips shower"],
    "BTH-010": ["handheld shower head", "hand shower bathroom"],
    "BED-001": ["bed rail safety", "hospital bed side rail"],
    "BED-002": ["adjustable hospital bed", "electric profiling bed"],
    "BED-003": ["bed risers furniture", "bed elevator blocks"],
    "BED-004": ["motion sensor night light", "night light plug"],
    "BED-005": ["fall mat bedside", "crash mat bedside"],
    "LIV-001": ["round coffee table", "circular coffee table living room"],
    "LIV-002": ["corner guards furniture", "table corner protectors"],
    "LIV-003": ["rug pad underlay", "non-slip rug underlay"],
    "LIV-004": ["recliner chair", "lift chair recliner"],
    "EXT-001": ["outdoor handrail stairs", "stair handrail entrance"],
    "EXT-002": ["wheelchair ramp entrance", "portable wheelchair ramp"],
    "EXT-003": ["outdoor motion sensor light", "security floodlight motion"],
    "EXT-004": ["solar security light", "solar outdoor floodlight"],
    "HAL-001": ["motion sensor ceiling light", "PIR motion light"],
    "HAL-002": ["LED strip lighting", "LED tape light"],
    "HAL-003": ["hallway handrail", "corridor handrail"],
    "KIT-001": ["pull-down kitchen shelf", "descending kitchen cupboard"],
    "KIT-002": ["lazy susan kitchen", "turntable kitchen organizer"],
    "KIT-003": ["gas leak detector", "natural gas detector"],
    "KIT-004": ["smoke detector", "smoke alarm ceiling"],
    "KIT-006": ["carbon monoxide detector", "CO alarm"],
    "KIT-005": ["fire extinguisher", "ABC fire extinguisher"],
    "BAL-001": ["anti-slip outdoor coating", "non-slip balcony floor"],
    "BAL-002": ["balcony railing", "balcony safety railing"],
    "MOB-001": ["walking frame", "zimmer frame walker"],
    "MOB-002": ["rollator", "wheeled walker rollator"],
    "MOB-003": ["wheelchair", "manual wheelchair"],
    "MOB-004": ["transfer chair", "transport wheelchair"],
    "MOB-005": ["walking cane", "walking stick"],
    "MOB-006": ["quad cane", "four prong cane"],
    "MOB-007": ["portable wheelchair ramp", "threshold ramp"],
    "SMT-001": ["video doorbell", "smart doorbell camera"],
    "SMT-002": ["smart door lock", "electronic door lock"],
    "SMT-003": ["indoor security camera", "CCTV camera indoor"],
    "SMT-004": ["PIR motion sensor", "motion detector sensor"],
    "SMT-005": ["door contact sensor", "magnetic door sensor"],
    "SMT-006": ["wearable SOS wristband elder", "panic button watch gateway"],
    "SMT-011": ["emergency SOS wall button", "pendant panic button alarm"],
    "SMT-007": ["pill organizer reminder", "medication reminder device"],
    "SMT-008": ["smart speaker voice assistant", "Amazon Echo speaker"],
    "SMT-009": ["water leak sensor", "flood detector sensor"],
    "SMT-010": ["smart smoke detector", "connected smoke alarm"],
    "EMG-001": ["emergency contact list board", "emergency phone numbers poster"],
    "EMG-002": ["first aid kit", "first aid box"],
    "EMG-003": ["emergency flashlight", "LED flashlight"],
    "EMG-004": ["emergency backup light", "rechargeable emergency light"],
    "EMG-005": ["medical information folder", "patient medical records folder"],
    "WEL-001": ["home care nurse visit", "elder care home visit"],
    "WEL-002": ["elderly companion care", "senior companionship"],
    "WEL-003": ["pharmacy prescription pickup", "pharmacist medication"],
    "WEL-004": ["doctor appointment assistance", "patient with caregiver clinic"],
    "WEL-005": ["grocery shopping assistance", "elderly grocery shopping"],
    "WEL-006": ["video call elderly", "senior using tablet video call"],
    "WEL-007": ["personal hygiene care elderly", "bathing assistance elderly"],
    "WEL-008": ["home caregiver", "home health aide"],
    "WEL-009": ["live-in caregiver", "elderly home care"],
    "WEL-010": ["care coordination meeting", "case manager healthcare"],
    "WEL-011": ["personal care attendant", "ADL assistance elderly"],
    "WEL-012": ["benefits counseling elderly", "social worker senior"],
    "WEL-013": ["smartphone training elderly", "senior using smartphone"],
    "WEL-014": ["smart home installation", "home automation installer"],
    "HM-001": ["electrical safety inspection", "electrician checking panel"],
    "HM-002": ["plumbing inspection", "plumber inspecting pipes"],
    "HM-003": ["home maintenance repair", "handyman home repair"],
    "HM-004": ["plumber repairing sink", "plumbing repair"],
    "HM-005": ["electrician repairing wiring", "electrical repair"],
    "HM-006": ["carpenter woodworking", "carpenter repairing furniture"],
    "HM-007": ["appliance repair technician", "washing machine repair"],
    "HM-008": ["pest control spraying", "exterminator pest control"],
    "HM-009": ["deep cleaning home", "house cleaning service"],
    "HM-010": ["air conditioner service", "AC technician"],
    "NUR-001": ["home nurse visit", "nurse house call"],
    "NUR-002": ["home nursing care", "nurse elderly patient"],
    "NUR-003": ["live-in nursing care", "nurse overnight care"],
    "NUR-004": ["injection syringe nurse", "nurse giving injection"],
    "NUR-005": ["wound dressing nurse", "bandaging wound"],
    "NUR-006": ["urinary catheter", "catheter care"],
    "NUR-007": ["IV drip infusion", "intravenous therapy"],
    "PHY-001": ["physiotherapy assessment", "physical therapist evaluation"],
    "PHY-002": ["physiotherapy home session", "physical therapy elderly"],
    "PHY-003": ["physiotherapy exercise", "physical therapy session"],
    "DX-001": ["doctor home visit", "physician house call"],
    "DX-002": ["blood sample collection", "phlebotomy blood draw"],
    "DX-003": ["medical laboratory test", "blood test tubes lab"],
    "DX-004": ["ECG electrocardiogram", "ECG machine patient"],
    "PM-001": ["Home inspection", "building inspector clipboard"],
    "PM-002": ["electricity meter", "utility meter"],
    "PM-003": ["construction supervisor", "building contractor site"],
    "PM-004": ["house renovation scaffolding", "home remodeling construction"],
    "TRN-001": ["hospital transport wheelchair", "ambulance patient transport"],
    "TRN-002": ["hospital accompaniment elderly", "caregiver hospital wheelchair"],
    "TRN-003": ["airport wheelchair passenger", "wheelchair airport terminal"],
}

CATEGORY_FALLBACK: dict[str, list[str]] = {
    "BTH": ["accessible bathroom", "bathroom grab bar"],
    "BED": ["hospital bed", "bedroom accessibility"],
    "LIV": ["living room furniture", "recliner chair"],
    "EXT": ["wheelchair ramp", "entrance handrail"],
    "HAL": ["hallway lighting", "corridor handrail"],
    "KIT": ["kitchen safety", "smoke detector"],
    "BAL": ["balcony railing", "outdoor safety"],
    "MOB": ["mobility aid", "walker wheelchair"],
    "SMT": ["smart home device", "security camera"],
    "EMG": ["first aid kit", "emergency flashlight"],
    "SVC": ["home healthcare", "home inspection"],
    "WEL": ["elder care", "home caregiver"],
    "HM": ["home repair", "handyman"],
    "NUR": ["home nurse", "nursing care"],
    "PHY": ["physiotherapy", "physical therapy"],
    "DX": ["doctor visit", "medical examination"],
    "PM": ["property management", "home inspection"],
    "TRN": ["patient transport", "wheelchair assistance"],
}


def _resolve_dest_tenant(db, *, tenant_id: int | None, tenant_name: str | None) -> Tenant:
    if tenant_id is not None:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise SystemExit(f"Tenant id={tenant_id} not found")
        return tenant
    names: list[str] = []
    if tenant_name:
        names.append(tenant_name)
    names.extend([TENANT_NAME, *LEGACY_TENANT_NAMES])
    for name in names:
        tenant = db.query(Tenant).filter(Tenant.name == name).first()
        if tenant:
            return tenant
    tenant = (
        db.query(Tenant)
        .filter(Tenant.vertical == "LIVEWELL360")
        .order_by(Tenant.id)
        .first()
    )
    if tenant:
        return tenant
    raise SystemExit("No SafeHome tenant found")


def _resolve_user(db, tenant: Tenant, email: str | None) -> User:
    preferred = email or TENANT_ADMIN_EMAIL
    user = db.query(User).filter(User.email == preferred).first()
    if user and (user.role == "SYSTEM_ADMIN" or user.tenant_id == tenant.id):
        return user
    user = (
        db.query(User)
        .filter(
            User.tenant_id == tenant.id,
            User.role.in_(("TENANT_ADMIN", "CARE_MANAGER", "SYSTEM_ADMIN")),
        )
        .order_by(User.id)
        .first()
    )
    if user:
        return user
    user = db.query(User).filter(User.role == "SYSTEM_ADMIN").order_by(User.id).first()
    if user:
        return user
    raise SystemExit("No staff user found")


def _http_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def commons_get_file(title: str) -> tuple[str, str] | None:
    """Resolve a known Commons file title to a download URL."""
    if not title.lower().startswith("file:"):
        title = f"File:{title}"
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url|mime|size",
        "iiurlwidth": 960,
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    try:
        data = _http_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    pages = list(((data.get("query") or {}).get("pages") or {}).values())
    for page in pages:
        if page.get("missing") is not None:
            continue
        info = (page.get("imageinfo") or [{}])[0]
        mime = str(info.get("mime") or "")
        if mime not in ("image/jpeg", "image/png", "image/webp"):
            continue
        dl = info.get("thumburl") or info.get("url")
        if dl:
            return str(dl), str(page.get("title") or title)
    return None


def commons_search_image(query: str) -> tuple[str, str] | None:
    """Return (download_url, file_title) for first suitable Commons image."""
    # Direct file lookup when query looks like a Commons filename
    if query.lower().startswith("file:") or query.lower().endswith(
        (".jpg", ".jpeg", ".png", ".webp")
    ):
        direct = commons_get_file(query)
        if direct:
            return direct

    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": 12,
        "prop": "imageinfo",
        "iiprop": "url|mime|size",
        "iiurlwidth": 960,
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    try:
        data = _http_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    pages = list(((data.get("query") or {}).get("pages") or {}).values())
    # Prefer exact filename hits and jpeg/png
    scored: list[tuple[int, str, str]] = []
    q_lower = query.lower().replace(".jpg", "").replace(".png", "")
    for page in pages:
        title = str(page.get("title") or "")
        info = (page.get("imageinfo") or [{}])[0]
        mime = str(info.get("mime") or "")
        if mime not in ("image/jpeg", "image/png", "image/webp"):
            continue
        size = int(info.get("size") or 0)
        if size and size < 8_000:
            continue
        dl = info.get("thumburl") or info.get("url")
        if not dl:
            continue
        score = 0
        t_lower = title.lower()
        if q_lower in t_lower:
            score += 50
        for token in q_lower.split():
            if len(token) > 3 and token in t_lower:
                score += 10
        if mime == "image/jpeg":
            score += 5
        if "pdf" in t_lower or "diagram" in t_lower or "svg" in t_lower:
            score -= 30
        # Reject clearly off-topic Commons hits
        for bad in (
            "hydrazine",
            "military",
            "missile",
            "weapon",
            "aircraft",
            "logo",
            "coat of arms",
            "flag of",
            "map of",
            "screenshot",
            "horse",
            "trailer",
            "alien property",
            "swimming pool",
            "earthquake",
            "boeing",
            "credit-card",
            "credit card",
        ):
            if bad in t_lower:
                score -= 100
        scored.append((score, str(dl), title))

    scored = [s for s in scored if s[0] > -50]

    if not scored:
        return None
    scored.sort(key=lambda x: -x[0])
    return scored[0][1], scored[0][2]


def find_image_for_product(code: str, name: str, prefix: str) -> tuple[str, str, str] | None:
    queries = list(PRODUCT_QUERIES.get(code) or [])
    queries.append(name)
    queries.extend(CATEGORY_FALLBACK.get(prefix.upper(), ["home safety product"]))

    seen: set[str] = set()
    for q in queries:
        q = q.strip()
        if not q or q in seen:
            continue
        seen.add(q)
        hit = commons_search_image(q)
        time.sleep(0.35)  # be polite to Commons
        if hit:
            return hit[0], hit[1], q
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replace catalog images with Wikimedia product-type photos"
    )
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--tenant-id", type=int)
    parser.add_argument("--tenant-name")
    parser.add_argument("--user-email")
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--codes",
        help="Comma-separated product codes to process (e.g. BTH-001,BTH-002)",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Only products with no image_ids (default: replace all)",
    )
    args = parser.parse_args()
    if not args.dry_run and not args.confirm:
        parser.error("Pass --confirm or --dry-run")

    db = SessionLocal()
    try:
        tenant = _resolve_dest_tenant(
            db, tenant_id=args.tenant_id, tenant_name=args.tenant_name
        )
        user = _resolve_user(db, tenant, args.user_email)
        # Duck-typed actor: SYSTEM_ADMIN resolve_tenant_id ignores user.tenant_id.
        class _CatalogActor:
            def __init__(self, src: User, tid: int):
                self.id = src.id
                self.email = src.email
                self.role = "TENANT_ADMIN"
                self.tenant_id = tid

        actor = _CatalogActor(user, int(tenant.id))

        catalog = normalize_catalog(ensure_global_catalog_dict(db))
        products = list(catalog.get("products") or [])
        if args.codes:
            wanted = {c.strip().upper() for c in args.codes.split(",") if c.strip()}
            products = [
                p
                for p in products
                if str(p.get("product_code") or "").upper() in wanted
            ]
        if args.limit is not None:
            products = products[: args.limit]

        ok = 0
        failed: list[str] = []

        for product in products:
            pid = str(product.get("id") or "")
            code = str(product.get("product_code") or "")
            name = str(product.get("name") or pid)
            prefix = str(product.get("category_prefix") or "HM")
            existing = product.get("image_ids") or []
            if args.only_missing and existing:
                print(f"  skip {code} (has images)")
                continue

            print(f"  search {code} · {name} …", flush=True)
            found = find_image_for_product(code, name, prefix)
            if not found:
                failed.append(f"{code}: no Commons image")
                print(f"    FAIL no image", flush=True)
                continue

            dl_url, title, query = found
            print(f"    -> {title} (q={query!r})", flush=True)

            if args.dry_run:
                ok += 1
                continue

            try:
                content = _http_bytes(dl_url)
                if len(content) < 2000:
                    raise RuntimeError("download too small")
                mime = "image/jpeg"
                if dl_url.lower().endswith(".png") or "png" in title.lower():
                    mime = "image/png"
                elif dl_url.lower().endswith(".webp"):
                    mime = "image/webp"

                if existing:
                    HomeSafetyCatalogImageService.remove_all_for_product(
                        db, actor, product_id=pid
                    )
                # Refresh product list after remove (catalog mutated)
                HomeSafetyCatalogImageService.upload_for_product(
                    db,
                    actor,
                    product_id=pid,
                    file_name=f"{code or pid}_commons.jpg"
                    if mime == "image/jpeg"
                    else f"{code or pid}_commons.png",
                    content=content,
                    content_type=mime,
                )
                ok += 1
            except Exception as exc:
                failed.append(f"{code}: {exc}")
                print(f"    error: {exc}", file=sys.stderr, flush=True)

        print(f"Done. ok={ok} failed={len(failed)} dry_run={args.dry_run}")
        for line in failed[:30]:
            print(f"  {line}", file=sys.stderr)
        return 1 if failed and not args.dry_run else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
