"""DPDP Act 2023 (#104): privacy notice, consent, "Download my data", "Delete my account".

Retention rule (also stated in the notice the family reads):

* Financial records — orders/quotes, tax invoices, credit notes, wallet and its ledger,
  payments — are KEPT for 8 years (Income-tax Act s.44AA / GST Act s.36). They stay linked
  to the client id, but the client's name and contact details are anonymised.
* Everything else personal is erased or anonymised when an admin approves the request:
  the login (email, name, password), emergency contacts, health notes, care sheets/goals/
  risks/handovers, visit notes and check-in GPS, location history, photos and documents,
  family questions, KushLife summaries.
* Consent history and the audit log are kept as proof of what was agreed and done.

Every consent, export and delete action is written to ``audit_logs``.

Household erasure — the decision for every table that points at a client (``elders.id``):

KEEP (financial / statutory, 8 years; client row itself is anonymised):
  orders, tax_invoices, invoice_counters, family_wallets, wallet_transactions,
  products, coupons (catalogue rows; elder_id is only a scope).
KEEP as proof, anonymised:
  privacy_consents (consented_by_name / relationship blanked), privacy_data_requests,
  audit_logs, care_incident_reports (kind/severity/dates kept; narrative, location,
  injury, witnesses, notes, follow-ups blanked), care_incidents (notes/details nulled),
  care_incident_events (recipient/detail nulled), care_incident_partner_links
  (partner email/phone nulled), care_jobs (notes, report, check-in GPS cleared),
  visits (notes, GPS cleared), family_questions (body, reply, names, call window
  cleared), visit_ratings (comment blanked, score kept), nps_responses (reason blanked,
  score kept), caregiver_location_events (coordinates zeroed — they locate the home),
  attendance_alerts (message/recipient blanked), care_series (tasks blanked),
  elder_prospects (converted prospect: name/contact anonymised), iot_hubs/iot_devices
  (hardware; notes cleared), home_safety_assessments (payload/history/versions replaced,
  elder link kept; photos and documents deleted).
KEEP unchanged (no personal content; workforce history):
  assignments, matches, match_runs, placement_history, attendance_records.
ERASE (rows deleted, stored files removed through the storage backend):
  documents (client + converted-prospect photos and files), visit_voice_notes (+ audio),
  kushlife_monthly_letters, kushlife_weekly_summaries, family_contacts, client_sheets,
  care_goals, client_risks, handover_notes, elder_locations, care_job_live_locations,
  home_safety_ai_jobs, home_safety_vision_analyses (via documents),
  recommendation_conversations/messages, family_elder_links.
users: family logins are unlinked and anonymised (``_anonymise_user``).
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import secrets
import zipfile
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.csv_safe import csv_safe
from app.core.security import hash_password
from app.livewell.brand import with_brand
from app.livewell.family_elder_access import (
    is_primary_member,
    list_linked_elders,
    links_for_elder,
    unlink_family_user,
)
from app.models.elder import Elder
from app.models.family_elder_link import FamilyElderLink
from app.models.privacy import PrivacyConsent, PrivacyDataRequest
from app.models.user import User
from app.services.audit_service import AuditService

NOTICE_VERSION = "2026-10-11"

# care_delivery cannot be refused while using the service (ask to delete instead);
# marketing is a separate opt-in and OFF unless ticked.
PURPOSES: list[dict] = [
    {"key": "care_delivery", "label": "Care delivery", "required": True, "default": True,
     "text": "Use your and your family member's names, phone, address and visit records to plan, deliver and bill care."},
    {"key": "health_data", "label": "Health information", "required": False, "default": False,
     "text": "Record health conditions, allergies, mobility and wellbeing checks so caregivers can look after them safely."},
    {"key": "location_sharing", "label": "Location during visits", "required": False, "default": False,
     "text": "Record where a caregiver checked in, and show you the caregiver's position while they are on the way."},
    {"key": "marketing", "label": "News and offers", "required": False, "default": False,
     "text": "Occasional news, tips and offers by email, SMS or WhatsApp. Off unless you turn it on."},
]
ELDER_PURPOSE_KEYS = ("care_delivery", "health_data", "location_sharing")
PURPOSE_KEYS = tuple(p["key"] for p in PURPOSES)

# Placeholder grievance officer = the founder's public contact (frontend/lib/marketing/founder.ts).
# Override per agency with tenant.workflow_config["grievance_officer"] = {name, email, phone}.
DEFAULT_GRIEVANCE_OFFICER = {
    "name": "Krish Posa",
    "role": "Grievance Officer (Founder)",
    "email": "contact@kushalaya.com",
    "phone": "+91 83095 00488",
    "response_days": 30,
}

NOTICE_SECTIONS: list[dict] = [
    {"heading": "Who we are",
     "body": "LiveWell360 provides home safety assessments and in-home elder care across India. "
             "We are the Data Fiduciary for the personal data in this app."},
    {"heading": "What we collect",
     "body": "Your name, email and phone; your family member's name, age, address, phone and emergency contacts; "
             "health notes, allergies and mobility; visit times, notes and photos; payments and receipts; "
             "and, during a visit, where the caregiver checked in."},
    {"heading": "Why we use it",
     "body": "To deliver and bill care, keep your family member safe, tell you what happened on each visit, and — "
             "only if you say yes — send you news and offers. We never sell your data."},
    {"heading": "Who sees it",
     "body": "Our care team (managers and the caregivers assigned to you), and service providers we need to run "
             "the service (hosting, payments, SMS and email), under contract. In an emergency we may share what "
             "is needed with hospitals, ambulance or police."},
    {"heading": "How long we keep it",
     "body": "While you use the service. If you ask us to delete your account, we erase or anonymise your personal "
             "data within 30 days, except invoices, receipts and payment records, which the law requires us to keep "
             "for 8 years (with names and contact details removed). Backups roll off within 8 weeks."},
    {"heading": "Your rights",
     "body": "You can see and download your data, correct it, withdraw any optional consent, ask us to delete it, "
             "and nominate someone to act for you. Withdrawing consent does not affect what was done before."},
    {"heading": "Complaints",
     "body": "Contact our Grievance Officer (details below). If you are not satisfied, you may complain to the "
             "Data Protection Board of India."},
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def grievance_officer(db: Session, tenant_id: int | None) -> dict:
    officer = dict(DEFAULT_GRIEVANCE_OFFICER)
    if tenant_id:
        from app.models.tenant import Tenant

        tenant = db.get(Tenant, tenant_id)
        override = ((getattr(tenant, "workflow_config", None) or {}).get("grievance_officer") or {}) if tenant else {}
        officer.update({k: v for k, v in override.items() if v})
    return officer


def notice_payload(db: Session, tenant_id: int | None = None) -> dict:
    return {
        "version": NOTICE_VERSION,
        "sections": [{"heading": s["heading"], "body": with_brand(s["body"])} for s in NOTICE_SECTIONS],
        "purposes": PURPOSES,
        "grievance_officer": grievance_officer(db, tenant_id),
    }


def _audit(db: Session, user: User | None, *, tenant_id: int, entity_type: str, entity_id: int,
           action: str, new_value: dict | None = None) -> None:
    AuditService.log(
        db,
        tenant_id=tenant_id,
        user_id=user.id if user else None,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        new_value=new_value,
    )


# ---------------------------------------------------------------------------- consent


def _latest(db: Session, *, user_id: int | None = None, subject: str, elder_id: int | None = None):
    q = db.query(PrivacyConsent).filter(PrivacyConsent.subject == subject)
    if subject == "family":
        q = q.filter(PrivacyConsent.user_id == user_id)
    else:
        q = q.filter(PrivacyConsent.elder_id == elder_id)
    return q.order_by(PrivacyConsent.created_at.desc(), PrivacyConsent.id.desc()).first()


def _consent_dict(row: PrivacyConsent | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": row.id,
        "subject": row.subject,
        "elder_id": row.elder_id,
        "notice_version": row.notice_version,
        "purposes": row.purposes or {},
        "consented_by_name": row.consented_by_name,
        "relationship": row.relationship,
        "method": row.method,
        "created_at": _iso(row.created_at),
        "current": row.notice_version == NOTICE_VERSION and not row.withdrawn,
    }


def consent_status(db: Session, user: User) -> dict:
    mine = _latest(db, user_id=user.id, subject="family")
    elders = []
    for elder in list_linked_elders(db, user):
        row = _latest(db, subject="elder", elder_id=elder.id)
        elders.append({
            "elder_id": elder.id,
            "name": f"{elder.first_name} {elder.last_name}".strip(),
            "consent": _consent_dict(row),
            "needs_consent": not (row and row.notice_version == NOTICE_VERSION and not row.withdrawn),
        })
    needs_mine = not (mine and mine.notice_version == NOTICE_VERSION and not mine.withdrawn)
    return {
        "notice_version": NOTICE_VERSION,
        "needs_consent": needs_mine or any(e["needs_consent"] for e in elders),
        "consent": _consent_dict(mine),
        "elders": elders,
        "pending_delete_request": _pending_request_dict(db, user),
    }


def _clean_purposes(raw: dict | None, keys: tuple[str, ...]) -> dict:
    raw = raw or {}
    out = {}
    for p in PURPOSES:
        if p["key"] not in keys:
            continue
        # Optional purposes need a clear tick (DPDP): a missing key means "no".
        val = raw.get(p["key"], p["required"])
        out[p["key"]] = bool(val)
    if not out.get("care_delivery"):
        raise HTTPException(
            status_code=400,
            detail="Care delivery consent is needed to use the service. To stop, ask us to delete your account.",
        )
    return out


def record_consent(db: Session, user: User, payload: dict) -> dict:
    purposes = _clean_purposes(payload.get("purposes"), PURPOSE_KEYS)
    name = str(payload.get("consented_by_name") or f"{user.first_name} {user.last_name}").strip()[:200]
    row = PrivacyConsent(
        tenant_id=user.tenant_id,
        user_id=user.id,
        subject="family",
        notice_version=NOTICE_VERSION,
        purposes=purposes,
        consented_by_name=name,
        relationship="self",
        method="family_portal",
        created_at=utcnow(),
    )
    db.add(row)
    db.flush()
    _audit(db, user, tenant_id=user.tenant_id, entity_type="privacy_consent", entity_id=row.id,
           action="privacy.consent", new_value={"subject": "family", "version": NOTICE_VERSION, "purposes": purposes})

    linked = {e.id: e for e in list_linked_elders(db, user)}
    for item in payload.get("elders") or []:
        elder = linked.get(int(item.get("elder_id") or 0))
        if elder is None:
            raise HTTPException(status_code=404, detail="Client not found")
        ep = _clean_purposes(item.get("purposes"), ELDER_PURPOSE_KEYS)
        erow = PrivacyConsent(
            tenant_id=elder.tenant_id,
            user_id=user.id,
            subject="elder",
            elder_id=elder.id,
            notice_version=NOTICE_VERSION,
            purposes=ep,
            consented_by_name=str(item.get("consented_by_name") or name).strip()[:200],
            relationship=(str(item.get("relationship") or "").strip()[:64] or None),
            method="family_portal",
            created_at=utcnow(),
        )
        db.add(erow)
        db.flush()
        _audit(db, user, tenant_id=elder.tenant_id, entity_type="privacy_consent", entity_id=erow.id,
               action="privacy.consent",
               new_value={"subject": "elder", "elder_id": elder.id, "version": NOTICE_VERSION, "purposes": ep,
                          "consented_by": erow.consented_by_name, "relationship": erow.relationship})
    db.commit()
    return consent_status(db, user)


def marketing_opted_in(db: Session, user: User) -> bool:
    row = _latest(db, user_id=user.id, subject="family")
    return bool(row and not row.withdrawn and (row.purposes or {}).get("marketing"))


# ---------------------------------------------------------------------------- export

# Never exported: other households, staff-only notes, credentials, keys, cost/margin.
_STAFF_KEY = re.compile(r"(staff|internal|manager|secret|token|password|api_?key|mqtt|hub|cost|margin|note_for_team)", re.I)


def _strip_staff(value):
    if isinstance(value, dict):
        return {k: _strip_staff(v) for k, v in value.items() if not _STAFF_KEY.search(str(k))}
    if isinstance(value, list):
        return [_strip_staff(v) for v in value]
    return value


def _rows(db: Session, table: str, cols: list[str], where: str, params: dict, order: str = "id") -> list[dict]:
    insp = inspect(db.get_bind())
    if not insp.has_table(table):
        return []
    have = {c["name"] for c in insp.get_columns(table)}
    use = [c for c in cols if c in have]
    if not use:
        return []
    sql = f'SELECT {", ".join(chr(34) + c + chr(34) for c in use)} FROM "{table}" WHERE {where} ORDER BY {order}'
    out = []
    for r in db.execute(text(sql), params).mappings():
        row = {}
        for k, v in r.items():
            if isinstance(v, str) and v[:1] in "[{":
                try:
                    v = json.loads(v)
                except ValueError:
                    pass
            row[k] = _strip_staff(v) if isinstance(v, (dict, list)) else _iso(v) if isinstance(v, (datetime, date)) else v
        out.append(row)
    return out


def build_export(db: Session, user: User) -> dict:
    from app.livewell.document_types import FAMILY_UPLOAD_TYPE_CODES, HOME_SAFETY_SIGNED_DOC, SIGNED_DOC_FORM_CODES

    elders = list_linked_elders(db, user)
    data: dict = {
        "generated_at": utcnow().isoformat(),
        "notice_version": NOTICE_VERSION,
        "account": {
            "id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name,
            "relationship": user.portal_relationship, "status": user.status,
        },
        "consents": [
            _consent_dict(c) for c in db.query(PrivacyConsent)
            .filter(PrivacyConsent.user_id == user.id).order_by(PrivacyConsent.id).all()
        ],
        "clients": [],
        "family_contacts": [],
        "questions": [],
        "visits": [],
        "orders": [],
        "wallet_transactions": [],
        "alerts": [],
        "documents": [],
        "tax_invoices": [],
        "visit_ratings": [],
        "nps_responses": [],
        "monthly_letters": [],
        "voice_notes": [],
    }
    doc_types = list(set(SIGNED_DOC_FORM_CODES) | {HOME_SAFETY_SIGNED_DOC} | set(FAMILY_UPLOAD_TYPE_CODES))
    for elder in elders:
        p = {"eid": elder.id, "tid": elder.tenant_id}
        w = "elder_id = :eid AND tenant_id = :tid"
        data["clients"].append({
            "id": elder.id, "first_name": elder.first_name, "last_name": elder.last_name,
            "date_of_birth": _iso(elder.date_of_birth), "gender": elder.gender, "phone": elder.phone,
            "address": elder.address, "emergency_contact_name": elder.emergency_contact_name,
            "emergency_contact_phone": elder.emergency_contact_phone,
            "medical_conditions": elder.medical_conditions, "allergies": elder.allergies,
            "mobility_status": elder.mobility_status, "care_level": elder.care_level,
            "status": elder.status, "details": _strip_staff(dict(elder.custom_attributes or {})),
            "consents": [
                _consent_dict(c) for c in db.query(PrivacyConsent)
                .filter(PrivacyConsent.subject == "elder", PrivacyConsent.elder_id == elder.id)
                .order_by(PrivacyConsent.id).all()
            ],
        })
        # Only the requester's own contact details; other members appear by name only.
        up = dict(p, uid=user.id)
        data["family_contacts"] += _rows(db, "family_contacts",
                                         ["id", "elder_id", "name", "email", "phone", "channel", "level"],
                                         w + " AND user_id = :uid", up)
        data["family_contacts"] += _rows(db, "family_contacts", ["elder_id", "name"],
                                         w + " AND (user_id IS NULL OR user_id <> :uid)", up)
        # Only the requester's own questions (and staff replies to them).
        data["questions"] += _rows(db, "family_questions",
                                   ["id", "elder_id", "kind", "body", "call_window", "status", "reply", "replied_at",
                                    "created_at"], w + " AND asker_user_id = :uid", up)
        data["tax_invoices"] += _rows(db, "tax_invoices",
                                      ["id", "elder_id", "kind", "doc_type", "number", "issued_at", "source_type",
                                       "customer", "place_of_supply", "lines", "gross_paise", "discount_paise",
                                       "taxable_paise", "cgst_paise", "sgst_paise", "igst_paise", "total_paise"], w, p)
        for inv in data["tax_invoices"]:
            if inv.get("elder_id") == elder.id and "pdf_url" not in inv:
                inv["pdf_url"] = f"/api/v1/home-safety/family/invoices/{inv['id']}/pdf"
        data["visit_ratings"] += _rows(db, "visit_ratings",
                                       ["id", "elder_id", "care_job_id", "rating", "comment", "created_at"],
                                       w + " AND user_id = :uid", up)
        data["nps_responses"] += _rows(db, "nps_responses",
                                       ["id", "elder_id", "score", "reason", "created_at"],
                                       w + " AND user_id = :uid", up)
        data["monthly_letters"] += _rows(db, "kushlife_monthly_letters",
                                         ["id", "elder_id", "month_start", "text", "next_plan", "approved_at",
                                          "sent_at"], w + " AND status = 'approved'", p)
        voice = _rows(db, "visit_voice_notes",
                      ["id", "elder_id", "care_job_id", "mime_type", "size_bytes", "duration_s", "shared_at",
                       "created_at"], w + " AND share_with_family = :yes", dict(p, yes=True))
        for v in voice:
            v["download_url"] = f"/api/v1/home-safety/family/voice-notes/{v['id']}/audio"
        data["voice_notes"] += voice
        data["visits"] += _rows(db, "care_jobs",
                                ["id", "elder_id", "kind", "title", "status", "scheduled_at", "duration_minutes",
                                 "started_at", "checked_in_at", "completed_at"], w, p)
        data["orders"] += _rows(db, "orders",
                                ["id", "elder_id", "status", "lines", "subtotal_paise", "discount_paise",
                                 "coupon_code", "gst_paise", "total_paise", "paid_paise", "paid_at", "family_note",
                                 "quoted_at", "created_at"], w, p)
        data["alerts"] += _rows(db, "care_incidents",
                                ["id", "elder_id", "kind", "severity", "status", "opened_at", "acknowledged_at",
                                 "resolved_at", "outcome", "resolved_by_label"], w, p)
        data["wallet_transactions"] += _rows(
            db, "wallet_transactions",
            ["public_id", "kind", "amount_minor", "balance_after_minor", "currency", "status",
             "reference_type", "reference_id", "gateway", "gateway_payment_id", "created_at"],
            "tenant_id = :tid AND wallet_id IN (SELECT id FROM family_wallets WHERE elder_id = :eid)", p)
        if doc_types:
            marks = ", ".join(f":d{i}" for i in range(len(doc_types)))
            dp = dict(p, **{f"d{i}": t for i, t in enumerate(doc_types)})
            data["documents"] += _rows(
                db, "documents",
                ["id", "entity_id", "document_type", "document_name", "file_name", "mime_type",
                 "file_size_bytes", "uploaded_at"],
                f"entity_type = 'elder' AND entity_id = :eid AND tenant_id = :tid AND document_type IN ({marks})",
                dp)
    return data


def _csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    w = csv.DictWriter(buf, fieldnames=keys or ["empty"])
    w.writeheader()
    for r in rows:
        w.writerow({k: csv_safe(json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                    for k, v in r.items()})
    return buf.getvalue()


def export_zip(db: Session, user: User) -> tuple[bytes, str]:
    data = build_export(db, user)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("my-data.json", json.dumps(data, ensure_ascii=False, indent=2, default=str))
        zf.writestr("account.csv", _csv([data["account"]]))
        for key in ("consents", "clients", "family_contacts", "questions", "visits", "orders",
                    "wallet_transactions", "alerts", "documents", "tax_invoices", "visit_ratings",
                    "nps_responses", "monthly_letters", "voice_notes"):
            zf.writestr(f"{key}.csv", _csv(data[key]))
        zf.writestr("README.txt",
                    with_brand("Your data from LiveWell360") + ", as of " + data["generated_at"] + ".\n"
                    "my-data.json has everything; the CSV files are the same data as spreadsheets.\n"
                    "Money is in paise (100 paise = 1 rupee). Document files themselves can be downloaded "
                    "from the Documents page.\n")
    _audit(db, user, tenant_id=user.tenant_id, entity_type="user", entity_id=user.id, action="privacy.export",
           new_value={"clients": [c["id"] for c in data["clients"]]})
    db.commit()
    return buf.getvalue(), f"my-data-{date.today().isoformat()}.zip"


# ---------------------------------------------------------------------------- delete


def _elder_name(row: PrivacyDataRequest) -> str | None:
    from sqlalchemy.orm import object_session

    sess = object_session(row)
    elder = sess.get(Elder, row.elder_id) if sess is not None and row.elder_id else None
    return f"{elder.first_name} {elder.last_name}".strip() if elder else None


def _request_dict(row: PrivacyDataRequest) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "scope": row.scope,
        "status": row.status,
        "elder_id": row.elder_id,
        "elder_name": _elder_name(row),
        "user_id": row.user_id,
        "requester": row.requester_label,
        "reason": row.reason,
        "review_note": row.review_note,
        "created_at": _iso(row.created_at),
        "reviewed_at": _iso(row.reviewed_at),
        "completed_at": _iso(row.completed_at),
        "result": row.result,
    }


def _pending_request_dict(db: Session, user: User) -> dict | None:
    row = (
        db.query(PrivacyDataRequest)
        .filter(PrivacyDataRequest.user_id == user.id, PrivacyDataRequest.status == "PENDING")
        .first()
    )
    return _request_dict(row) if row else None


def request_delete(db: Session, user: User, *, scope: str = "account", reason: str | None = None) -> dict:
    scope = "household" if scope == "household" else "account"
    if _pending_request_dict(db, user):
        raise HTTPException(status_code=409, detail="You already have a delete request waiting for review.")
    elder = db.get(Elder, user.elder_id) if user.elder_id else None
    if scope == "household":
        if elder is None or not is_primary_member(db, user, elder):
            raise HTTPException(status_code=403, detail="Only the main family member can ask to delete the client's records.")
    row = PrivacyDataRequest(
        tenant_id=user.tenant_id,
        user_id=user.id,
        elder_id=elder.id if elder else None,
        kind="DELETE",
        scope=scope,
        status="PENDING",
        requester_label=f"{user.first_name} {user.last_name} <{user.email}>"[:200],
        reason=(reason or "").strip()[:2000] or None,
    )
    db.add(row)
    db.flush()
    _audit(db, user, tenant_id=user.tenant_id, entity_type="privacy_request", entity_id=row.id,
           action="privacy.delete_requested", new_value={"scope": scope, "elder_id": row.elder_id})
    db.commit()
    db.refresh(row)
    return _request_dict(row)


def _admin_tenant(admin: User) -> int | None:
    from app.core.rbac import resolve_tenant_id

    return resolve_tenant_id(admin)


def list_requests(db: Session, admin: User, status: str | None = None) -> list[dict]:
    q = db.query(PrivacyDataRequest)
    tid = _admin_tenant(admin)
    if tid is not None:
        q = q.filter(PrivacyDataRequest.tenant_id == tid)
    if status:
        q = q.filter(PrivacyDataRequest.status == status.upper())
    return [_request_dict(r) for r in q.order_by(PrivacyDataRequest.id.desc()).limit(200).all()]


def _get_request(db: Session, admin: User, request_id: int) -> PrivacyDataRequest:
    row = db.get(PrivacyDataRequest, request_id)
    tid = _admin_tenant(admin)
    if row is None or (tid is not None and row.tenant_id != tid):
        raise HTTPException(status_code=404, detail="Request not found")
    if row.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"Request is already {row.status.lower()}")
    return row


def reject_request(db: Session, admin: User, request_id: int, note: str | None) -> dict:
    row = _get_request(db, admin, request_id)
    row.status = "REJECTED"
    row.review_note = (note or "").strip()[:2000] or None
    row.reviewed_by_user_id = admin.id
    row.reviewed_at = utcnow()
    _audit(db, admin, tenant_id=row.tenant_id, entity_type="privacy_request", entity_id=row.id,
           action="privacy.delete_rejected", new_value={"note": row.review_note})
    db.commit()
    return _request_dict(row)


def _exec(db: Session, table: str, sql: str, params: dict) -> int:
    if not inspect(db.get_bind()).has_table(table):
        return 0
    try:
        with db.begin_nested():
            return db.execute(text(sql), params).rowcount or 0
    except (OperationalError, ProgrammingError):  # column not on this server's schema
        return 0


def _anonymise_user(db: Session, member: User) -> None:
    for link in db.query(FamilyElderLink).filter(FamilyElderLink.user_id == member.id).all():
        elder = db.get(Elder, link.elder_id)
        if elder is not None:
            unlink_family_user(db, member, elder, commit=False)
    _exec(db, "family_contacts", 'DELETE FROM "family_contacts" WHERE user_id = :uid', {"uid": member.id})
    # The consent record stays as proof; only the typed name is anonymised.
    _exec(db, "privacy_consents", "UPDATE privacy_consents SET consented_by_name = :n, relationship = NULL "
          "WHERE user_id = :uid", {"uid": member.id, "n": f"Deleted user #{member.id}"})
    member.email = f"deleted-user-{member.id}@deleted.invalid"
    member.first_name = "Deleted"
    member.last_name = "user"
    member.password_hash = hash_password(secrets.token_urlsafe(32))
    member.elder_id = None
    member.status = "INACTIVE"
    if hasattr(member, "portal_relationship"):
        member.portal_relationship = None


def _erase_voice_notes(db: Session, elder_id: int) -> int:
    """Delete the client's visit voice notes and their audio files."""
    if not inspect(db.get_bind()).has_table("visit_voice_notes"):
        return 0
    from app.core.storage import get_storage

    keys = [r[0] for r in db.execute(text("SELECT storage_key FROM visit_voice_notes WHERE elder_id = :eid"),
                                     {"eid": elder_id}).fetchall()]
    storage = get_storage()
    for key in keys:
        try:
            storage.delete(key)
        except Exception:  # a missing file must not block the erasure
            pass
    return _exec(db, "visit_voice_notes", "DELETE FROM visit_voice_notes WHERE elder_id = :eid", {"eid": elder_id})


