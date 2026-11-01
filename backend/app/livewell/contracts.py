"""Contracts signed inside the app — vendor agreements and client service contracts.

Flow (owner, 30–31 Oct 2026):

1. An admin keeps editable, versioned templates (``ContractTemplate``) with
   ``{placeholders}``. Editing makes a new version; signed contracts keep their text.
2. Staff pick a template for a vendor or a client; the text is filled in and stored on
   a ``Contract``. A care manager can prepare it ("Waiting for KushAlaya signature");
   only a TENANT_ADMIN — the authorised signatory — can "Sign & send". Their saved
   signature (``ContractSignatory``) is applied with name, designation, time, IP, user
   agent and the SHA-256 of the exact text. From then on the text is locked.
3. Only after the company has signed is a no-login link created
   (``/sign/<id>-<nonce>-<hmac>``, 30 days). The vendor / client sees KushAlaya's
   signature block, types their name, draws or types a signature, ticks "I agree".
4. The server checks the text still hashes to what the company signed, records the
   second signature once, builds a PDF with both signature blocks and an audit page,
   stores it as a Document and emails the signer, the company signatory and staff.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import logging
import re
import secrets
import uuid
import zipfile
from datetime import date, datetime, timedelta, timezone
from html import escape
from xml.etree import ElementTree

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rbac import TENANT_ADMIN, assert_tenant_access, resolve_tenant_id
from app.core.team_scope import assert_elder_in_team, team_elder_ids
from app.models.contract import CONTRACT_KINDS, Contract, ContractSignatory, ContractTemplate
from app.models.document import Document
from app.models.elder import Elder
from app.models.tenant import Tenant
from app.models.user import User
from app.models.vendor import FEE_BASES, VENDOR_SERVICES, Vendor

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
LINK_DAYS = 30
#: After signing, the same link shows the signed copy for this long.
SIGNED_LINK_DAYS = 30
MAX_SIGNATURE_BYTES = 400_000
MAX_DOCX_BYTES = 5_000_000
BLANK = "__________"
KIND_LABEL = dict(CONTRACT_KINDS)
PARTY_LABEL = {"vendor": "Vendor", "client": "Client"}
DOCUMENT_TYPE = "SIGNED_CONTRACT"

#: (key, what it is, which kinds use it). The editor shows this as the cheat-sheet.
PLACEHOLDERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("company_name", "KushAlaya's legal name (Settings → Business details)", ("vendor", "client")),
    ("company_address", "KushAlaya's registered address", ("vendor", "client")),
    ("company_gstin", "KushAlaya's GSTIN", ("vendor", "client")),
    ("date", "Today's date", ("vendor", "client")),
    ("start_date", "Start date (plan start, or today)", ("vendor", "client")),
    ("end_date", "End date (plan end)", ("vendor", "client")),
    ("signer_name", "The person who signs", ("vendor", "client")),
    ("client_name", "Client's full name", ("client",)),
    ("client_address", "Client's address", ("client",)),
    ("client_phone", "Client's phone", ("client",)),
    ("plan_name", "Client's current plan", ("client",)),
    ("plan_amount", "Plan amount incl. GST", ("client",)),
    ("vendor_name", "Vendor owner / contact name", ("vendor",)),
    ("vendor_company", "Vendor company name", ("vendor",)),
    ("vendor_address", "Vendor address", ("vendor",)),
    ("vendor_gstin", "Vendor GSTIN", ("vendor",)),
    ("vendor_phone", "Vendor phone", ("vendor",)),
    ("vendor_services", "Services the vendor provides", ("vendor",)),
    ("vendor_fee", "Vendor fee and basis", ("vendor",)),
)
PLACEHOLDER_KEYS = {k for k, _, _ in PLACEHOLDERS}
_PH = re.compile(r"\{([a-z_]+)\}")

DEFAULT_TEMPLATES: dict[str, tuple[str, str]] = {
    "vendor": (
        "Vendor agreement",
        """[PLACEHOLDER — Replace with KushAlaya's own wording before sending to a real vendor.]

# Parties
This agreement is made on {date} between {company_name}, {company_address} ("KushAlaya") and {vendor_company}, represented by {vendor_name}, {vendor_address} ("the Vendor").

# Services
The Vendor will provide: {vendor_services}. Work is booked by KushAlaya for its clients, who are older adults living at home.

# Fees
{vendor_fee}. KushAlaya pays against the Vendor's invoice within 15 days. GSTIN of the Vendor: {vendor_gstin}.

# Conduct and safety
The Vendor's staff will be courteous, carry identification, follow the client's home rules and report any safety concern to KushAlaya at once.

# Confidentiality
The Vendor keeps all client information private and uses it only to do the work.

# Term
From {start_date} until either side ends it with 30 days' written notice.""",
    ),
    "client": (
        "Client service contract",
        """[PLACEHOLDER — Replace with KushAlaya's own wording before sending to a real client.]

# Parties
This contract is made on {date} between {company_name}, {company_address} ("KushAlaya") and {signer_name}, on behalf of {client_name}, {client_address} ("the Client").

# Services
KushAlaya provides the {plan_name} plan as described on its website and in the care plan agreed with the Client.

# Fees
{plan_amount} including GST, for the period {start_date} to {end_date}, paid in advance.

# Care and safety
KushAlaya's care team visits as scheduled and tells the family about any concern. In an emergency KushAlaya calls the family and emergency services.

# Privacy
KushAlaya keeps the Client's personal and health information private and uses it only to provide care.

# Ending the contract
Either side may end this contract with 15 days' written notice.""",
    ),
}


# --- small helpers -----------------------------------------------------------------


