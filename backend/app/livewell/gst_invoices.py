"""GST tax invoices, bills of supply and credit notes (FIX_TODO #102).

When an invoice is issued
    Every successful wallet *debit* that pays an order / quote ("order") or a
    service request ("service_request") gets one invoice, in the same database
    transaction as the debit (hooked from WalletService.record). A *refund* of
    that payment gets one credit note that references the invoice. Wallet
    top-ups are not sales and get no invoice (they keep their KA- receipt).

Numbering (gapless, per financial year Apr–Mar, IST)
    invoice      {PREFIX}{YY}{YY}/{00001}   e.g. KUS2627/00001
    credit note  {PREFIX}{YY}{YY}C/{00001}  e.g. KUS2627C/00001
    The prefix is at most 5 letters/digits, so a number is never longer than
    the 16 characters GST allows. The next number comes from `invoice_counters`
    with one UPDATE … SET last_number = last_number + 1 inside the payment's
    transaction: the row lock serialises concurrent payments, and a rolled-back
    payment rolls its number back too, so there are no gaps.

GST maths (integer paise, never float)
    Orders: the order already charged GST = floor(taxable × 18%) on top of the
    discounted price (commerce.price_order). The invoice shows exactly what was
    paid: taxable = subtotal − discount, tax = paid − taxable.
    Service requests: the quoted price is GST-inclusive, so
    taxable = round_half_up(price × 100 / 118) and tax = price − taxable.
    Same state as the business (place of supply = client's state, default the
    business's own state): CGST 9% + SGST 9% where CGST = ceil(tax / 2) and
    SGST = floor(tax / 2) (the odd paisa goes to CGST). Other state: IGST = tax.
    CGST + SGST (or IGST) + taxable always equals the amount paid, to the paisa.

No GSTIN yet
    Documents are issued as "Bill of supply / receipt" with no GST breakdown;
    the admin settings page shows a banner asking for the GSTIN.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.responses import raise_bad_request, raise_not_found
from app.models.elder import Elder
from app.models.tax_invoice import InvoiceCounter, TaxInvoice
from app.models.tenant import Tenant

log = logging.getLogger(__name__)

KEY = "business"
IST = timezone(timedelta(hours=5, minutes=30))
GST_BP = 1800
DEFAULT_SAC = "9993"  # placeholder (human health / social care services) until the owner confirms codes
DEFAULT_STATE_CODE = "36"  # Telangana (Hyderabad)
DEFAULT_PREFIX = "KUS"
GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
PREFIX_RE = re.compile(r"^[A-Z0-9]{1,5}$")
INVOICED_REFERENCES = ("order", "service_request", "plan_purchase")

STATE_NAMES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra", "29": "Karnataka", "30": "Goa",
    "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
}


# --- Business details (tenant.workflow_config["business"]) -------------------------


def get_business(tenant: Tenant | None) -> dict:
    raw = ((tenant.workflow_config or {}) if tenant else {}).get(KEY) or {}
    hsn = raw.get("hsn_by_category") or {}
    return {
        "legal_name": str(raw.get("legal_name") or (tenant.name if tenant else "") or ""),
        "trade_name": str(raw.get("trade_name") or ""),
        "gstin": str(raw.get("gstin") or ""),
        "address": str(raw.get("address") or (tenant.address if tenant else "") or ""),
        "state_code": str(raw.get("state_code") or DEFAULT_STATE_CODE),
        "email": str(raw.get("email") or ""),
        "phone": str(raw.get("phone") or ""),
        "invoice_prefix": str(raw.get("invoice_prefix") or DEFAULT_PREFIX),
        "default_sac": str(raw.get("default_sac") or DEFAULT_SAC),
        "hsn_by_category": {str(k): str(v) for k, v in hsn.items() if str(v).strip()},
    }


def business_payload(tenant: Tenant | None) -> dict:
    b = get_business(tenant)
    return {
        **b,
        "gst_registered": bool(b["gstin"]),
        "state_name": STATE_NAMES.get(b["state_code"], ""),
        "states": [{"code": k, "name": v} for k, v in sorted(STATE_NAMES.items())],
    }


def save_business(db: Session, tenant: Tenant, body: dict) -> dict:
    current = get_business(tenant)
    for key in ("legal_name", "trade_name", "address", "email", "phone"):
        if key in body and body[key] is not None:
            current[key] = str(body[key]).strip()[:500]
    if "gstin" in body and body["gstin"] is not None:
        gstin = re.sub(r"\s+", "", str(body["gstin"])).upper()
        if gstin and not GSTIN_RE.match(gstin):
            raise_bad_request("That GSTIN doesn't look right — it is 15 characters, like 36ABCDE1234F1Z5")
        current["gstin"] = gstin
        if gstin:
            current["state_code"] = gstin[:2]
    if body.get("state_code") is not None and not current["gstin"]:
        code = str(body["state_code"]).strip().zfill(2)
        if code not in STATE_NAMES:
            raise_bad_request("Pick a state")
        current["state_code"] = code
    if body.get("invoice_prefix") is not None:
        prefix = str(body["invoice_prefix"]).strip().upper()
        if not PREFIX_RE.match(prefix):
            raise_bad_request("Invoice prefix: 1 to 5 letters or digits")
        current["invoice_prefix"] = prefix
    if body.get("default_sac") is not None:
        sac = str(body["default_sac"]).strip()
        if not re.match(r"^\d{4,8}$", sac):
            raise_bad_request("SAC / HSN codes are 4 to 8 digits")
        current["default_sac"] = sac
    if isinstance(body.get("hsn_by_category"), dict):
        cleaned = {}
        for cat, code in body["hsn_by_category"].items():
            code = str(code or "").strip()
            if code and not re.match(r"^\d{4,8}$", code):
                raise_bad_request(f"{cat}: SAC / HSN codes are 4 to 8 digits")
            if code:
                cleaned[str(cat)[:60]] = code
        current["hsn_by_category"] = cleaned
    if not current["legal_name"].strip():
        raise_bad_request("Legal name is needed")
    cfg = dict(tenant.workflow_config or {})
    cfg[KEY] = current
    tenant.workflow_config = cfg
    flag_modified(tenant, "workflow_config")
    db.commit()
    return business_payload(tenant)


# --- Numbering -------------------------------------------------------------------


def financial_year(when: datetime) -> int:
    """Start year of the Indian financial year (Apr–Mar) for an instant, in IST."""
    d = (when if when.tzinfo else when.replace(tzinfo=timezone.utc)).astimezone(IST)
    return d.year if d.month >= 4 else d.year - 1


def _fy_label(fy: int) -> str:
    return f"{fy % 100:02d}{(fy + 1) % 100:02d}"


def format_number(prefix: str, fy: int, kind: str, seq: int) -> str:
    return f"{prefix}{_fy_label(fy)}{'C' if kind == 'credit_note' else ''}/{seq:05d}"


def allocate_number(db: Session, tenant_id: int, fy: int, series: str) -> int:
    """Next number in the series. Must run inside the transaction that stores the document."""
    dialect = db.get_bind().dialect.name
    values = {"tenant_id": tenant_id, "fy": fy, "series": series, "last_number": 0}
    if dialect in ("postgresql", "sqlite"):
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as dialect_insert
        else:
            from sqlalchemy.dialects.sqlite import insert as dialect_insert
        db.execute(dialect_insert(InvoiceCounter).values(**values).on_conflict_do_nothing())
    else:  # pragma: no cover - other databases
        exists = db.execute(
            select(InvoiceCounter.id).where(
                InvoiceCounter.tenant_id == tenant_id, InvoiceCounter.fy == fy, InvoiceCounter.series == series
            )
        ).first()
        if not exists:
            db.add(InvoiceCounter(**values))
            db.flush()
    cond = (InvoiceCounter.tenant_id == tenant_id, InvoiceCounter.fy == fy, InvoiceCounter.series == series)
    db.execute(
        update(InvoiceCounter)
        .where(*cond)
        .values(last_number=InvoiceCounter.last_number + 1)
        .execution_options(synchronize_session=False)
    )
    return int(db.execute(select(InvoiceCounter.last_number).where(*cond)).scalar_one())


# --- Maths -----------------------------------------------------------------------


def split_tax(tax_paise: int, intra_state: bool) -> tuple[int, int, int]:
    """(cgst, sgst, igst). Intra-state: the odd paisa goes to CGST."""
    tax = max(0, int(tax_paise))
    if intra_state:
        return (tax + 1) // 2, tax // 2, 0
    return 0, 0, tax


def taxable_from_inclusive(amount_paise: int, gst_bp: int = GST_BP) -> int:
    """Taxable value inside a GST-inclusive price, rounded half up to the paisa."""
    denom = 10000 + gst_bp
    return (int(amount_paise) * 10000 * 2 + denom) // (denom * 2)


def _customer(db: Session, elder: Elder, supplier_state: str) -> tuple[dict, str]:
    attrs = elder.custom_attributes or {}
    state = str(attrs.get("state_code") or "").strip().zfill(2) if attrs.get("state_code") else ""
    pos = state if state in STATE_NAMES else supplier_state
    name = f"{elder.first_name or ''} {elder.last_name or ''}".strip()
    return {
        "name": name,
        "address": elder.address or "",
        "gstin": str(attrs.get("gstin") or ""),
        "state_code": pos,
    }, pos


def _order_lines(db: Session, order, business: dict) -> list[dict]:
    from app.models.commerce import Product

    out = []
    for ln in order.lines or []:
        p = db.get(Product, int(ln.get("product_id") or 0)) if ln.get("product_id") else None
        cat = p.category if p else ""
        qty = int(ln.get("qty") or 1)
        unit = int(ln.get("unit_paise") or 0)
        out.append({
            "description": str(ln.get("name") or ""),
            "hsn_sac": business["hsn_by_category"].get(cat) or business["default_sac"],
            "qty": qty,
            "unit_paise": unit,
            "amount_paise": unit * qty,
        })
    return out


# --- Issue -----------------------------------------------------------------------


def _existing(db: Session, tenant_id: int, kind: str, source_type: str, source_id: str) -> TaxInvoice | None:
    return (
        db.query(TaxInvoice)
        .filter(
            TaxInvoice.tenant_id == tenant_id,
            TaxInvoice.kind == kind,
            TaxInvoice.source_type == source_type,
            TaxInvoice.source_id == source_id,
        )
        .first()
    )


def _store(db: Session, inv: TaxInvoice, prefix: str) -> TaxInvoice:
    inv.seq = allocate_number(db, inv.tenant_id, inv.fy, "CN" if inv.kind == "credit_note" else "INV")
    inv.number = format_number(prefix, inv.fy, inv.kind, inv.seq)
    db.add(inv)
    db.flush()
    return inv


def issue_invoice(db: Session, *, tenant_id: int, elder_id: int, source_type: str, source_id: str,
                  amount_paise: int, wallet_transaction_id: str | None = None, note: str = "",
                  when: datetime | None = None) -> TaxInvoice | None:
    """Invoice for a payment. Idempotent per source. Does not commit."""
    if amount_paise <= 0 or source_type not in INVOICED_REFERENCES:
        return None
    found = _existing(db, tenant_id, "invoice", source_type, source_id)
    if found:
        return found
    tenant = db.get(Tenant, tenant_id)
    elder = db.get(Elder, elder_id)
    if not tenant or not elder:
        return None
    business = get_business(tenant)
    registered = bool(business["gstin"])
    customer, pos = _customer(db, elder, business["state_code"])
    intra = pos == business["state_code"]
    total = int(amount_paise)

    if source_type == "order":
        from app.models.commerce import Order

        order = db.get(Order, int(source_id))
        lines = _order_lines(db, order, business) if order else []
        gross = sum(ln["amount_paise"] for ln in lines) if lines else total
        discount = int(order.discount_paise or 0) if order else 0
        taxable = gross - discount
        if taxable > total or taxable < 0:  # defensive: never show more taxable value than was paid
            taxable = taxable_from_inclusive(total)
            gross, discount = taxable, 0
    else:
        taxable = taxable_from_inclusive(total)
        lines = [{
            "description": note or "Care service",
            "hsn_sac": business["hsn_by_category"].get("Service") or business["default_sac"],
            "qty": 1,
            "unit_paise": taxable,
            "amount_paise": taxable,
        }]
        gross, discount = taxable, 0

    tax = total - taxable
    cgst, sgst, igst = split_tax(tax, intra) if registered else (0, 0, 0)
    when = when or datetime.now(timezone.utc)
    inv = TaxInvoice(
        tenant_id=tenant_id, elder_id=elder_id, kind="invoice",
        doc_type="tax_invoice" if registered else "bill_of_supply",
        fy=financial_year(when), issued_at=when,
        source_type=source_type, source_id=str(source_id), wallet_transaction_id=wallet_transaction_id,
        supplier={k: business[k] for k in ("legal_name", "trade_name", "gstin", "address", "state_code", "email", "phone")},
        customer=customer, place_of_supply=pos, intra_state=intra, lines=lines,
        gross_paise=gross, discount_paise=discount,
        taxable_paise=taxable if registered else total,
        cgst_paise=cgst, sgst_paise=sgst, igst_paise=igst, total_paise=total, note=(note or "")[:300],
    )
    return _store(db, inv, business["invoice_prefix"])


def issue_credit_note(db: Session, *, tenant_id: int, source_type: str, source_id: str,
                      wallet_transaction_id: str | None = None, when: datetime | None = None) -> TaxInvoice | None:
    """Full credit note against the invoice for this source. Idempotent. Does not commit."""
    original = _existing(db, tenant_id, "invoice", source_type, str(source_id))
    if not original:
        return None  # paid before invoicing existed
    found = _existing(db, tenant_id, "credit_note", source_type, str(source_id))
    if found:
        return found
    business = get_business(db.get(Tenant, tenant_id))
    when = when or datetime.now(timezone.utc)
    cn = TaxInvoice(
        tenant_id=tenant_id, elder_id=original.elder_id, kind="credit_note", doc_type=original.doc_type,
        fy=financial_year(when), issued_at=when, source_type=source_type, source_id=str(source_id),
        wallet_transaction_id=wallet_transaction_id, original_invoice_id=original.id,
        supplier=original.supplier, customer=original.customer, place_of_supply=original.place_of_supply,
        intra_state=original.intra_state, lines=original.lines,
        gross_paise=original.gross_paise, discount_paise=original.discount_paise,
        taxable_paise=original.taxable_paise, cgst_paise=original.cgst_paise, sgst_paise=original.sgst_paise,
        igst_paise=original.igst_paise, total_paise=original.total_paise,
        note=f"Refund against {original.number}",
    )
    return _store(db, cn, business["invoice_prefix"])


def on_wallet_entry(db: Session, entry) -> None:
    """Called from WalletService.record after a ledger row is flushed (same transaction).
    A failure here never blocks the payment: it runs in a savepoint and is logged."""
    if entry is None or entry.status != "success" or entry.reference_type not in INVOICED_REFERENCES:
        return
    if entry.kind not in ("debit", "refund") or not entry.reference_id:
        return
    try:
        from app.models.family_wallet import FamilyWallet

        with db.begin_nested():
            if entry.kind == "debit":
                wallet = db.get(FamilyWallet, entry.wallet_id)
                if wallet is None:
                    return
                issued = issue_invoice(
                    db, tenant_id=entry.tenant_id, elder_id=wallet.elder_id,
                    source_type=entry.reference_type, source_id=str(entry.reference_id),
                    amount_paise=abs(int(entry.amount_minor)), wallet_transaction_id=entry.public_id,
                    note=entry.note or "",
                )
                if issued is not None:
                    from app.livewell.invoice_delivery import send_invoice_to_family
                    db.flush()
                    send_invoice_to_family(db, issued, payment_ref=getattr(entry, 'public_id', None))
            else:
                issue_credit_note(
                    db, tenant_id=entry.tenant_id, source_type=entry.reference_type,
                    source_id=str(entry.reference_id), wallet_transaction_id=entry.public_id,
                )
    except Exception:  # noqa: BLE001 — never block a payment on paperwork
        log.exception("invoice_issue_failed entry=%s", getattr(entry, "public_id", None))


# --- Read ------------------------------------------------------------------------


def _rupees(paise: int) -> str:
    from app.core.money import format_minor

    return format_minor(int(paise or 0))


def invoice_row(inv: TaxInvoice, original_number: str | None = None) -> dict:
    return {
        "id": inv.id,
        "kind": inv.kind,
        "doc_type": inv.doc_type,
        "title": doc_title(inv),
        "number": inv.number,
        "issued_at": inv.issued_at.isoformat() if inv.issued_at else None,
        "elder_id": inv.elder_id,
        "customer_name": (inv.customer or {}).get("name", ""),
        "source_type": inv.source_type,
        "source_id": inv.source_id,
        "original_number": original_number,
        "taxable_paise": inv.taxable_paise,
        "cgst_paise": inv.cgst_paise,
        "sgst_paise": inv.sgst_paise,
        "igst_paise": inv.igst_paise,
        "total_paise": inv.total_paise,
    }


def doc_title(inv: TaxInvoice) -> str:
    if inv.kind == "credit_note":
        return "Credit note"
    return "Tax invoice" if inv.doc_type == "tax_invoice" else "Bill of supply / receipt"


def _rows(db: Session, invs: list[TaxInvoice]) -> list[dict]:
    ids = {i.original_invoice_id for i in invs if i.original_invoice_id}
    numbers = dict(db.query(TaxInvoice.id, TaxInvoice.number).filter(TaxInvoice.id.in_(ids)).all()) if ids else {}
    return [invoice_row(i, numbers.get(i.original_invoice_id)) for i in invs]


def list_for_elders(db: Session, tenant_id: int, elder_ids: set[int] | None, *, limit: int = 200) -> list[dict]:
    q = db.query(TaxInvoice).filter(TaxInvoice.tenant_id == tenant_id)
    if elder_ids is not None:
        q = q.filter(TaxInvoice.elder_id.in_(list(elder_ids) or [-1]))
    return _rows(db, q.order_by(TaxInvoice.issued_at.desc(), TaxInvoice.id.desc()).limit(limit).all())


def get_visible(db: Session, invoice_id: int, tenant_id: int, elder_ids: set[int] | None) -> TaxInvoice:
    inv = db.get(TaxInvoice, invoice_id)
    if not inv or inv.tenant_id != tenant_id or (elder_ids is not None and inv.elder_id not in elder_ids):
        raise_not_found("Invoice not found")
    return inv


# --- PDF -------------------------------------------------------------------------


def render_pdf(db: Session, inv: TaxInvoice) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    def rs(p: int) -> str:  # reportlab's base fonts have no ₹ glyph
        return _rupees(p).replace("₹", "Rs. ")

    from html import escape

    styles = getSampleStyleSheet()
    sup = {k: escape(str(v)) for k, v in (inv.supplier or {}).items()}
    cus = {k: escape(str(v)) for k, v in (inv.customer or {}).items()}
    original = db.get(TaxInvoice, inv.original_invoice_id) if inv.original_invoice_id else None
    issued = inv.issued_at.astimezone(IST) if inv.issued_at.tzinfo else inv.issued_at.replace(tzinfo=timezone.utc).astimezone(IST)
    registered = inv.doc_type == "tax_invoice"

    story = [Paragraph(f"<b>{doc_title(inv)}</b>", styles["Title"])]
    head = [
        f"<b>{sup.get('legal_name', '')}</b>" + (f" ({sup['trade_name']})" if sup.get("trade_name") else ""),
        sup.get("address", ""),
        f"GSTIN: {sup['gstin']}" if sup.get("gstin") else "Not registered under GST",
        f"State: {STATE_NAMES.get(sup.get('state_code', ''), '')} ({sup.get('state_code', '')})",
    ]
    story.append(Paragraph("<br/>".join(h for h in head if h), styles["Normal"]))
    story.append(Spacer(1, 4 * mm))
    meta = [
        f"<b>No.</b> {inv.number} &nbsp; <b>Date</b> {issued:%d %b %Y}",
        f"<b>Against invoice</b> {original.number} dated {original.issued_at.astimezone(IST):%d %b %Y}" if original else "",
        f"<b>Billed to</b> {cus.get('name', '')}" + (f", {cus['address']}" if cus.get("address") else ""),
        f"<b>Place of supply</b> {STATE_NAMES.get(inv.place_of_supply, '')} ({inv.place_of_supply})" if registered else "",
    ]
    story.append(Paragraph("<br/>".join(m for m in meta if m), styles["Normal"]))
    story.append(Spacer(1, 4 * mm))

    data = [["#", "Description", "HSN/SAC", "Qty", "Rate", "Amount"]]
    for i, ln in enumerate(inv.lines or [], 1):
        data.append([str(i), Paragraph(escape(str(ln.get("description", ""))), styles["Normal"]), ln.get("hsn_sac", ""),
                     str(ln.get("qty", 1)), rs(ln.get("unit_paise", 0)), rs(ln.get("amount_paise", 0))])
    totals = [["", "Subtotal", "", "", "", rs(inv.gross_paise)]]
    if inv.discount_paise:
        totals.append(["", "Discount", "", "", "", "-" + rs(inv.discount_paise)])
    if registered:
        totals.append(["", "Taxable value", "", "", "", rs(inv.taxable_paise)])
        if inv.intra_state:
            totals += [["", "CGST 9%", "", "", "", rs(inv.cgst_paise)], ["", "SGST 9%", "", "", "", rs(inv.sgst_paise)]]
        else:
            totals.append(["", "IGST 18%", "", "", "", rs(inv.igst_paise)])
    else:
        other = inv.total_paise - (inv.gross_paise - inv.discount_paise)
        if other:
            totals.append(["", "Taxes and charges", "", "", "", rs(other)])
    totals.append(["", "Total" if inv.kind == "invoice" else "Total credited", "", "", "", rs(inv.total_paise)])
    table = Table(data + totals, colWidths=[8 * mm, 72 * mm, 22 * mm, 12 * mm, 28 * mm, 30 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.grey),
        ("LINEABOVE", (0, len(data)), (-1, len(data)), 0.5, colors.grey),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(table)
    story.append(Spacer(1, 6 * mm))
    foot = ("Paid from the family's prepaid wallet." if inv.kind == "invoice"
            else "Amount refunded to the family's prepaid wallet.")
    if not registered:
        foot += " Issued without GST details: the business's GSTIN has not been added yet."
    story.append(Paragraph(foot + " This is a computer-generated document.", styles["Italic"]))

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, title=inv.number, leftMargin=14 * mm, rightMargin=14 * mm).build(story)
    return buf.getvalue()