def _erase_household(db: Session, elder: Elder, request_id: int) -> dict:
    """Erase/anonymise the client's personal data. Financial tables are NOT touched."""
    from app.models.elder_prospect import ElderProspect
    from app.services.customer_delete_service import _delete_documents, _release_document_refs

    p = {"eid": elder.id}
    counts: dict = {}
    has = inspect(db.get_bind()).has_table
    _release_document_refs(db, entity_type="elder", entity_id=elder.id)
    counts["documents"] = _delete_documents(db, entity_type="elder", entity_id=elder.id)
    # Photos taken before the client converted sit on the prospect record.
    for pr in db.query(ElderProspect).filter(ElderProspect.converted_elder_id == elder.id).all():
        _release_document_refs(db, entity_type="elder_prospect", entity_id=pr.id)
        counts["documents"] += _delete_documents(db, entity_type="elder_prospect", entity_id=pr.id)
    counts["visit_voice_notes"] = _erase_voice_notes(db, elder.id)
    if has("care_jobs"):
        counts["care_job_live_locations"] = _exec(
            db, "care_job_live_locations",
            "DELETE FROM care_job_live_locations WHERE job_id IN (SELECT id FROM care_jobs WHERE elder_id = :eid)", p)
    if has("recommendation_conversations"):
        _exec(db, "recommendation_messages",
              "DELETE FROM recommendation_messages WHERE conversation_id IN "
              "(SELECT id FROM recommendation_conversations WHERE elder_id = :eid)", p)
        counts["recommendation_conversations"] = _exec(
            db, "recommendation_conversations", "DELETE FROM recommendation_conversations WHERE elder_id = :eid", p)
    for table in ("family_contacts", "client_sheets", "care_goals", "client_risks", "handover_notes",
                  "elder_locations", "kushlife_weekly_summaries", "kushlife_monthly_letters",
                  "home_safety_ai_jobs"):
        counts[table] = _exec(db, table, f'DELETE FROM "{table}" WHERE elder_id = :eid', p)
    counts["family_questions"] = _exec(
        db, "family_questions", "UPDATE family_questions SET body = NULL, reply = NULL, replied_by_name = NULL, "
        "call_window = NULL, visit_label = NULL WHERE elder_id = :eid", p)
    counts["visit_ratings"] = _exec(db, "visit_ratings", "UPDATE visit_ratings SET comment = '' WHERE elder_id = :eid", p)
    counts["nps_responses"] = _exec(db, "nps_responses", "UPDATE nps_responses SET reason = '' WHERE elder_id = :eid", p)
    counts["care_incident_reports"] = _exec(
        db, "care_incident_reports", "UPDATE care_incident_reports SET location = '', what_happened = '[erased]', "
        "injury = '', action_taken = '', witnesses = '', staff_notes = '', family_summary = '', outcome = '', "
        "follow_ups = NULL WHERE elder_id = :eid", p)
    if has("care_incidents"):
        sub = "(SELECT id FROM care_incidents WHERE elder_id = :eid)"
        _exec(db, "care_incident_events",
              f"UPDATE care_incident_events SET recipient = NULL, detail = NULL WHERE incident_id IN {sub}", p)
        _exec(db, "care_incident_partner_links", "UPDATE care_incident_partner_links SET partner_email = NULL, "
              f"partner_phone = NULL WHERE incident_id IN {sub}", p)
    counts["privacy_consents"] = _exec(
        db, "privacy_consents", "UPDATE privacy_consents SET consented_by_name = :n, relationship = NULL "
        "WHERE elder_id = :eid", dict(p, n=f"Deleted client #{elder.id}"))
    counts["caregiver_location_events"] = _exec(
        db, "caregiver_location_events",
        "UPDATE caregiver_location_events SET latitude = 0, longitude = 0 WHERE elder_id = :eid", p)
    _exec(db, "attendance_alerts", "UPDATE attendance_alerts SET message = '', recipient = '' WHERE elder_id = :eid", p)
    _exec(db, "care_series", "UPDATE care_series SET tasks = '' WHERE elder_id = :eid", p)
    _exec(db, "iot_hubs", "UPDATE iot_hubs SET notes = NULL WHERE elder_id = :eid", p)
    _exec(db, "iot_devices", "UPDATE iot_devices SET notes = NULL WHERE elder_id = :eid", p)
    counts["care_jobs"] = _exec(
        db, "care_jobs", "UPDATE care_jobs SET staff_note = '', caregiver_note = '', location = '', report = NULL, "
        "checkin_lat = NULL, checkin_lng = NULL WHERE elder_id = :eid", p)
    # Separate, so a server without these newer columns still clears the rest.
    _exec(db, "care_jobs", "UPDATE care_jobs SET checkin_accuracy_m = NULL, checkout_lat = NULL, "
          "checkout_lng = NULL, checkout_accuracy_m = NULL WHERE elder_id = :eid", p)
    # "Visit away from home" notices name the client.
    _exec(db, "staff_alerts", "UPDATE staff_alerts SET title = '', body = '' WHERE elder_id = :eid", p)
    counts["visits"] = _exec(
        db, "visits", "UPDATE visits SET visit_notes = NULL, gps_latitude = NULL, gps_longitude = NULL "
        "WHERE elder_id = :eid", p)
    counts["care_incidents"] = _exec(
        db, "care_incidents", "UPDATE care_incidents SET note = NULL, resolution_note = NULL, details = NULL "
        "WHERE elder_id = :eid", p)
    if has("home_safety_assessments"):
        # Keep the record (it may back a paid assessment / invoice) but drop everything
        # personal in it; its photos went with the client's documents above.
        from app.models.home_safety_assessment import HomeSafetyAssessmentRecord

        rows = db.query(HomeSafetyAssessmentRecord).filter(HomeSafetyAssessmentRecord.elder_id == elder.id).all()
        for a in rows:
            a.payload = {"erased": True, "erased_at": utcnow().isoformat(), "erasure_request_id": request_id}
            a.versions = []
            a.history = []
        counts["home_safety_assessments"] = len(rows)
    for pr in db.query(ElderProspect).filter(ElderProspect.converted_elder_id == elder.id).all():
        pr.first_name, pr.last_name = "Deleted", f"client #{elder.id}"
        pr.phone = pr.email = pr.address = pr.notes = None
    for member_link in links_for_elder(db, elder.id):
        member = db.get(User, member_link.user_id)
        if member is not None:
            unlink_family_user(db, member, elder, commit=False)
    for member in db.query(User).filter(User.elder_id == elder.id).all():
        member.elder_id = None

    elder.first_name = "Deleted"
    elder.last_name = f"client #{elder.id}"
    elder.date_of_birth = None
    elder.phone = None
    elder.address = None
    elder.emergency_contact_name = None
    elder.emergency_contact_phone = None
    elder.medical_conditions = None
    elder.allergies = None
    elder.mobility_status = None
    elder.custom_attributes = {"erased_at": utcnow().isoformat(), "erasure_request_id": request_id}
    elder.status = "INACTIVE"
    return counts