def _now() -> datetime:
    """Naive UTC, like the other timestamps in this app."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(dt: datetime | None) -> str | None:
    return dt.replace(tzinfo=timezone.utc).isoformat() if dt else None


def _ist(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.replace(tzinfo=timezone.utc).astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")


def _utc(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC") if dt else ""


def _bad(detail: str, code: int = 422):
    raise HTTPException(status_code=code, detail=detail)


def _name(u: User | None) -> str:
    if not u:
        return ""
    return f"{u.first_name or ''} {u.last_name or ''}".strip() or (u.email or "")


def _rupees(paise: int | None) -> str:
    if paise is None:
        return ""
    whole, frac = divmod(int(paise), 100)
    s = str(whole)
    if len(s) > 3:  # Indian grouping: 12,34,567
        head, tail = s[:-3], s[-3:]
        head = ",".join(re.findall(r"\d{1,2}", head[::-1]))[::-1] if head else ""
        s = f"{head},{tail}"
    return f"₹{s}" + (f".{frac:02d}" if frac else "")


def _history(c: Contract, event: str, by: str = "") -> None:
    c.history = [*(c.history or []), {"at": _iso(_now()), "event": event, "by": by}]


def is_signatory(user: User) -> bool:
    return user.role == TENANT_ADMIN and user.tenant_id is not None


def canonical_text(title: str, body: str) -> str:
    """The exact text both parties sign: title, blank line, body (LF line endings)."""
    return f"{(title or '').strip()}\n\n{(body or '').replace(chr(13) + chr(10), chr(10)).strip()}"


def text_sha256(title: str, body: str) -> str:
    return hashlib.sha256(canonical_text(title, body).encode("utf-8")).hexdigest()


def render(text: str, values: dict[str, str]) -> str:
    """Fill ``{key}`` placeholders; unknown ``{words}`` are left as they are."""

    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key not in PLACEHOLDER_KEYS:
            return m.group(0)
        v = (values.get(key) or "").strip()
        return v or BLANK

    return _PH.sub(sub, text or "")


# --- signing link ------------------------------------------------------------------


def _sig(contract_id: int, nonce: str) -> str:
    msg = f"contract:{contract_id}:{nonce}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:32]


def make_token(c: Contract) -> str | None:
    if not c.token_nonce:
        return None
    return f"{c.id}-{c.token_nonce}-{_sig(c.id, c.token_nonce)}"


def sign_path(c: Contract) -> str | None:
    t = make_token(c)
    return f"/sign/{t}" if t else None


def contract_for_token(db: Session, token: str) -> Contract:
    """The contract a link points at, or 404. Expiry is checked by the caller."""
    parts = (token or "")[:120].split("-")
    if len(parts) != 3 or not parts[0].isdigit():
        _bad("This link is not valid.", 404)
    cid, nonce, sig = int(parts[0]), parts[1], parts[2]
    c = db.get(Contract, cid)
    if (
        c is None
        or not c.token_nonce
        or not hmac.compare_digest(nonce, c.token_nonce)
        or not hmac.compare_digest(sig, _sig(cid, nonce))
    ):
        _bad("This link is not valid.", 404)
    return c


def effective_status(c: Contract, now: datetime | None = None) -> str:
    now = now or _now()
    if c.status in ("sent", "viewed") and c.expires_at and c.expires_at < now:
        return "expired"
    return c.status


def _new_link(c: Contract) -> None:
    c.token_nonce = secrets.token_hex(12)
    c.expires_at = _now() + timedelta(days=LINK_DAYS)


# --- signatures ----------------------------------------------------------------------


def clean_signature(png: str | None, typed: str | None) -> tuple[str, str | None, str | None]:
    """(kind, png_data_url, text). A drawn PNG wins; otherwise a typed signature."""
    png = (png or "").strip()
    if png:
        prefix = "data:image/png;base64,"
        if not png.startswith(prefix):
            _bad("The signature must be a PNG image.")
        try:
            raw = base64.b64decode(png[len(prefix):], validate=True)
        except Exception:
            _bad("The signature image could not be read.")
        if len(raw) > MAX_SIGNATURE_BYTES:
            _bad("The signature image is too large.")
        if not raw.startswith(b"\x89PNG\r\n\x1a\n") or len(raw) < 50:
            _bad("The signature image could not be read.")
        return "drawn", png, None
    text = " ".join((typed or "").split())
    if len(text) < 2:
        _bad("Draw your signature or type it.")
    return "typed", None, text[:100]


def _png_bytes(data_url: str | None) -> bytes | None:
    if not data_url or "," not in data_url:
        return None
    try:
        return base64.b64decode(data_url.split(",", 1)[1])
    except Exception:
        return None


def signatory_out(s: ContractSignatory | None) -> dict | None:
    if not s:
        return None
    return {
        "name": s.name,
        "designation": s.designation,
        "signature_kind": s.signature_kind,
        "signature_png": s.signature_png,
        "signature_text": s.signature_text,
        "updated_at": _iso(s.updated_at),
    }


def get_signatory(db: Session, user: User) -> ContractSignatory | None:
    return db.query(ContractSignatory).filter(ContractSignatory.user_id == user.id).first()


def save_signatory(db: Session, user: User, data: dict) -> dict:
    if not is_signatory(user):
        _bad("Only an admin (authorised signatory) can save a company signature.", 403)
    name = " ".join((data.get("name") or "").split())[:200] or _name(user)
    designation = " ".join((data.get("designation") or "").split())[:120]
    if not designation:
        _bad("Add your designation, e.g. Director.")
    kind, png, text = clean_signature(data.get("signature_png"), data.get("signature_text"))
    row = get_signatory(db, user)
    if row is None:
        row = ContractSignatory(tenant_id=user.tenant_id, user_id=user.id)
        db.add(row)
    row.name, row.designation = name, designation
    row.signature_kind, row.signature_png, row.signature_text = kind, png, text
    db.commit()
    db.refresh(row)
    return signatory_out(row)


# --- templates -----------------------------------------------------------------------


def _tenant_id(user: User) -> int:
    tid = resolve_tenant_id(user)
    if tid is None:
        _bad("Sign in as a staff member of a tenant.", 400)
    return tid


def ensure_default_templates(db: Session, tenant_id: int) -> None:
    have = {k for (k,) in db.query(ContractTemplate.kind).filter(ContractTemplate.tenant_id == tenant_id).distinct()}
    added = False
    for kind, (title, body) in DEFAULT_TEMPLATES.items():
        if kind not in have:
            db.add(ContractTemplate(tenant_id=tenant_id, kind=kind, group_key=uuid.uuid4().hex, version=1,
                                    is_current=True, title=title, body=body))
            added = True
    if added:
        db.commit()


def template_out(t: ContractTemplate, created_by: str = "") -> dict:
    return {
        "id": t.id,
        "kind": t.kind,
        "kind_label": KIND_LABEL.get(t.kind, t.kind),
        "group_key": t.group_key,
        "version": t.version,
        "is_current": t.is_current,
        "archived": t.archived,
        "title": t.title,
        "body": t.body,
        "is_placeholder": "[PLACEHOLDER" in (t.body or ""),
        "created_at": _iso(t.created_at),
        "created_by": created_by,
    }


def list_templates(db: Session, user: User, kind: str | None = None, include_archived: bool = False) -> list[dict]:
    tid = _tenant_id(user)
    ensure_default_templates(db, tid)
    q = db.query(ContractTemplate).filter(ContractTemplate.tenant_id == tid, ContractTemplate.is_current.is_(True))
    if kind:
        q = q.filter(ContractTemplate.kind == kind)
    if not include_archived:
        q = q.filter(ContractTemplate.archived.is_(False))
    return [template_out(t) for t in q.order_by(ContractTemplate.kind.desc(), ContractTemplate.title).all()]


def _template(db: Session, user: User, template_id: int) -> ContractTemplate:
    t = db.get(ContractTemplate, template_id)
    if t is None or t.tenant_id != _tenant_id(user):
        _bad("Template not found", 404)
    return t


def template_versions(db: Session, user: User, template_id: int) -> list[dict]:
    t = _template(db, user, template_id)
    rows = (
        db.query(ContractTemplate)
        .filter(ContractTemplate.tenant_id == t.tenant_id, ContractTemplate.group_key == t.group_key)
        .order_by(ContractTemplate.version.desc())
        .all()
    )
    names = {u.id: _name(u) for u in db.query(User).filter(User.id.in_({r.created_by_user_id for r in rows} or {-1}))}
    return [template_out(r, names.get(r.created_by_user_id, "")) for r in rows]


def _clean_template(data: dict) -> tuple[str, str, str]:
    kind = data.get("kind") or ""
    if kind not in KIND_LABEL:
        _bad("Choose Vendor agreement or Client service contract.")
    title = " ".join((data.get("title") or "").split())[:200]
    body = (data.get("body") or "").replace("\r\n", "\n").strip()
    if not title:
        _bad("Add a title.")
    if len(body) < 20:
        _bad("Add the contract text.")
    if len(body) > 100_000:
        _bad("The contract text is too long (100,000 characters at most).")
    return kind, title, body


def create_template(db: Session, user: User, data: dict) -> dict:
    if not is_signatory(user):
        _bad("Only an admin can change contract templates.", 403)
    kind, title, body = _clean_template(data)
    t = ContractTemplate(tenant_id=_tenant_id(user), kind=kind, group_key=uuid.uuid4().hex, version=1,
                         is_current=True, title=title, body=body, created_by_user_id=user.id)
    db.add(t)
    db.commit()
    db.refresh(t)
    return template_out(t, _name(user))


def update_template(db: Session, user: User, template_id: int, data: dict) -> dict:
    """Editing never changes a stored version: it adds version + 1 and makes it current."""
    if not is_signatory(user):
        _bad("Only an admin can change contract templates.", 403)
    old = _template(db, user, template_id)
    _kind, title, body = _clean_template({**data, "kind": old.kind})
    latest = (
        db.query(ContractTemplate)
        .filter(ContractTemplate.tenant_id == old.tenant_id, ContractTemplate.group_key == old.group_key)
        .order_by(ContractTemplate.version.desc())
        .first()
    )
    if latest and latest.title == title and latest.body == body:
        return template_out(latest)
    db.query(ContractTemplate).filter(
        ContractTemplate.tenant_id == old.tenant_id, ContractTemplate.group_key == old.group_key
    ).update({ContractTemplate.is_current: False}, synchronize_session=False)
    t = ContractTemplate(tenant_id=old.tenant_id, kind=old.kind, group_key=old.group_key,
                         version=(latest.version if latest else old.version) + 1, is_current=True,
                         archived=False, title=title, body=body, created_by_user_id=user.id)
    db.add(t)
    db.commit()
    db.refresh(t)
    return template_out(t, _name(user))


def archive_template(db: Session, user: User, template_id: int, archived: bool = True) -> dict:
    if not is_signatory(user):
        _bad("Only an admin can change contract templates.", 403)
    t = _template(db, user, template_id)
    db.query(ContractTemplate).filter(
        ContractTemplate.tenant_id == t.tenant_id, ContractTemplate.group_key == t.group_key
    ).update({ContractTemplate.archived: archived}, synchronize_session=False)
    db.commit()
    db.refresh(t)
    return template_out(t)


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_to_text(content: bytes) -> str:
    """Plain text of a .docx (paragraphs; Heading styles become "# " lines). No python-docx needed."""
    if len(content) > MAX_DOCX_BYTES:
        _bad("The file is too large (5 MB at most).")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            info = z.getinfo("word/document.xml")
            if info.file_size > 20_000_000:
                _bad("The document is too large.")
            xml = z.read(info)
    except HTTPException:
        raise
    except Exception:
        _bad("That is not a Word (.docx) file. Save it as .docx, or paste the text.")
    if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
        _bad("The document could not be read.")
    root = ElementTree.fromstring(xml)
    lines: list[str] = []
    for p in root.iter(f"{_W}p"):
        parts: list[str] = []
        for node in p.iter():
            if node.tag == f"{_W}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{_W}tab":
                parts.append("\t")
            elif node.tag in (f"{_W}br", f"{_W}cr"):
                parts.append("\n")
        text = "".join(parts).strip()
        style = p.find(f"{_W}pPr/{_W}pStyle")
        heading = style is not None and "heading" in (style.get(f"{_W}val") or "").lower()
        if text:
            lines.append(f"# {text}" if heading else text)
    return "\n\n".join(lines)


# --- values for placeholders -----------------------------------------------------------


def _business(db: Session, tenant_id: int) -> dict:
    from app.livewell.gst_invoices import get_business

    return get_business(db.get(Tenant, tenant_id))


def _today_text() -> str:
    return datetime.now(IST).strftime("%d %b %Y")


def _plan_values(db: Session, elder: Elder) -> dict[str, str]:
    try:
        from app.livewell import care_plan_catalog as catalog
        from app.models.customer_plan import CustomerPlan

        row = (
            db.query(CustomerPlan)
            .filter(CustomerPlan.elder_id == elder.id, CustomerPlan.status != "cancelled")
            .order_by(CustomerPlan.start_date.desc(), CustomerPlan.id.desc())
            .first()
        )
    except Exception:
        logger.exception("contract_plan_lookup_failed elder=%s", elder.id)
        return {}
    if not row:
        return {}
    p = catalog.plan(row.plan_id)
    fmt = lambda d: d.strftime("%d %b %Y") if isinstance(d, date) else ""  # noqa: E731
    return {
        "plan_name": p["name"] if p else row.plan_id,
        "plan_amount": _rupees(row.amount_paise),
        "start_date": fmt(row.start_date),
        "end_date": fmt(row.end_date),
    }


def _vendor_values(v: Vendor) -> dict[str, str]:
    services = dict(VENDOR_SERVICES)
    names = [v.services_other if s == "other" and v.services_other else services.get(s, s) for s in (v.services or [])]
    basis = dict(FEE_BASES).get(v.fee_basis or "", "")
    return {
        "vendor_name": v.owner_name or v.company_name,
        "vendor_company": v.company_name,
        "vendor_address": v.address or "",
        "vendor_gstin": v.gstin or "Not registered",
        "vendor_phone": v.phone1 or "",
        "vendor_services": ", ".join(names),
        "vendor_fee": f"{_rupees(v.fee_paise)} {basis.lower()}".strip() if v.fee_paise is not None else "",
    }


def _party(db: Session, user: User, kind: str, elder_id: int | None, vendor_id: int | None):
    tid = _tenant_id(user)
    if kind == "client":
        elder = db.get(Elder, elder_id) if elder_id else None
        if elder is None:
            _bad("Client not found", 404)
        assert_tenant_access(user, elder.tenant_id)
        assert_elder_in_team(db, user, elder.id)
        return elder, None
    if kind == "vendor":
        vendor = db.get(Vendor, vendor_id) if vendor_id else None
        if vendor is None or vendor.tenant_id != tid:
            _bad("Vendor not found", 404)
        return None, vendor
    _bad("Choose Vendor agreement or Client service contract.")


def field_values(db: Session, tenant_id: int, elder: Elder | None, vendor: Vendor | None,
                 signer_name: str = "", overrides: dict | None = None) -> dict[str, str]:
    biz = _business(db, tenant_id)
    values = {
        "company_name": biz.get("legal_name") or "",
        "company_address": biz.get("address") or "",
        "company_gstin": biz.get("gstin") or "",
        "date": _today_text(),
        "start_date": _today_text(),
        "end_date": "",
        "signer_name": signer_name,
    }
    if elder is not None:
        values.update({
            "client_name": f"{elder.first_name or ''} {elder.last_name or ''}".strip(),
            "client_address": elder.address or "",
            "client_phone": elder.phone or "",
        })
        values.update(_plan_values(db, elder))
    if vendor is not None:
        values.update(_vendor_values(vendor))
    for k, v in (overrides or {}).items():
        if k in PLACEHOLDER_KEYS and isinstance(v, str) and v.strip():
            values[k] = v.strip()[:300]
    return values


def preview(db: Session, user: User, data: dict) -> dict:
    t = _template(db, user, int(data.get("template_id") or 0))
    elder, vendor = _party(db, user, t.kind, data.get("elder_id"), data.get("vendor_id"))
    values = field_values(db, t.tenant_id, elder, vendor, data.get("signer_name") or "", data.get("fields"))
    used = sorted({m.group(1) for m in _PH.finditer(t.title + "\n" + t.body) if m.group(1) in PLACEHOLDER_KEYS})
    return {
        "template_id": t.id,
        "template_version": t.version,
        "title": render(t.title, values),
        "body": render(t.body, values),
        "fields": {k: values.get(k, "") for k in used},
        "missing": [k for k in used if not (values.get(k) or "").strip()],
        "suggested_signers": _suggested_signers(db, elder, vendor),
    }


def _suggested_signers(db: Session, elder: Elder | None, vendor: Vendor | None) -> list[dict]:
    out: list[dict] = []
    if vendor is not None:
        out.append({"name": vendor.owner_name or vendor.company_name, "email": "", "mobile": vendor.phone1 or "",
                    "relation": "Vendor"})
    if elder is not None:
        out.append({"name": f"{elder.first_name or ''} {elder.last_name or ''}".strip(),
                    "email": getattr(elder, "email", None) or "", "mobile": elder.phone or "", "relation": "Client"})
        from app.models.family_elder_link import FamilyElderLink

        try:
            fam = (
                db.query(User)
                .join(FamilyElderLink, FamilyElderLink.user_id == User.id)
                .filter(FamilyElderLink.elder_id == elder.id)
                .limit(10)
                .all()
            )
        except Exception:
            fam = []
        for u in fam:
            if any(o["name"].lower() == _name(u).lower() for o in out):
                continue  # the client's own login: already listed
            out.append({"name": _name(u), "email": u.email or "", "mobile": getattr(u, "phone", None) or "",
                        "relation": (u.portal_relationship or "Family").title()})
    return out


# --- contracts -----------------------------------------------------------------------


def contract_out(db: Session, c: Contract, *, full: bool = True) -> dict:
    status = effective_status(c)
    out = {
        "id": c.id,
        "ref": f"KA-CT-{c.id:05d}",
        "kind": c.kind,
        "kind_label": KIND_LABEL.get(c.kind, c.kind),
        "elder_id": c.elder_id,
        "vendor_id": c.vendor_id,
        "party_name": _party_name(db, c),
        "title": c.title,
        "status": status,
        "template_id": c.template_id,
        "template_version": c.template_version,
        "signer_name": c.signer_name,
        "signer_email": c.signer_email,
        "signer_mobile": c.signer_mobile,
        "signer_relation": c.signer_relation,
        "created_at": _iso(c.created_at),
        "submitted_at": _iso(c.submitted_at),
        "sent_at": _iso(c.sent_at),
        "viewed_at": _iso(c.viewed_at),
        "signed_at": _iso(c.signed_at),
        "cancelled_at": _iso(c.cancelled_at),
        "expires_at": _iso(c.expires_at),
        "company_signer_name": c.company_signer_name,
        "company_signer_designation": c.company_signer_designation,
        "company_signed_at": _iso(c.company_signed_at),
        "locked": c.company_signed_at is not None,
        "has_pdf": c.status == "signed",
        "sign_path": sign_path(c) if status in ("sent", "viewed") else None,
        "created_by": _name(db.get(User, c.created_by_user_id)) if c.created_by_user_id else "",
    }
    if full:
        out.update({
            "body": c.body,
            "fields": c.fields or {},
            "text_sha256": c.signed_text_sha256 or c.company_text_sha256,
            "history": c.history or [],
        })
    return out


def _party_name(db: Session, c: Contract) -> str:
    if c.elder_id:
        e = db.get(Elder, c.elder_id)
        return f"{e.first_name or ''} {e.last_name or ''}".strip() if e else ""
    if c.vendor_id:
        v = db.get(Vendor, c.vendor_id)
        return v.company_name if v else ""
    return ""


def _contract(db: Session, user: User, contract_id: int) -> Contract:
    c = db.get(Contract, contract_id)
    if c is None:
        _bad("Contract not found", 404)
    assert_tenant_access(user, c.tenant_id)
    if c.elder_id:
        ids = team_elder_ids(db, user)
        if ids is not None and c.elder_id not in ids:
            _bad("Contract not found", 404)
    return c


def get_contract(db: Session, user: User, contract_id: int) -> dict:
    return contract_out(db, _contract(db, user, contract_id))


def list_contracts(db: Session, user: User, *, elder_id: int | None = None, vendor_id: int | None = None,
                   status: str | None = None, kind: str | None = None) -> list[dict]:
    tid = _tenant_id(user)
    q = db.query(Contract).filter(Contract.tenant_id == tid)
    if elder_id:
        q = q.filter(Contract.elder_id == elder_id)
    if vendor_id:
        q = q.filter(Contract.vendor_id == vendor_id)
    if kind in KIND_LABEL:
        q = q.filter(Contract.kind == kind)
    ids = team_elder_ids(db, user)
    if ids is not None:
        q = q.filter(or_(Contract.elder_id.is_(None), Contract.elder_id.in_(ids or {-1})))
    rows = [contract_out(db, c, full=False) for c in q.order_by(Contract.id.desc()).limit(500).all()]
    if status:
        rows = [r for r in rows if r["status"] == status]
    return rows


def _clean_signer(data: dict) -> dict:
    name = " ".join((data.get("signer_name") or "").split())[:200]
    if not name:
        _bad("Add the name of the person who signs.")
    email = (data.get("signer_email") or "").strip()[:255] or None
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        _bad("That email address doesn't look right.")
    mobile = re.sub(r"[^\d+]", "", data.get("signer_mobile") or "")[:30] or None
    relation = " ".join((data.get("signer_relation") or "").split())[:60] or None
    return {"signer_name": name, "signer_email": email, "signer_mobile": mobile, "signer_relation": relation}


def create_contract(db: Session, user: User, data: dict, *, ip: str = "", ua: str = "") -> dict:
    t = _template(db, user, int(data.get("template_id") or 0))
    if t.archived:
        _bad("That template is archived.")
    elder, vendor = _party(db, user, t.kind, data.get("elder_id"), data.get("vendor_id"))
    signer = _clean_signer(data)
    values = field_values(db, t.tenant_id, elder, vendor, signer["signer_name"], data.get("fields"))
    # Staff may adjust the filled-in text before KushAlaya signs (one-off clauses).
    title = " ".join((data.get("title") or "").split())[:200] or render(t.title, values)
    body = (data.get("body") or "").replace("\r\n", "\n").strip() or render(t.body, values)
    if len(body) > 100_000:
        _bad("The contract text is too long.")
    c = Contract(
        tenant_id=t.tenant_id, kind=t.kind, template_id=t.id, template_version=t.version,
        elder_id=elder.id if elder else None, vendor_id=vendor.id if vendor else None,
        title=title, body=body, fields={k: values.get(k, "") for k in PLACEHOLDER_KEYS if values.get(k)},
        status="draft", created_by_user_id=user.id, history=[], **signer,
    )
    db.add(c)
    db.flush()
    _history(c, "created", _name(user))
    action = data.get("action") or "draft"
    if action == "sign_and_send":
        return _sign_and_send(db, user, c, ip=ip, ua=ua)
    if action == "submit":
        return _submit(db, user, c)
    db.commit()
    db.refresh(c)
    return contract_out(db, c)


def update_contract(db: Session, user: User, contract_id: int, data: dict) -> dict:
    c = _contract(db, user, contract_id)
    if c.company_signed_at is not None or c.status not in ("draft", "awaiting_company"):
        _bad("KushAlaya has signed this contract, so its text is locked. Cancel it and make a new one.", 409)
    for k, v in _clean_signer({**{
        "signer_name": c.signer_name, "signer_email": c.signer_email,
        "signer_mobile": c.signer_mobile, "signer_relation": c.signer_relation}, **data}).items():
        setattr(c, k, v)
    if data.get("title"):
        c.title = " ".join(data["title"].split())[:200]
    if data.get("body"):
        c.body = data["body"].replace("\r\n", "\n").strip()[:100_000]
    _history(c, "edited", _name(user))
    db.commit()
    db.refresh(c)
    return contract_out(db, c)


def _submit(db: Session, user: User, c: Contract) -> dict:
    if c.status not in ("draft", "awaiting_company"):
        _bad("This contract has already been sent.", 409)
    c.status = "awaiting_company"
    c.submitted_at = _now()
    _history(c, "waiting_for_company_signature", _name(user))
    db.commit()
    db.refresh(c)
    _email_admins_to_sign(db, c, _name(user))
    return contract_out(db, c)


def submit(db: Session, user: User, contract_id: int) -> dict:
    c = _contract(db, user, contract_id)
    if is_signatory(user) and get_signatory(db, user):
        _bad("You are a signatory: use Sign & send.", 409)
    return _submit(db, user, c)


def _sign_and_send(db: Session, user: User, c: Contract, *, ip: str, ua: str) -> dict:
    if not is_signatory(user):
        _bad("Only an admin (authorised signatory) can sign for KushAlaya. Send it for KushAlaya signature instead.", 403)
    if c.status not in ("draft", "awaiting_company") or c.company_signed_at is not None:
        _bad("KushAlaya has already signed this contract.", 409)
    sig = get_signatory(db, user)
    if sig is None:
        _bad("Set up your signature first (name, designation and signature).", 409)
    if not c.signer_email and not c.signer_mobile:
        _bad("Add the signer's email or mobile so the link can reach them.")
    now = _now()
    c.company_signer_user_id = user.id
    c.company_signer_name = sig.name
    c.company_signer_designation = sig.designation
    c.company_signer_email = user.email
    c.company_signature_kind = sig.signature_kind
    c.company_signature_png = sig.signature_png
    c.company_signature_text = sig.signature_text
    c.company_signed_at = now
    c.company_ip = (ip or "")[:64]
    c.company_user_agent = (ua or "")[:400]
    c.company_text_sha256 = text_sha256(c.title, c.body)
    c.status = "sent"
    c.sent_at = now
    _new_link(c)
    _history(c, "signed_by_company_and_sent", sig.name)
    db.commit()
    db.refresh(c)
    _email_link(db, c)
    return contract_out(db, c)


def sign_and_send(db: Session, user: User, contract_id: int, *, ip: str = "", ua: str = "") -> dict:
    return _sign_and_send(db, user, _contract(db, user, contract_id), ip=ip, ua=ua)


def resend(db: Session, user: User, contract_id: int) -> dict:
    """New link (the old one stops working), 30 more days, email again."""
    c = _contract(db, user, contract_id)
    if c.status not in ("sent", "viewed"):
        _bad("Only a sent, unsigned contract can be resent.", 409)
    c.status = "sent"
    c.sent_at = _now()
    _new_link(c)
    _history(c, "resent", _name(user))
    db.commit()
    db.refresh(c)
    _email_link(db, c)
    return contract_out(db, c)


def cancel(db: Session, user: User, contract_id: int) -> dict:
    c = _contract(db, user, contract_id)
    if c.status in ("signed", "cancelled"):
        _bad("A signed or cancelled contract can't be cancelled.", 409)
    c.status = "cancelled"
    c.cancelled_at = _now()
    c.token_nonce = None  # the link stops working at once
    _history(c, "cancelled", _name(user))
    db.commit()
    db.refresh(c)
    return contract_out(db, c)


# --- public signing --------------------------------------------------------------------


def _public_block(kind: str | None, png: str | None, text: str | None) -> dict:
    return {"signature_kind": kind, "signature_png": png, "signature_text": text}


def _link_open(c: Contract, now: datetime) -> bool:
    if c.status == "signed":
        return bool(c.signed_at and c.signed_at + timedelta(days=SIGNED_LINK_DAYS) > now) or bool(
            c.expires_at and c.expires_at > now)
    return c.status in ("sent", "viewed") and bool(c.expires_at and c.expires_at > now)


def public_view(db: Session, token: str) -> dict:
    c = contract_for_token(db, token)
    now = _now()
    if c.status == "cancelled":
        _bad("This contract was withdrawn. Please contact KushAlaya.", 410)
    if not _link_open(c, now):
        _bad("This link has expired. Ask KushAlaya to send it again.", 410)
    if c.status == "sent":
        c.status = "viewed"
        c.viewed_at = now
        _history(c, "viewed", c.signer_name)
        db.commit()
        db.refresh(c)
    biz = _business(db, c.tenant_id)
    return {
        "ref": f"KA-CT-{c.id:05d}",
        "kind": c.kind,
        "party_label": PARTY_LABEL.get(c.kind, "Signer"),
        "title": c.title,
        "body": c.body,
        "status": c.status,
        "signer_name": c.signer_name,
        "company_name": biz.get("legal_name") or "KushAlaya",
        "expires_at": _iso(c.expires_at),
        "company": {
            "name": c.company_signer_name,
            "designation": c.company_signer_designation,
            "signed_at": _iso(c.company_signed_at),
            "signed_at_ist": _ist(c.company_signed_at),
            **_public_block(c.company_signature_kind, c.company_signature_png, c.company_signature_text),
        },
        "signer": {
            "name": c.signed_name,
            "signed_at": _iso(c.signed_at),
            "signed_at_ist": _ist(c.signed_at),
            **_public_block(c.signature_kind, c.signature_png, c.signature_text),
        } if c.status == "signed" else None,
        "text_sha256": c.signed_text_sha256 or c.company_text_sha256,
    }


def public_sign(db: Session, token: str, data: dict, *, ip: str = "", ua: str = "") -> dict:
    c = contract_for_token(db, token)
    now = _now()
    if c.status == "signed":
        _bad("This contract is already signed.", 409)
    if c.status == "cancelled":
        _bad("This contract was withdrawn. Please contact KushAlaya.", 410)
    if c.status not in ("sent", "viewed") or not _link_open(c, now):
        _bad("This link has expired. Ask KushAlaya to send it again.", 410)
    if not c.company_signed_at or not c.company_text_sha256:
        _bad("KushAlaya hasn't signed this contract yet.", 409)
    digest = text_sha256(c.title, c.body)
    if not hmac.compare_digest(digest, c.company_text_sha256):
        logger.error("contract_text_changed contract=%s", c.id)
        _bad("This contract's text changed after KushAlaya signed it. Please contact KushAlaya.", 409)
    if data.get("agree") is not True:
        _bad("Tick “I agree” to sign.")
    name = " ".join((data.get("name") or "").split())[:200]
    if len(name) < 2:
        _bad("Type your full name.")
    kind, png, text = clean_signature(data.get("signature_png"), data.get("signature_text"))
    # One conditional UPDATE: a second tap or a second device can't sign again.
    done = (
        db.query(Contract)
        .filter(Contract.id == c.id, Contract.status.in_(["sent", "viewed"]), Contract.token_nonce == c.token_nonce)
        .update({
            Contract.status: "signed",
            Contract.signed_at: now,
            Contract.signed_name: name,
            Contract.signature_kind: kind,
            Contract.signature_png: png,
            Contract.signature_text: text,
            Contract.signer_ip: (ip or "")[:64],
            Contract.signer_user_agent: (ua or "")[:400],
            Contract.signed_text_sha256: digest,
            Contract.viewed_at: c.viewed_at or now,
        }, synchronize_session=False)
    )
    if done != 1:
        db.rollback()
        _bad("This contract is already signed.", 409)
    db.commit()
    db.refresh(c)
    _history(c, "signed", name)
    db.commit()
    try:
        store_pdf(db, c)
    except Exception:
        logger.exception("contract_pdf_failed contract=%s", c.id)  # rebuilt on first download
    _email_signed(db, c)
    return public_view(db, token)


def public_pdf(db: Session, token: str) -> tuple[bytes, str]:
    c = contract_for_token(db, token)
    if c.status != "signed" or not _link_open(c, _now()):
        _bad("The signed copy isn't available on this link.", 404)
    return pdf_bytes(db, c)


# --- PDF -----------------------------------------------------------------------------


def _pdf_text(s: str) -> str:
    """reportlab's base fonts have no ₹ glyph; escape for its mini-HTML."""
    return escape((s or "").replace("₹", "Rs. "))


