"""Blog posts: validation, Markdown cleaning, visibility and the public views.

Admins write posts in Settings-free ops (/kushalaya/blog); the public site
(www /blog) reads published posts of the site tenant — the same tenant
Settings → Website and website enquiries use (the first tenant).

Body is Markdown. Raw HTML is stripped on save and links with script-capable
schemes are neutralised; the site renders Markdown to React elements, never to
injected HTML, so a stored post cannot run script either way.
"""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session

from app.core.responses import raise_bad_request, raise_not_found
from app.models.blog import BLOG_STATUSES, BlogImage, BlogPost
from app.models.tenant import Tenant
from app.models.user import User

EXCERPT_MAX = 160
SEO_TITLE_MAX = 70
TITLE_MAX = 200
SLUG_MAX = 100
TAG_MAX = 10
WORDS_PER_MINUTE = 200
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _aware(d: datetime | None) -> datetime | None:
    if d is None:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _iso(d: datetime | None) -> str | None:
    d = _aware(d)
    return d.isoformat() if d else None


# --- Text helpers ---------------------------------------------------------------


def slugify(text: str) -> str:
    """"Caring for Parents — Hyderabad!" -> "caring-for-parents-hyderabad"."""
    norm = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", norm.lower()).strip("-")
    slug = slug[:SLUG_MAX].strip("-")
    return slug or "post"


_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_AUTOLINK = re.compile(r"<((?:https?://|mailto:)[^>\s]+)>", re.I)
_HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
_BAD_LINK = re.compile(r"(\]\(\s*<?)\s*(?:javascript|vbscript|data|file)\s*:[^)\s]*", re.I)
_BAD_REF = re.compile(r"^(\s*\[[^\]]+\]:\s*)(?:javascript|vbscript|data|file)\s*:\S*", re.I | re.M)


def clean_markdown(md: str) -> str:
    """Strip raw HTML and script-capable link targets from Markdown."""
    text = (md or "").replace("\r\n", "\n")
    text = _HTML_COMMENT.sub("", text)
    text = _AUTOLINK.sub(r"\1", text)
    # Repeat: "<scr<script>ipt>" leaves a tag behind after one pass.
    for _ in range(3):
        stripped = _HTML_TAG.sub("", text)
        if stripped == text:
            break
        text = stripped
    text = _BAD_LINK.sub(r"\1#", text)
    text = _BAD_REF.sub(r"\1#", text)
    return text.strip()


def plain_words(md: str) -> list[str]:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md or "")  # images
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links keep their text
    text = re.sub(r"[#>*_`~\-|]+", " ", text)
    return [w for w in text.split() if any(ch.isalnum() for ch in w)]


def reading_minutes(md: str) -> int:
    return max(1, math.ceil(len(plain_words(md)) / WORDS_PER_MINUTE))