def approve_request(db: Session, admin: User, request_id: int, note: str | None = None) -> dict:
    row = _get_request(db, admin, request_id)
    member = db.get(User, row.user_id) if row.user_id else None
    result: dict = {"scope": row.scope, "kept": "orders, tax invoices, wallet ledger and payments (8 years)"}
    if row.scope == "household" and row.elder_id:
        elder = db.get(Elder, row.elder_id)
        if elder is not None:
            result["erased"] = _erase_household(db, elder, row.id)
            result["elder_id"] = elder.id
    if member is not None:
        _anonymise_user(db, member)
        result["account_anonymised"] = member.id
    row.status = "COMPLETED"
    row.review_note = (note or "").strip()[:2000] or None
    row.reviewed_by_user_id = admin.id
    row.reviewed_at = row.completed_at = utcnow()
    row.requester_label = f"Deleted user #{row.user_id}"
    row.reason = None
    row.result = result
    _audit(db, admin, tenant_id=row.tenant_id, entity_type="privacy_request", entity_id=row.id,
           action="privacy.delete_approved", new_value=result)
    db.commit()
    return _request_dict(row)


# ---------------------------------------------------------------------------- backup status

DEFAULT_BACKUP_STATUS_FILE = "/var/lib/safehomeops/backup/status.json"


def backup_status() -> dict:
    """Read the status file scripts/backup/backup-db.sh writes after every run."""
    path = os.environ.get("BACKUP_STATUS_FILE") or DEFAULT_BACKUP_STATUS_FILE
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {"configured": False, "ok": False, "message": "No backup has run on this server yet."}
    except (OSError, ValueError):
        return {"configured": True, "ok": False, "message": "Backup status file is unreadable."}
    out = {k: data.get(k) for k in (
        "last_attempt_at", "last_success_at", "last_status", "db_bytes", "uploads_bytes", "remote",
        "restore_test_at", "restore_test_status", "restore_test_detail", "message")}
    out["configured"] = True
    ok = data.get("last_status") == "ok"
    stale = True
    try:
        last = datetime.fromisoformat(str(data.get("last_success_at")).replace("Z", "+00:00"))
        stale = utcnow() - last > timedelta(hours=36)
    except (TypeError, ValueError):
        pass
    out["stale"] = stale
    out["ok"] = ok and not stale
    return out
