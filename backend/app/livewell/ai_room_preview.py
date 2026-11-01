"""AI room preview helpers: privacy, room-unchanged check, watermark, prices, caps, usage, PDF.

Used by ai_visualization_service (job lifecycle) and ai_render_queue (background worker).
Pillow only — no numpy — so it runs on the VM as installed.
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.home_safety_ai_job import HomeSafetyAIJob

PNG_MAGIC = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
WATERMARK_TEXT = "KushAlaya · Illustration"
IST = timezone(timedelta(hours=5, minutes=30))

# Seconds shown as "about N s" while a render runs.
ESTIMATE_SECONDS = {"gemini_image": 12, "gpt_image": 60, "fal_kontext": 15, "local_stub": 2}

STAGE_LABELS = {
    "queued": "Waiting to start…",
    "preparing": "Uploading photo…",
    "generating": "Generating…",
    "checking": "Checking result…",
    "retrying": "Room changed — trying once more…",
    "saving": "Saving…",
    "done": "Ready for review",
    "failed": "Failed",
}
STAGE_PCT = {
    "queued": 5,
    "preparing": 15,
    "generating": 45,
    "checking": 80,
    "retrying": 55,
    "saving": 92,
    "done": 100,
    "failed": 100,
}


# --- Images ----------------------------------------------------------------------


def _pil():
    try:
        from PIL import Image  # noqa: F401

        return True
    except ImportError:  # pragma: no cover
        return False


def strip_exif(data: bytes, *, max_side: int = 1600) -> bytes:
    """Re-encode without EXIF/GPS/text chunks (orientation applied first); cap the size.

    Only the pixels leave the server. Unreadable input is returned unchanged (the
    provider will reject it anyway).
    """
    if not data or not _pil():
        return data
    from PIL import Image, ImageOps

    try:
        img = Image.open(io.BytesIO(data))
        fmt = (img.format or "JPEG").upper()
        img = ImageOps.exif_transpose(img)
        if max(img.size) > max_side:
            img.thumbnail((max_side, max_side))
        out = io.BytesIO()
        if fmt == "PNG":
            # New image object = no text/eXIf chunks carried over.
            clean = Image.new(img.mode, img.size)
            clean.paste(img)
            clean.save(out, format="PNG", optimize=True)
        else:
            clean = img.convert("RGB")
            clean.save(out, format="JPEG", quality=92)
        return out.getvalue()
    except Exception:
        return data


def has_exif(data: bytes) -> bool:
    if not data or not _pil():
        return False
    from PIL import Image

    try:
        img = Image.open(io.BytesIO(data))
        return bool(img.getexif()) or "exif" in img.info
    except Exception:
        return False


def _gray(data: bytes, size: int):
    from PIL import Image

    img = Image.open(io.BytesIO(data)).convert("L").resize((size, size), Image.BILINEAR)
    return list(img.getdata())


def room_similarity(source: bytes, result: bytes, *, size: int = 64, block: int = 8, keep: float = 0.7) -> float | None:
    """SSIM-like structural similarity of the room, ignoring the most-changed blocks.

    Both images are downscaled to `size`×`size` grey; SSIM is taken per `block`×`block`
    tile and the `keep` share of most-similar tiles is averaged, so the tiles where the
    products were added do not count against the room. 1.0 = identical.
    """
    if not source or not result or not _pil():
        return None
    try:
        a = _gray(source, size)
        b = _gray(result, size)
    except Exception:
        return None
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    scores: list[float] = []
    n = block * block
    for by in range(0, size, block):
        for bx in range(0, size, block):
            xs = [a[(by + j) * size + bx + i] for j in range(block) for i in range(block)]
            ys = [b[(by + j) * size + bx + i] for j in range(block) for i in range(block)]
            mx = sum(xs) / n
            my = sum(ys) / n
            vx = sum((x - mx) ** 2 for x in xs) / n
            vy = sum((y - my) ** 2 for y in ys) / n
            cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
            s = ((2 * mx * my + c1) * (2 * cov + c2)) / ((mx * mx + my * my + c1) * (vx + vy + c2))
            scores.append(s)
    scores.sort(reverse=True)
    top = scores[: max(1, int(len(scores) * keep))]
    return round(max(0.0, sum(top) / len(top)), 3)


def _font(size: int):
    from app.livewell.ai_stub_image import _load_font

    return _load_font(size)


def watermark(data: bytes, text: str = WATERMARK_TEXT) -> tuple[bytes, str]:
    """Small "KushAlaya · Illustration" mark in the bottom-right corner (JPEG out)."""
    if not data or not _pil():
        return data, "image/png"
    from PIL import Image, ImageDraw

    try:
        img = Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return data, "image/png"
    w, h = img.size
    size = max(12, min(w, h) // 36)
    font = _font(size)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    box = draw.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    pad = max(4, size // 3)
    margin = max(6, size // 2)
    x1, y1 = w - margin, h - margin
    x0, y0 = x1 - tw - pad * 2, y1 - th - pad * 2
    draw.rounded_rectangle((x0, y0, x1, y1), radius=pad, fill=(15, 40, 48, 150))
    draw.text((x0 + pad - box[0], y0 + pad - box[1]), text, font=font, fill=(255, 255, 255, 235))
    out = io.BytesIO()
    merged = Image.alpha_composite(img, layer).convert("RGB")
    if data[:4] == PNG_MAGIC[:4]:
        merged.save(out, format="PNG", optimize=True)
        return out.getvalue(), "image/png"
    merged.save(out, format="JPEG", quality=90)
    return out.getvalue(), "image/jpeg"


def build_preview_stub(source: bytes, labels: list[str]) -> bytes:
    """Offline stand-in for an AI edit: the same room with numbered product tags.

    Keeps the room pixel-identical outside the tags so the before/after slider and the
    room-unchanged check behave like a good real render.
    """
    from PIL import Image, ImageDraw

    img = Image.open(io.BytesIO(source)).convert("RGB")
    if max(img.size) < 480:
        scale = 480 / max(img.size)
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    w, h = img.size
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    size = max(12, min(w, h) // 30)
    font = _font(size)
    y = max(8, size // 2)
    for i, label in enumerate(labels[:6], start=1):
        text = f"{i}  {label}"[:48]
        box = draw.textbbox((0, 0), text, font=font)
        tw, th = box[2] - box[0], box[3] - box[1]
        draw.rounded_rectangle((8, y, 8 + tw + 16, y + th + 12), radius=6, fill=(13, 110, 110, 190))
        draw.text((16 - box[0], y + 6 - box[1]), text, font=font, fill=(255, 255, 255, 255))
        y += th + 18
    out = io.BytesIO()
    Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB").save(out, format="PNG")
    return out.getvalue()


# --- Products and prices (integer paise, GST 18%) ----------------------------------

ROOM_SEGMENTS = {
    "bathroom": ("BTH",),
    "toilet": ("BTH",),
    "bedroom": ("BED",),
    "kitchen": ("KIT",),
    "living": ("LIV",),
    "living_room": ("LIV",),
    "hallway": ("STA", "HAL"),
    "stairs": ("STA", "HAL"),
    "entry": ("ENT", "EXT"),
    "entrance": ("ENT", "EXT"),
    "balcony": ("ENT", "BAL"),
}


def _room_segments(room_type: str) -> tuple[str, ...]:
    room = (room_type or "").strip().lower().replace(" ", "_")
    if room in ROOM_SEGMENTS:
        return ROOM_SEGMENTS[room]
    for key, seg in ROOM_SEGMENTS.items():
        if key in room:
            return seg
    return ()


def _is_visual_product(code: str) -> bool:
    from app.livewell.commerce import SERVICE_PREFIXES

    prefix = (code or "").split("-")[0].upper()
    return bool(prefix) and prefix not in SERVICE_PREFIXES


def recommended_codes(db: Session, user, payload: dict, room_type: str) -> list[str]:
    """Product codes the assessment recommends for this room.

    Ratings Risk / Needs attention → solution library (rubricItemIds) → solutions for
    this room (LW-HS-<ROOM>-…) → catalog products whose (corrected) solution_ids list them.
    Services are left out: they cannot be drawn into a photo.
    """
    from app.livewell.catalog_service import HomeSafetyCatalogService
    from app.livewell.solution_service import HomeSafetySolutionService

    ratings = (payload or {}).get("ratings") or {}
    flagged = {k for k, v in ratings.items() if str(v).strip().lower() in ("unsafe", "acceptable")}
    if not flagged:
        return []
    segments = _room_segments(room_type)
    lib = HomeSafetySolutionService.get_solutions(db, user) or {}
    if not lib.get("solutions"):  # tenant never saved its own library: use the shipped one
        from app.livewell.solution_service import DEFAULT_SOLUTIONS

        lib = DEFAULT_SOLUTIONS
    solution_ids: set[str] = set()
    for sol in lib.get("solutions") or []:
        sid = str(sol.get("id") or "")
        if not set(sol.get("rubricItemIds") or []) & flagged:
            continue
        parts = sid.split("-")
        if segments and (len(parts) < 3 or parts[2] not in segments):
            continue
        solution_ids.add(sid)
    if not solution_ids:
        return []
    catalog = HomeSafetyCatalogService.get_catalog(db, None)
    out: list[str] = []
    for p in catalog.get("products") or []:
        code = str(p.get("product_code") or "")
        if code and _is_visual_product(code) and set(p.get("solution_ids") or []) & solution_ids:
            out.append(code)
    return list(dict.fromkeys(out))


def priced_items(db: Session, tenant_id: int, codes: list[str]) -> dict:
    """Numbered items with price incl. GST and totals, in the order given. Never cost/margin."""
    from app.livewell.commerce import GST_BP, ensure_default_products, price_paise
    from app.models.commerce import Product

    codes = [c for c in dict.fromkeys(str(c).strip() for c in codes or []) if c]
    if not codes:
        return {"items": [], "subtotal_paise": 0, "gst_paise": 0, "total_paise": 0, "all_priced": True}
    ensure_default_products(db, tenant_id)
    rows = {
        p.product_code: p
        for p in db.query(Product).filter(Product.tenant_id == tenant_id, Product.product_code.in_(codes)).all()
    }
    items = []
    subtotal = 0
    gst_total = 0
    all_priced = True
    for n, code in enumerate(codes, start=1):
        p = rows.get(code)
        price = price_paise(p.cost_paise, p.margin_bp) if (p and p.cost_paise) else 0
        gst = price * GST_BP // 10000
        priced = bool(p and p.cost_paise)
        all_priced = all_priced and priced
        subtotal += price
        gst_total += gst
        items.append(
            {
                "n": n,
                "product_id": p.id if p else None,
                "product_code": code,
                "name": p.name if p else code,
                "price_paise": price,
                "gst_paise": gst,
                "price_with_gst_paise": price + gst,
                "priced": priced,
            }
        )
    return {
        "items": items,
        "subtotal_paise": subtotal,
        "gst_paise": gst_total,
        "total_paise": subtotal + gst_total,
        "all_priced": all_priced,
    }


def catalog_for_picker(db: Session, tenant_id: int) -> list[dict]:
    """Every active product that can be drawn into a room photo, for the add/remove search."""
    from app.livewell.commerce import GST_BP, ensure_default_products, price_paise
    from app.models.commerce import Product

    ensure_default_products(db, tenant_id)
    rows = (
        db.query(Product)
        .filter(Product.tenant_id == tenant_id, Product.active.is_(True))
        .order_by(Product.sort_order, Product.name)
        .all()
    )
    out = []
    for p in rows:
        if not p.product_code or not _is_visual_product(p.product_code):
            continue
        price = price_paise(p.cost_paise, p.margin_bp) if p.cost_paise else 0
        out.append(
            {
                "product_id": p.id,
                "product_code": p.product_code,
                "name": p.name,
                "category": p.category or "",
                "price_with_gst_paise": price + price * GST_BP // 10000,
                "priced": bool(p.cost_paise),
            }
        )
    return out


# --- Caps ---------------------------------------------------------------------------


def _ist_day_start_utc(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    ist = now.astimezone(IST)
    start = ist.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc).replace(tzinfo=None)


def _ist_month_start_utc(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    ist = now.astimezone(IST)
    start = ist.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc).replace(tzinfo=None)


def _int_setting(settings: dict, key: str, default: int) -> int:
    try:
        return int(settings.get(key) if settings.get(key) is not None else default)
    except (TypeError, ValueError):
        return default


def renders_today(db: Session, tenant_id: int) -> int:
    return (
        db.query(HomeSafetyAIJob)
        .filter(
            HomeSafetyAIJob.tenant_id == tenant_id,
            HomeSafetyAIJob.created_at >= _ist_day_start_utc(),
            HomeSafetyAIJob.provider != "manual_upload",
        )
        .count()
    )


def check_render_caps(
    db: Session,
    tenant_id: int,
    settings: dict,
    *,
    assessment_id: str,
    source_document_id: int,
    tiers: list[str],
) -> dict[str, str | None]:
    """Raise when a new render would pass a cap; return {tier: public_id it re-runs or None}.

    Caps, on every path that calls the provider (generate, single create, regenerate):
    - at most `max_images_per_assessment` photos × 3 tiers per assessment,
    - at most `max_regenerations_per_tier` re-runs of one photo + tier,
    - at most `daily_render_cap` renders per tenant per IST day.
    """
    max_photos = _int_setting(settings, "max_images_per_assessment", 3)
    max_regen = _int_setting(settings, "max_regenerations_per_tier", 2)
    daily_cap = _int_setting(settings, "daily_render_cap", 30)
    aid = assessment_id.strip()
    levels = [t.strip().lower() for t in tiers if t and t.strip()]

    active = (
        db.query(HomeSafetyAIJob)
        .filter(
            HomeSafetyAIJob.tenant_id == tenant_id,
            HomeSafetyAIJob.assessment_id == aid,
            HomeSafetyAIJob.status != "cancelled",
        )
        .all()
    )
    photos = {j.source_document_id for j in active}
    if source_document_id not in photos and len(photos) >= max_photos:
        raise HTTPException(
            status_code=400,
            detail=f"This assessment already has AI previews for {max_photos} photos (the limit).",
        )
    pairs = {(j.source_document_id, (j.package_level or "").lower()): j for j in active}
    new_pairs = {(source_document_id, t) for t in levels} - set(pairs)
    if len(pairs) + len(new_pairs) > max_photos * 3:
        raise HTTPException(
            status_code=400,
            detail=f"Assessment exceeds max AI jobs limit ({max_photos} photos × 3 packages).",
        )

    out: dict[str, str | None] = {}
    for tier in levels:
        prior = pairs.get((source_document_id, tier))
        if prior is None:
            out[tier] = None
            continue
        used = (
            db.query(HomeSafetyAIJob)
            .filter(
                HomeSafetyAIJob.tenant_id == tenant_id,
                HomeSafetyAIJob.assessment_id == aid,
                HomeSafetyAIJob.source_document_id == source_document_id,
                HomeSafetyAIJob.package_level == tier,
                HomeSafetyAIJob.regenerated_from.isnot(None),
            )
            .count()
        )
        if used >= max_regen:
            raise HTTPException(
                status_code=400,
                detail=f"No regenerations left for the {tier.title()} package of this photo ({max_regen} used).",
            )
        out[tier] = prior.public_id

    if renders_today(db, tenant_id) + len(levels) > daily_cap:
        raise HTTPException(
            status_code=429,
            detail=f"Daily AI preview limit reached ({daily_cap} images). Try again tomorrow or raise it in AI settings.",
        )
    return out


def regenerations_left(db: Session, job: HomeSafetyAIJob, settings: dict) -> int:
    max_regen = _int_setting(settings, "max_regenerations_per_tier", 2)
    used = (
        db.query(HomeSafetyAIJob)
        .filter(
            HomeSafetyAIJob.tenant_id == job.tenant_id,
            HomeSafetyAIJob.assessment_id == job.assessment_id,
            HomeSafetyAIJob.source_document_id == job.source_document_id,
            HomeSafetyAIJob.package_level == job.package_level,
            HomeSafetyAIJob.regenerated_from.isnot(None),
        )
        .count()
    )
    return max(0, max_regen - used)


# --- Usage ---------------------------------------------------------------------------


def _attempts(job: HomeSafetyAIJob) -> int:
    n = sum(
        1
        for e in job.event_log or []
        if isinstance(e, dict) and e.get("event") == "provider_request_sent"
    )
    return max(n, int(job.render_attempts or 0))


FEATURE_LABELS = {"room_preview": "Room previews", "hazard_check": "Hazard checks"}
FREE_PROVIDERS = {"local_stub", "stub", "none", "", None}


def _cost_per_call(provider: str | None, settings: dict) -> int:
    """Estimated paise per provider call (settings override; stub/none cost nothing)."""
    if provider in FREE_PROVIDERS:
        return 0
    if (provider or "").startswith("fal"):
        return _int_setting(settings, "estimated_cost_paise_per_image", 350)
    return _int_setting(settings, "estimated_cost_paise_per_vision_call", 10)


def usage_summary(db: Session, tenant_id: int, settings: dict) -> dict:
    """Owner card: this IST month's AI calls and estimated cost, per feature, from the
    shared ai_usage_events table (room preview renders + QA, hazard checks)."""
    from app.models.ai_usage import AiUsageEvent

    rows = (
        db.query(AiUsageEvent.feature, AiUsageEvent.provider, AiUsageEvent.cache_hit, AiUsageEvent.status)
        .filter(AiUsageEvent.tenant_id == tenant_id, AiUsageEvent.created_at >= _ist_month_start_utc())
        .all()
    )
    features: dict[str, dict] = {}
    for feature, provider, cache_hit, status in rows:
        f = features.setdefault(
            feature,
            {"feature": feature, "label": FEATURE_LABELS.get(feature, feature.replace("_", " ").title()),
             "calls": 0, "cache_hits": 0, "failed": 0, "estimated_cost_paise": 0},
        )
        if cache_hit:
            f["cache_hits"] += 1
            continue
        f["calls"] += 1
        if status != "ok":
            f["failed"] += 1
        f["estimated_cost_paise"] += _cost_per_call(provider, settings)
    for key in FEATURE_LABELS:
        features.setdefault(key, {"feature": key, "label": FEATURE_LABELS[key], "calls": 0,
                                  "cache_hits": 0, "failed": 0, "estimated_cost_paise": 0})
    items = sorted(features.values(), key=lambda f: f["feature"] != "room_preview")
    return {
        "features": items,
        "total_calls": sum(f["calls"] for f in items),
        "estimated_cost_paise": sum(f["estimated_cost_paise"] for f in items),
        "previews_today": renders_today(db, tenant_id),
        "daily_cap": _int_setting(settings, "daily_render_cap", 30),
    }


# --- Team scope ----------------------------------------------------------------------


def job_elder_id(db: Session, job: HomeSafetyAIJob) -> int | None:
    if job.elder_id:
        return job.elder_id
    if job.prospect_id:
        from app.models.elder_prospect import ElderProspect

        p = db.query(ElderProspect).filter(ElderProspect.id == job.prospect_id).first()
        return p.converted_elder_id if p else None
    return None


def assert_job_in_team(db: Session, user, job: HomeSafetyAIJob) -> None:
    from app.core.team_scope import is_scoped_manager, team_elder_ids

    if not is_scoped_manager(user):
        return
    elder_id = job_elder_id(db, job)
    if elder_id is None:
        return  # prospect not yet a client: no team yet
    ids = team_elder_ids(db, user) or set()
    if elder_id not in ids:
        raise HTTPException(status_code=404, detail="AI job not found")


def client_first_name(db: Session, job: HomeSafetyAIJob) -> str:
    from app.models.elder import Elder

    elder_id = job_elder_id(db, job)
    if elder_id:
        e = db.query(Elder).filter(Elder.id == elder_id).first()
        if e and e.first_name:
            return e.first_name.strip()
    if job.prospect_id:
        from app.models.elder_prospect import ElderProspect

        p = db.query(ElderProspect).filter(ElderProspect.id == job.prospect_id).first()
        name = (getattr(p, "first_name", None) or getattr(p, "name", None) or "").strip() if p else ""
        if name:
            return name.split()[0]
    return ""


# --- PDF -------------------------------------------------------------------------------


def _rupees(paise: int) -> str:
    rupees, p = divmod(int(paise), 100)
    s = f"{rupees:,}"
    return f"Rs {s}" + (f".{p:02d}" if p else "")


def build_preview_pdf(
    *,
    title: str,
    first_name: str,
    room_label: str,
    before: bytes,
    after: bytes,
    pricing: dict,
    disclaimer: str,
) -> bytes:
    """One A4 page: before and after side by side, numbered items with price incl. GST, total."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    pw, ph = A4
    m = 36
    c.setFillColorRGB(0.05, 0.43, 0.43)
    c.rect(0, ph - 64, pw, 64, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(m, ph - 38, title)
    c.setFont("Helvetica", 10)
    c.drawString(m, ph - 54, f"{room_label}" + (f" · for {first_name}" if first_name else ""))

    col_w = (pw - 2 * m - 12) / 2
    top = ph - 84
    img_h = 0.0
    for i, (label, data) in enumerate((("Before", before), ("After (illustration)", after))):
        x = m + i * (col_w + 12)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x, top - 12, label)
        try:
            reader = ImageReader(io.BytesIO(data))
            iw, ih = reader.getSize()
            h = col_w * ih / iw if iw else col_w
            h = min(h, 300)
            w = h * iw / ih if ih else col_w
            c.drawImage(reader, x, top - 20 - h, width=w, height=h)
            img_h = max(img_h, h)
        except Exception:
            c.drawString(x, top - 40, "Image unavailable")
            img_h = max(img_h, 40)

    y = top - 20 - img_h - 28
    c.setFont("Helvetica-Bold", 12)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.drawString(m, y, "Suggested safety items")
    y -= 18
    c.setFont("Helvetica", 10)
    for item in pricing.get("items") or []:
        price = _rupees(item["price_with_gst_paise"]) if item.get("priced") else "Price on request"
        c.drawString(m, y, f"{item['n']}.  {item['name'][:70]}")
        c.drawRightString(pw - m, y, price)
        y -= 15
        if y < 90:
            break
    c.line(m, y + 6, pw - m, y + 6)
    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawString(m, y, "Total (incl. 18% GST)")
    c.drawRightString(pw - m, y, _rupees(pricing.get("total_paise") or 0))
    y -= 14
    c.setFont("Helvetica", 9)
    c.drawString(
        m,
        y,
        f"Before GST {_rupees(pricing.get('subtotal_paise') or 0)} · GST {_rupees(pricing.get('gst_paise') or 0)}",
    )
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    text = c.beginText(m, 48)
    words = (disclaimer or "").split()
    line = ""
    for w in words:
        trial = f"{line} {w}".strip()
        if c.stringWidth(trial, "Helvetica-Oblique", 8) > pw - 2 * m:
            text.textLine(line)
            line = w
        else:
            line = trial
    if line:
        text.textLine(line)
    c.drawText(text)
    c.showPage()
    c.save()
    return buf.getvalue()


def job_progress(job: HomeSafetyAIJob) -> dict:
    stage = job.progress_stage or ("done" if job.status in ("needs_review", "completed") else (
        "failed" if job.status == "failed" else "queued"
    ))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    started = job.started_at
    finished = job.finished_at
    elapsed = None
    if started:
        elapsed = int(((finished or now) - started).total_seconds())
    return {
        "stage": stage,
        "label": STAGE_LABELS.get(stage, stage),
        "percent": STAGE_PCT.get(stage, 0),
        "started_at": started.isoformat() if started else None,
        "finished_at": finished.isoformat() if finished else None,
        "elapsed_seconds": elapsed,
        "estimate_seconds": ESTIMATE_SECONDS.get(job.provider or "", 15),
        "running": stage in ("queued", "preparing", "generating", "checking", "retrying", "saving")
        and job.status in ("queued", "running"),
    }