def render_pdf(db: Session, c: Contract) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    body_style = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=14, spaceAfter=6)
    head_style = ParagraphStyle("head", parent=styles["Heading3"], spaceBefore=8, spaceAfter=4)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, leading=10)
    typed = ParagraphStyle("typed", parent=styles["Normal"], fontName="Times-Italic", fontSize=20, leading=24)
    biz = _business(db, c.tenant_id)
    company = biz.get("legal_name") or "KushAlaya"

    story = [Paragraph(f"<b>{_pdf_text(c.title)}</b>", styles["Title"])]
    story.append(Paragraph(f"{_pdf_text(company)} · Ref KA-CT-{c.id:05d}", small))
    story.append(Spacer(1, 4 * mm))
    for block in re.split(r"\n\s*\n", c.body or ""):
        block = block.strip()
        if not block:
            continue
        if block.startswith("#"):
            first, _, block = block.partition("\n")
            story.append(Paragraph(f"<b>{_pdf_text(first.lstrip('#').strip())}</b>", head_style))
            block = block.strip()
        if block:
            story.append(Paragraph(_pdf_text(block).replace("\n", "<br/>"), body_style))

    def sig_cell(kind: str | None, png: str | None, text: str | None):
        raw = _png_bytes(png) if kind == "drawn" else None
        if raw:
            try:
                iw, ih = ImageReader(io.BytesIO(raw)).getSize()
                w = 60 * mm
                h = min(22 * mm, w * ih / max(iw, 1))
                return Image(io.BytesIO(raw), width=h * iw / max(ih, 1), height=h)
            except Exception:
                pass
        return Paragraph(_pdf_text(text or ""), typed)

    party = PARTY_LABEL.get(c.kind, "Signer")
    blocks = Table(
        [
            [Paragraph(f"<b>For {_pdf_text(company)}</b>", body_style), Paragraph(f"<b>{party}</b>", body_style)],
            [sig_cell(c.company_signature_kind, c.company_signature_png, c.company_signature_text),
             sig_cell(c.signature_kind, c.signature_png, c.signature_text)],
            [Paragraph(f"{_pdf_text(c.company_signer_name or '')}<br/>{_pdf_text(c.company_signer_designation or '')}"
                       f"<br/>{_ist(c.company_signed_at)}", small),
             Paragraph(f"{_pdf_text(c.signed_name or '')}"
                       + (f"<br/>{_pdf_text(c.signer_relation)}" if c.signer_relation else "")
                       + f"<br/>{_ist(c.signed_at)}", small)],
        ],
        colWidths=[88 * mm, 88 * mm],
    )
    blocks.setStyle(TableStyle([
        ("BOX", (0, 0), (0, -1), 0.5, colors.grey),
        ("BOX", (1, 0), (1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [Spacer(1, 8 * mm), Paragraph("<b>Signatures</b>", head_style), blocks]

    story += [PageBreak(), Paragraph("<b>Audit trail</b>", styles["Heading2"])]
    rows = [
        ["Contract", f"KA-CT-{c.id:05d} · {KIND_LABEL.get(c.kind, c.kind)} · template v{c.template_version or 1}"],
        ["SHA-256 of signed text", c.signed_text_sha256 or c.company_text_sha256 or ""],
        ["Signing link sent to", ", ".join(x for x in (c.signer_email, c.signer_mobile) if x)],
        ["Link sent", f"{_utc(c.sent_at)} · {_ist(c.sent_at)}"],
        ["Link opened", f"{_utc(c.viewed_at)} · {_ist(c.viewed_at)}"],
        [f"Signed for {company}", f"{c.company_signer_name or ''}, {c.company_signer_designation or ''}"],
        ["  Time", f"{_utc(c.company_signed_at)} · {_ist(c.company_signed_at)}"],
        ["  IP address", c.company_ip or ""],
        ["  Device", c.company_user_agent or ""],
        ["  Text hash at signing", c.company_text_sha256 or ""],
        [f"Signed by {party.lower()}", f"{c.signed_name or ''}" + (f" ({c.signer_relation})" if c.signer_relation else "")],
        ["  Time", f"{_utc(c.signed_at)} · {_ist(c.signed_at)}"],
        ["  IP address", c.signer_ip or ""],
        ["  Device", c.signer_user_agent or ""],
        ["  Text hash at signing", c.signed_text_sha256 or ""],
        ["  Method", f"{'Drawn' if c.signature_kind == 'drawn' else 'Typed'} signature, typed full name and “I agree” tick"],
    ]
    audit = Table([[Paragraph(_pdf_text(a), small), Paragraph(_pdf_text(b), small)] for a, b in rows],
                  colWidths=[45 * mm, 131 * mm])
    audit.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story += [audit, Spacer(1, 4 * mm), Paragraph(
        "Signed electronically. The SHA-256 value identifies the exact text both parties signed; "
        "any change to the text gives a different value.", small)]

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, title=c.title, author=company,
                      leftMargin=17 * mm, rightMargin=17 * mm, topMargin=16 * mm, bottomMargin=16 * mm).build(story)
    return buf.getvalue()


def _file_name(c: Contract) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "-", f"{c.title}-{_party_name_cached(c)}").strip("-")[:80] or "contract"
    return f"KA-CT-{c.id:05d}-{safe}-signed.pdf"


def _party_name_cached(c: Contract) -> str:
    return c.signed_name or c.signer_name or ""


def store_pdf(db: Session, c: Contract) -> Document:
    from app.core.storage import get_storage

    if c.status != "signed":
        _bad("Only a signed contract has a signed PDF.", 409)
    if c.document_id:
        doc = db.get(Document, c.document_id)
        if doc:
            return doc
    pdf = render_pdf(db, c)
    entity_type, entity_id = ("elder", c.elder_id) if c.elder_id else ("vendor", c.vendor_id or 0)
    name = _file_name(c)
    key, url = get_storage().save(c.tenant_id, entity_type, entity_id, name, pdf, "application/pdf")
    doc = Document(
        tenant_id=c.tenant_id, entity_type=entity_type, entity_id=entity_id, document_type=DOCUMENT_TYPE,
        document_name=c.title, file_name=name, storage_key=key, storage_url=url, mime_type="application/pdf",
        file_size_bytes=len(pdf), verification_status="VERIFIED", uploaded_at=_now(),
    )
    db.add(doc)
    db.flush()
    c.document_id = doc.id
    db.commit()
    return doc


def pdf_bytes(db: Session, c: Contract) -> tuple[bytes, str]:
    from app.core.storage import get_storage

    doc = store_pdf(db, c)
    try:
        content, _mime = get_storage().read(doc.storage_key)
    except Exception:
        logger.exception("contract_pdf_read_failed contract=%s", c.id)
        content = render_pdf(db, c)
    return content, doc.file_name


def staff_pdf(db: Session, user: User, contract_id: int) -> tuple[bytes, str]:
    return pdf_bytes(db, _contract(db, user, contract_id))


# --- family ------------------------------------------------------------------------------


def family_list(db: Session, elder: Elder) -> list[dict]:
    rows = (
        db.query(Contract)
        .filter(Contract.tenant_id == elder.tenant_id, Contract.elder_id == elder.id, Contract.status == "signed")
        .order_by(Contract.signed_at.desc())
        .all()
    )
    return [{
        "id": c.id, "ref": f"KA-CT-{c.id:05d}", "title": c.title, "signed_at": _iso(c.signed_at),
        "signed_name": c.signed_name, "company_signer_name": c.company_signer_name,
    } for c in rows]


def family_pdf(db: Session, elder: Elder, contract_id: int) -> tuple[bytes, str]:
    c = db.get(Contract, contract_id)
    if c is None or c.elder_id != elder.id or c.tenant_id != elder.tenant_id or c.status != "signed":
        _bad("Contract not found", 404)
    return pdf_bytes(db, c)


# --- email ---------------------------------------------------------------------------------


def _send(recipients: list[str], title: str, body: str, *, path: str, family: bool, who: str = "") -> None:
    from app.livewell.email_notifications import email_context, send

    try:
        with email_context(path, who):
            send(recipients, title, body, family=family)
    except Exception:
        logger.exception("contract_email_failed")


def _staff_path(c: Contract) -> str:
    if c.elder_id:
        return f"/kushalaya/customers/{c.elder_id}?tab=documents"
    return "/kushalaya/contracts"


def _email_admins_to_sign(db: Session, c: Contract, by: str) -> None:
    admins = [
        u.email for u in db.query(User).filter(
            User.tenant_id == c.tenant_id, User.role == TENANT_ADMIN, User.status == "ACTIVE").all() if u.email
    ]
    _send(admins, f"Contract to sign: {c.title}",
          f"{by or 'A care manager'} prepared “{c.title}” for {_party_name(db, c)}. "
          "It goes to the signer once an authorised signatory signs it for KushAlaya (Sign & send).",
          path="/kushalaya/contracts", family=False, who=_party_name(db, c))


def _email_link(db: Session, c: Contract) -> None:
    if not c.signer_email:
        return
    company = _business(db, c.tenant_id).get("legal_name") or "KushAlaya"
    _send([c.signer_email], f"Please sign: {c.title}",
          f"Dear {c.signer_name},\n{company} has signed “{c.title}” and sent it to you. "
          f"Open the link to read it and sign on your phone or computer. The link works for {LINK_DAYS} days.",
          path=sign_path(c) or "", family=True)


def _email_signed(db: Session, c: Contract) -> None:
    from app.livewell.email_notifications import agency_recipients, staff_recipients

    company = _business(db, c.tenant_id).get("legal_name") or "KushAlaya"
    if c.signer_email:
        _send([c.signer_email], f"Signed: {c.title}",
              f"Thank you, {c.signed_name}. “{c.title}” is now signed by you and {company}. "
              f"Open the link to download the signed PDF (available for {SIGNED_LINK_DAYS} days).",
              path=sign_path(c) or "", family=True)
    try:
        if c.elder_id and (elder := db.get(Elder, c.elder_id)):
            staff = staff_recipients(db, elder, "contract")
        else:
            staff = agency_recipients(db, c.tenant_id, "contract")
    except Exception:
        logger.exception("contract_staff_recipients_failed contract=%s", c.id)
        staff = []
    to, seen = [], set()
    for a in [c.company_signer_email or "", *staff]:
        if a and a.lower() not in seen and a.lower() != (c.signer_email or "").lower():
            seen.add(a.lower())
            to.append(a)
    _send(to, f"Contract signed: {c.title}",
          f"{c.signed_name} signed “{c.title}” ({_party_name(db, c)}) on {_ist(c.signed_at)}. "
          "Both signatures are on the PDF; it is stored with the documents.",
          path=_staff_path(c), family=False, who=_party_name(db, c))


def meta(db: Session, user: User) -> dict:
    return {
        "kinds": [{"code": k, "label": lbl} for k, lbl in CONTRACT_KINDS],
        "placeholders": [{"key": k, "label": lbl, "kinds": list(kinds)} for k, lbl, kinds in PLACEHOLDERS],
        "can_sign": is_signatory(user),
        "signatory": signatory_out(get_signatory(db, user)) if is_signatory(user) else None,
        "link_days": LINK_DAYS,
        "my_name": _name(user),
    }