def _clean_tags(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = raw.split(",")
    out: list[str] = []
    for t in raw:
        tag = re.sub(r"\s+", " ", str(t or "")).strip().lower()[:40]
        if tag and tag not in out:
            out.append(tag)
    return out[:TAG_MAX]


def _url_ok(url: str, allow_relative: bool = True) -> bool:
    if not url:
        return True
    if allow_relative and url.startswith("/") and not url.startswith("//"):
        return True
    return bool(re.match(r"^https?://[^\s]+$", url, re.I))


def _parse_dt(value) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return _aware(value)
    try:
        return _aware(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError:
        raise_bad_request("Use a valid date and time for scheduling")


def _clean_faq(raw) -> list[dict]:
    out = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        q = str(item.get("q") or "").strip()[:300]
        a = clean_markdown(str(item.get("a") or ""))[:2000]
        if q and a:
            out.append({"q": q, "a": a})
    return out[:20]


# --- Tenancy ----------------------------------------------------------------------


def site_tenant(db: Session) -> Tenant | None:
    """The tenant the public website belongs to (same rule as /enquiries/site)."""
    return db.query(Tenant).order_by(Tenant.id).first()


def admin_tenant_id(db: Session, user: User) -> int:
    if user.tenant_id:
        return user.tenant_id
    site = site_tenant(db)
    if site is None:
        raise_not_found("Agency not found")
    return site.id


# --- Visibility -------------------------------------------------------------------


def visible_filter(now: datetime | None = None):
    now = now or now_utc()
    return or_(
        and_(BlogPost.status == "published", or_(BlogPost.published_at.is_(None), BlogPost.published_at <= now)),
        and_(BlogPost.status == "scheduled", BlogPost.publish_at.isnot(None), BlogPost.publish_at <= now),
    )


def is_live(p: BlogPost, now: datetime | None = None) -> bool:
    now = now or now_utc()
    if p.status == "published":
        return p.published_at is None or _aware(p.published_at) <= now
    if p.status == "scheduled":
        return p.publish_at is not None and _aware(p.publish_at) <= now
    return False


def effective_date(p: BlogPost) -> datetime | None:
    if p.status == "scheduled":
        return _aware(p.publish_at)
    return _aware(p.published_at)


# --- Rows ---------------------------------------------------------------------------


def card_row(p: BlogPost) -> dict:
    return {
        "id": p.id,
        "slug": p.slug,
        "title": p.title,
        "excerpt": p.excerpt,
        "cover_image_url": p.cover_image_url,
        "cover_image_alt": p.cover_image_alt,
        "tags": list(p.tags or []),
        "author_name": p.author_name,
        "published_at": _iso(effective_date(p)),
        "updated_at": _iso(p.updated_at),
        "reading_minutes": p.reading_minutes,
    }


def public_row(p: BlogPost) -> dict:
    return {
        **card_row(p),
        "body_md": p.body_md,
        "seo_title": p.seo_title,
        "og_image_url": p.og_image_url,
        "canonical_url": p.canonical_url,
        "faq": list(p.faq or []),
    }


def admin_row(p: BlogPost) -> dict:
    return {
        **public_row(p),
        "status": p.status,
        "publish_at": _iso(p.publish_at),
        "created_at": _iso(p.created_at),
        "live": is_live(p),
    }


# --- Admin CRUD ----------------------------------------------------------------------


def _get(db: Session, tenant_id: int, post_id: int) -> BlogPost:
    p = db.get(BlogPost, post_id)
    if not p or p.tenant_id != tenant_id:
        raise_not_found("Post not found")
    return p


def _slug_taken(db: Session, tenant_id: int, slug: str, exclude_id: int | None = None) -> bool:
    q = db.query(BlogPost.id).filter(BlogPost.tenant_id == tenant_id, BlogPost.slug == slug)
    if exclude_id:
        q = q.filter(BlogPost.id != exclude_id)
    return db.query(q.exists()).scalar()


def unique_slug(db: Session, tenant_id: int, base: str, exclude_id: int | None = None) -> str:
    base = slugify(base)
    slug, n = base, 2
    while _slug_taken(db, tenant_id, slug, exclude_id):
        suffix = f"-{n}"
        slug = f"{base[: SLUG_MAX - len(suffix)]}{suffix}"
        n += 1
    return slug


def _apply(db: Session, p: BlogPost, body: dict, *, creating: bool) -> None:
    if "title" in body or creating:
        title = re.sub(r"\s+", " ", str(body.get("title") or "")).strip()
        if not title:
            raise_bad_request("Give the post a title")
        if len(title) > TITLE_MAX:
            raise_bad_request(f"Keep the title under {TITLE_MAX} characters")
        p.title = title

    if "slug" in body and str(body.get("slug") or "").strip():
        slug = slugify(str(body["slug"]))
        if _slug_taken(db, p.tenant_id, slug, p.id):
            raise HTTPException(status_code=409, detail=f"Another post already uses the address /blog/{slug}")
        p.slug = slug
    elif creating:
        p.slug = unique_slug(db, p.tenant_id, p.title)

    if "excerpt" in body:
        excerpt = re.sub(r"\s+", " ", str(body.get("excerpt") or "")).strip()
        if len(excerpt) > EXCERPT_MAX:
            raise_bad_request(f"Keep the summary to {EXCERPT_MAX} characters (it is {len(excerpt)})")
        p.excerpt = excerpt
    if "body_md" in body:
        p.body_md = clean_markdown(str(body.get("body_md") or ""))
        p.reading_minutes = reading_minutes(p.body_md)
    if "seo_title" in body:
        seo = re.sub(r"\s+", " ", str(body.get("seo_title") or "")).strip()
        if len(seo) > SEO_TITLE_MAX:
            raise_bad_request(f"Keep the search title to {SEO_TITLE_MAX} characters")
        p.seo_title = seo
    for key, relative in (("cover_image_url", True), ("og_image_url", True), ("canonical_url", False)):
        if key in body:
            url = str(body.get(key) or "").strip()
            if not _url_ok(url, allow_relative=relative):
                raise_bad_request("Use a full https:// address" if not relative else "Use an uploaded image or an https:// address")
            setattr(p, key, url[:500])
    if "cover_image_alt" in body:
        p.cover_image_alt = str(body.get("cover_image_alt") or "").strip()[:200]
    if "tags" in body:
        p.tags = _clean_tags(body.get("tags"))
    if "author_name" in body:
        p.author_name = str(body.get("author_name") or "").strip()[:120]
    if "faq" in body:
        p.faq = _clean_faq(body.get("faq"))

    if "publish_at" in body:
        p.publish_at = _parse_dt(body.get("publish_at"))
    if "status" in body:
        status = str(body.get("status") or "").strip().lower()
        if status not in BLOG_STATUSES:
            raise_bad_request("Status must be draft, published or scheduled")
        if status == "scheduled":
            if not p.publish_at:
                raise_bad_request("Pick a date and time to publish")
            p.published_at = None
        elif status == "published":
            # First publish stamps the date; re-publishing keeps the original one.
            if not p.published_at:
                p.published_at = now_utc()
            p.publish_at = None
        p.status = status

    if p.status in ("published", "scheduled"):
        _check_publishable(p)


def _check_publishable(p: BlogPost) -> None:
    if p.cover_image_url and not p.cover_image_alt:
        raise_bad_request("Describe the cover image (alt text) before publishing")
    if re.search(r"!\[\s*\]\(", p.body_md or ""):
        raise_bad_request("Every image in the article needs a short description (alt text) before publishing")
    if not (p.body_md or "").strip():
        raise_bad_request("Write the article before publishing")


def list_admin(db: Session, user: User) -> list[dict]:
    tid = admin_tenant_id(db, user)
    rows = (
        db.query(BlogPost)
        .filter(BlogPost.tenant_id == tid)
        .order_by(BlogPost.updated_at.desc(), BlogPost.id.desc())
        .all()
    )
    return [admin_row(p) for p in rows]


def get_admin(db: Session, user: User, post_id: int) -> dict:
    return admin_row(_get(db, admin_tenant_id(db, user), post_id))


def create_post(db: Session, user: User, body: dict) -> dict:
    p = BlogPost(
        tenant_id=admin_tenant_id(db, user),
        status="draft",
        tags=[],
        faq=[],
        created_by=user.id,
        author_name=(f"{user.first_name or ''} {user.last_name or ''}".strip()),
    )
    _apply(db, p, body, creating=True)
    db.add(p)
    db.commit()
    db.refresh(p)
    return admin_row(p)


def update_post(db: Session, user: User, post_id: int, body: dict) -> dict:
    p = _get(db, admin_tenant_id(db, user), post_id)
    _apply(db, p, body, creating=False)
    p.updated_at = now_utc()
    db.commit()
    db.refresh(p)
    return admin_row(p)


def delete_post(db: Session, user: User, post_id: int) -> None:
    p = _get(db, admin_tenant_id(db, user), post_id)
    db.delete(p)
    db.commit()


# --- Images ---------------------------------------------------------------------------


def image_url(image_id: int) -> str:
    return f"/api/v1/public/blog/images/{image_id}"


def save_image(db: Session, user: User, content: bytes, mime: str, name: str, alt: str) -> dict:
    if mime not in IMAGE_TYPES:
        raise_bad_request("Use a JPG, PNG or WebP picture")
    if not content:
        raise_bad_request("The file is empty")
    if len(content) > MAX_IMAGE_BYTES:
        raise_bad_request("Pictures must be 5 MB or smaller")
    from app.core.storage import get_storage

    tid = admin_tenant_id(db, user)
    img = BlogImage(tenant_id=tid, storage_key="", mime=mime, alt=(alt or "").strip()[:200])
    db.add(img)
    db.flush()
    key, _url = get_storage().save(tid, "blog", img.id, name or "image", content, mime)
    img.storage_key = key
    db.commit()
    return {"id": img.id, "url": image_url(img.id), "alt": img.alt}


def image_bytes(db: Session, image_id: int) -> tuple[bytes, str]:
    img = db.get(BlogImage, image_id)
    if not img or not img.storage_key:
        raise_not_found("No picture")
    from app.core.storage import get_storage

    content, mime = get_storage().read(img.storage_key)
    return content, (img.mime or mime)


# --- Public ------------------------------------------------------------------------------


def _public_q(db: Session):
    site = site_tenant(db)
    tid = site.id if site is not None else -1
    return db.query(BlogPost).filter(BlogPost.tenant_id == tid, visible_filter())


def _newest_first(q):
    return q.order_by(func.coalesce(BlogPost.published_at, BlogPost.publish_at).desc(), BlogPost.id.desc())


def public_list(db: Session, *, page: int = 1, per_page: int = 9, tag: str | None = None) -> dict:
    rows = _newest_first(_public_q(db)).all()
    all_tags: list[str] = []
    for p in rows:
        for t in p.tags or []:
            if t not in all_tags:
                all_tags.append(t)
    if tag:
        tag = tag.strip().lower()
        rows = [p for p in rows if tag in (p.tags or [])]
    total = len(rows)
    pages = max(1, math.ceil(total / per_page))
    start = (page - 1) * per_page
    return {
        "items": [card_row(p) for p in rows[start : start + per_page]],
        "total": total,
        "page": page,
        "pages": pages,
        "per_page": per_page,
        "tag": tag or None,
        "tags": sorted(all_tags),
    }


def public_post(db: Session, slug: str) -> dict:
    p = _public_q(db).filter(BlogPost.slug == slugify(slug)).first()
    if p is None:
        raise_not_found("Post not found")
    others = _newest_first(_public_q(db).filter(BlogPost.id != p.id)).limit(30).all()
    tags = set(p.tags or [])
    others.sort(key=lambda o: -len(tags & set(o.tags or [])))  # stable: newest first within a score
    return {**public_row(p), "related": [card_row(o) for o in others[:3]]}


def public_sitemap(db: Session) -> list[dict]:
    rows = _newest_first(_public_q(db)).all()
    return [
        {"slug": p.slug, "updated_at": _iso(p.updated_at or effective_date(p)), "published_at": _iso(effective_date(p))}
        for p in rows
    ]
