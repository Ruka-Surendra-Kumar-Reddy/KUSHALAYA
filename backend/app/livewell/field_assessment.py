"""Assessment done by a caregiver in the field app, for an assigned assessment job.

The caregiver gets the agency's question set (the effective rubric), answers one
question at a time, and the answers are saved through the normal assessment
service — so scoring, the Independence Score™ and the family publish are the
same as an assessment made in the ops portal.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.responses import raise_bad_request
from app.livewell.assessment_service import HomeSafetyAssessmentService
from app.livewell.care_jobs import _caregiver_job, serialize
from app.livewell.family_elder_link import republish_latest_assessment_for_elder
from app.livewell.scoring import effective_rubric
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.home_safety_assessment import HomeSafetyAssessmentRecord
from app.models.tenant import Tenant
from app.models.user import User
from app.livewell.brand import safety_score_name

RATINGS = {"excellent", "acceptable", "unsafe", "na"}


def _questions(db: Session, tenant_id: int, answered: dict | None = None) -> list[dict]:
    """Questions for the caregiver app. Hidden ones are left out unless this
    assessment already answered them."""
    tenant = db.get(Tenant, tenant_id)
    categories, _ = effective_rubric(tenant.workflow_config if tenant else None)
    answered = answered or {}
    out = []
    for c in categories:
        items = [
            {
                "id": i["id"],
                "label": i.get("label") or i["id"],
                "group": i.get("group") or "",
                "input_type": i.get("inputType") or "rating",
                "hint": i.get("help") or i.get("hint") or i.get("description") or "",
                "visit_question": bool(i.get("visitQuestion")),
                # Admin-set wording and answer options (rubric editor); empty = app defaults.
                "ask": i.get("ask") or "",
                "options": i.get("options") or [],
            }
            for i in c.get("items", [])
            if i.get("id") and (not i.get("hidden") or answered.get(i["id"]))
        ]
        if items:
            out.append({"id": c.get("id"), "title": str(c.get("title") or "").lstrip("0123456789. "), "items": items})
    return out


SKIP_KEY = "assessment_skip"


def home_skips(elder: Elder | None) -> list[str]:
    """Questions marked "Not applicable" for this home in its last completed assessment."""
    attrs = (elder.custom_attributes if elder and isinstance(elder.custom_attributes, dict) else None) or {}
    return [str(x) for x in attrs.get(SKIP_KEY) or []]


def _remember_skips(db: Session, elder: Elder, ratings: dict) -> None:
    from sqlalchemy.orm.attributes import flag_modified

    attrs = dict(elder.custom_attributes or {})
    attrs[SKIP_KEY] = sorted(k for k, v in ratings.items() if v == "na")
    elder.custom_attributes = attrs
    flag_modified(elder, "custom_attributes")


def _assessment_id(job_id: int) -> str:
    return f"field-job-{job_id}"


def load_for_job(db: Session, user: User, job_id: int) -> dict:
    job = _caregiver_job(db, user, job_id)
    if job.kind != "assessment":
        raise_bad_request("This job is not an assessment")
    row = (
        db.query(HomeSafetyAssessmentRecord)
        .filter(HomeSafetyAssessmentRecord.assessment_id == (job.assessment_id or _assessment_id(job.id)))
        .first()
    )
    payload = (row.payload if row else None) or {}
    skip = home_skips(db.get(Elder, job.elder_id))
    ratings = payload.get("ratings") or {}
    if not row:
        # A new (re)assessment starts with last time's "doesn't apply here" answers.
        ratings = {k: "na" for k in skip}
    return {
        "job": serialize(db, job),
        "categories": _questions(db, job.tenant_id, payload.get("ratings") or {}),
        "skip_for_home": skip,
        "ratings": ratings,
        "item_notes": payload.get("itemNotes") or {},
        "answer_labels": payload.get("answerLabels") or {},
        "resident_profile": payload.get("residentProfile") or {},
        "notes": payload.get("notes") or "",
        "status": row.status if row else "new",
        "score": payload.get("independenceScore"),
        "client": client_info(db, db.get(Elder, job.elder_id), job),
    }


def _assessor_name(db: Session, job, cg, user: User) -> str:
    """Who did the assessment: the assigned care manager, else the caregiver, else whoever saves it."""
    cm = db.get(User, job.assignee_user_id) if getattr(job, "assignee_user_id", None) else None
    for p in (cm, cg, user):
        if p is not None and (p.first_name or p.last_name):
            return f"{p.first_name or ''} {p.last_name or ''}".strip()
    return ""


def save_for_job(db: Session, user: User, job_id: int, data: dict) -> dict:
    job = _caregiver_job(db, user, job_id)
    if job.kind != "assessment":
        raise_bad_request("This job is not an assessment")
    if job.status not in ("checked_in", "on_the_way", "scheduled"):
        raise_bad_request("This assessment is already closed")
    elder = db.get(Elder, job.elder_id)
    cg = db.get(Caregiver, job.caregiver_id) if job.caregiver_id else None  # office-run jobs have none
    ratings = {k: v for k, v in (data.get("ratings") or {}).items() if v in RATINGS}
    now = datetime.now(timezone.utc).isoformat()
    aid = job.assessment_id or _assessment_id(job.id)
    existing = db.query(HomeSafetyAssessmentRecord).filter(HomeSafetyAssessmentRecord.assessment_id == aid).first()
    created = ((existing.payload or {}).get("createdAt") if existing else None) or now
    complete = bool(data.get("complete"))
    if complete and not client_info(db, elder, job).get("confirmed"):
        raise_bad_request("Confirm the client's details and home location first (step 1), then submit.")
    if complete:
        # Every question needs an answer ("Not applicable" counts): an unanswered one
        # would score as a risk and could publish a misleading low score to the family.
        notes = data.get("item_notes") or {}
        missing = [
            q["label"]
            for c in _questions(db, elder.tenant_id, ratings)
            for q in c["items"]
            if not ratings.get(q["id"]) and not (q["input_type"] == "text" and str(notes.get(q["id"]) or "").strip())
        ]
        if missing:
            n = len(missing)
            raise_bad_request(
                f"{n} question{'' if n == 1 else 's'} not answered yet. Answer {'it' if n == 1 else 'them'}, "
                "or choose the last option if it doesn't apply, then submit."
            )
    payload = {
        "id": aid,
        "createdAt": created,
        "updatedAt": now,
        "completedAt": now if complete else None,
        "status": "completed" if complete else "draft",
        "clientFirstName": elder.first_name or "",
        "clientLastName": elder.last_name or "",
        "clientAddress": elder.address or "",
        "clientPhone": elder.phone or "",
        "assessorName": _assessor_name(db, job, cg, user),
        "notes": str(data.get("notes") or ""),
        "residentProfile": data.get("resident_profile") or {},
        "ratings": ratings,
        "itemNotes": {k: str(v) for k, v in (data.get("item_notes") or {}).items() if str(v).strip()},
        # The option the caregiver tapped (for the report); only for answered questions.
        "answerLabels": {
            k: str(v).strip()[:100]
            for k, v in (data.get("answer_labels") or {}).items()
            if k in ratings and str(v or "").strip()
        },
        "elderId": elder.id,
        # Photos are uploaded separately (add_photo) and kept across saves.
        "photos": list(((existing.payload or {}).get("photos") or []) if existing else []),
    }
    if complete:
        # The family's improvement plan (the office wizard builds it in the browser).
        from app.livewell.server_plan import build_family_plan

        tenant = db.get(Tenant, elder.tenant_id)
        plan = build_family_plan(payload, tenant.workflow_config if tenant else None)
        if plan:
            payload["familyImprovementPlan"] = plan
    result = HomeSafetyAssessmentService.upsert_assessment(db, user, payload)
    job.assessment_id = aid
    if complete:
        _remember_skips(db, elder, ratings)
        republish_latest_assessment_for_elder(db, tenant_id=elder.tenant_id, elder_id=elder.id, prospect_id=None)
        if job.status != "checked_in":
            job.checked_in_at = job.checked_in_at or datetime.now(timezone.utc)
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        from app.livewell.care_jobs import _notify_family, _notify_staff_done, record_location

        # Where the assessment was finished (required by the caregiver route).
        record_location(db, job, "checkout", data.get("latitude"), data.get("longitude"), data.get("accuracy"))

        score = result.get("server_score") if isinstance(result, dict) else None
        msg = (
            f"The {safety_score_name()} is {score}/100. See the report in the portal."
            if score is not None
            else "The report is ready in the portal."
        )
        _notify_family(db, elder, "Home safety assessment completed", msg, "report")
        _notify_staff_done(db, elder, "Home safety assessment completed", msg)
        from app.livewell.assessment_start import lead_assessment_done

        lead_assessment_done(db, user, elder)  # a lead's card moves to "Assessment done"
    db.commit()
    return {
        "job": serialize(db, job),
        "status": "completed" if complete else "draft",
        "score": result.get("server_score") if isinstance(result, dict) else None,
    }


def add_photo(
    db: Session,
    user: User,
    job_id: int,
    *,
    file_name: str,
    content: bytes,
    content_type: str,
    room_type: str | None,
    caption: str | None,
) -> dict:
    """A room photo taken during the field assessment (used for before/after pictures)."""
    import uuid

    from sqlalchemy.orm.attributes import flag_modified

    from app.livewell.photo_service import HomeSafetyPhotoService

    job = _caregiver_job(db, user, job_id)
    if job.kind != "assessment":
        doc = HomeSafetyPhotoService.upload(
            db,
            user,
            file_name=file_name,
            content=content,
            content_type=content_type,
            caption=caption,
            assessment_id=None,
            prospect_id=None,
            elder_id=job.elder_id,
            room_type=room_type,
        )
        report = dict(job.report or {})
        report["photo_ids"] = [*report.get("photo_ids", []), doc.id]
        job.report = report
        flag_modified(job, "report")
        db.commit()
        return {"document_id": doc.id, "room_type": room_type, "count": len(report["photo_ids"])}
    aid = job.assessment_id or _assessment_id(job.id)
    if not db.query(HomeSafetyAssessmentRecord).filter(HomeSafetyAssessmentRecord.assessment_id == aid).first():
        save_for_job(db, user, job_id, {"ratings": {}, "item_notes": {}, "resident_profile": {}})
    doc = HomeSafetyPhotoService.upload(
        db,
        user,
        file_name=file_name,
        content=content,
        content_type=content_type,
        caption=caption,
        assessment_id=aid,
        prospect_id=None,
        elder_id=job.elder_id,
        room_type=room_type,
    )
    row = db.query(HomeSafetyAssessmentRecord).filter(HomeSafetyAssessmentRecord.assessment_id == aid).first()
    payload = dict(row.payload or {})
    photos = list(payload.get("photos") or [])
    photos.append(
        {
            "id": uuid.uuid4().hex[:12],
            "caption": caption or "",
            "roomType": room_type,
            "localPreview": None,
            "documentId": doc.id,
            "uploadedAt": datetime.now(timezone.utc).isoformat(),
        }
    )
    payload["photos"] = photos
    row.payload = payload
    flag_modified(row, "payload")
    db.commit()
    return {"document_id": doc.id, "room_type": room_type, "count": len(photos)}


def suggestions_for_job(db: Session, user: User, job_id: int) -> list[dict]:
    from app.livewell.suggestions import suggestions_for_ratings

    job = _caregiver_job(db, user, job_id)
    row = (
        db.query(HomeSafetyAssessmentRecord)
        .filter(HomeSafetyAssessmentRecord.assessment_id == (job.assessment_id or _assessment_id(job.id)))
        .first()
    )
    ratings = ((row.payload or {}).get("ratings") if row else None) or {}
    return [
        {k: v for k, v in s.items() if k not in ("price_paise",)}
        for s in suggestions_for_ratings(db, job.tenant_id, ratings)
    ]


# --- Step 1 of the assessment: client details + home location ------------------

CLIENT_CONFIRMED_KEY = "assessment_client_confirmed_job"
HOME_LOCATION_KEY = "home_location"
EXTRA_FIELDS = ("email", "area", "city", "pincode", "contact_relation", "contact_email")
BENEFICIARIES_KEY = "beneficiaries"  # more people in the same home (spouse …), besides the main one
# Optional (owner, 28 Oct): date of birth (often unknown) and the beneficiary's own phone
# (many elders don't use one). The contact person's phone stays required: we call them for SOS.
REQUIRED = ("first_name", "address", "city", "pincode", "gender",
            "emergency_contact_name", "emergency_contact_phone")


def _lead_prefill(db: Session, elder: Elder, out: dict) -> None:
    """A lead's name/phone/email are the ENQUIRER's (usually the son or daughter): they
    pre-fill the contact person, not the beneficiary."""
    from app.livewell.assessment_start import lead_id_of
    from app.models.elder_prospect import ElderProspect

    lid = lead_id_of(elder)
    lead = db.get(ElderProspect, lid) if lid else None
    if lead is None or out["emergency_contact_name"] or out["emergency_contact_phone"]:
        return
    who = f"{lead.first_name or ''} {lead.last_name or ''}".strip()
    out["emergency_contact_name"] = who
    out["emergency_contact_phone"] = lead.phone or ""
    out["contact_email"] = out["contact_email"] or (lead.email or "")
    if f"{out['first_name']} {out['last_name']}".strip() == who:
        out["first_name"] = out["last_name"] = ""
    if out["phone"] and out["phone"] == (lead.phone or ""):
        out["phone"] = ""
    if out["email"] and out["email"] == (lead.email or ""):
        out["email"] = ""
    out["pincode"] = out["pincode"] or (lead.pincode or "")


def client_info(db: Session, elder: Elder | None, job) -> dict:
    """What step 1 shows: the client's details, the saved home location, whether
    anything required is missing, and whether this is a lead or a reassessment."""
    if elder is None:
        return {}
    from app.livewell.assessment_start import lead_id_of

    attrs = elder.custom_attributes if isinstance(elder.custom_attributes, dict) else {}
    out = {
        "first_name": elder.first_name or "",
        "last_name": elder.last_name or "",
        "phone": elder.phone or "",
        "gender": elder.gender or "",
        "date_of_birth": elder.date_of_birth.isoformat() if elder.date_of_birth else "",
        "address": elder.address or "",
        "emergency_contact_name": elder.emergency_contact_name or "",
        "emergency_contact_phone": elder.emergency_contact_phone or "",
        **{k: str(attrs.get(k) or "") for k in EXTRA_FIELDS},
    }
    if out["first_name"] == "Lead":
        out["first_name"] = ""
    _lead_prefill(db, elder, out)
    previous = (
        db.query(HomeSafetyAssessmentRecord.id)
        .filter(
            HomeSafetyAssessmentRecord.elder_id == elder.id,
            HomeSafetyAssessmentRecord.status == "completed",
            HomeSafetyAssessmentRecord.assessment_id != (job.assessment_id or _assessment_id(job.id)),
        )
        .first()
    )
    return {
        "details": out,
        "location": attrs.get(HOME_LOCATION_KEY) or None,
        "beneficiaries": list(attrs.get(BENEFICIARIES_KEY) or []),
        "missing": [k for k in REQUIRED if not out.get(k)],
        "is_lead": lead_id_of(elder) is not None,
        "reassessment": previous is not None,
        # Confirmed for this assessment, or nothing to confirm: every required detail and
        # a home location are already on file (e.g. continuing a draft) — then "Continue"
        # opens at the questions instead of step 1 (owner, 28 Oct).
        "confirmed": attrs.get(CLIENT_CONFIRMED_KEY) == job.id
        or (not [k for k in REQUIRED if not out.get(k)] and bool(attrs.get(HOME_LOCATION_KEY))),
    }


def save_client(db: Session, user: User, job_id: int, data: dict) -> dict:
    """Step 1 → Next: save the client's details and home location for this assessment."""
    from datetime import date

    from sqlalchemy.orm.attributes import flag_modified

    job = _caregiver_job(db, user, job_id)
    if job.kind != "assessment":
        raise_bad_request("This job is not an assessment")
    elder = db.get(Elder, job.elder_id)
    d = {k: str(v or "").strip() for k, v in (data.get("details") or {}).items()}
    missing = [k for k in REQUIRED if not d.get(k)]
    if missing:
        raise_bad_request("Fill in every required detail: " + ", ".join(m.replace("_", " ") for m in missing))
    if not d["pincode"].isdigit() or len(d["pincode"]) != 6:
        raise_bad_request("PIN code must be 6 digits")
    dob = None
    if d.get("date_of_birth"):
        try:
            dob = date.fromisoformat(d["date_of_birth"])
        except ValueError:
            raise_bad_request("Date of birth is not a valid date")
        if not (date(1900, 1, 1) <= dob <= date.today()):
            raise_bad_request("Date of birth is not a valid date")
    extra = []
    for b in (data.get("beneficiaries") or [])[:6]:
        b = {k: str((b or {}).get(k) or "").strip()[:100] for k in ("name", "gender", "date_of_birth", "relation", "phone")}
        if not any(b.values()):
            continue
        if not b["name"]:
            raise_bad_request("Each added beneficiary needs a name")
        extra.append(b)
    loc = data.get("location") or {}
    mode = loc.get("mode")
    if mode == "auto":
        try:
            lat, lng = float(loc["latitude"]), float(loc["longitude"])
        except (KeyError, TypeError, ValueError):
            raise_bad_request("Location was not detected. Try again, or enter it manually.")
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise_bad_request("Location was not detected. Try again, or enter it manually.")
        location = {"mode": "auto", "latitude": lat, "longitude": lng,
                    "accuracy": loc.get("accuracy"), "label": str(loc.get("label") or "")[:300]}
    elif mode == "manual":
        location = {"mode": "manual", "label": d["address"][:300]}
    else:
        raise_bad_request("Choose how to set the home location: auto-detect or enter manually.")
    location["at"] = datetime.now(timezone.utc).isoformat()
    location["by_user_id"] = user.id

    elder.first_name = d["first_name"][:100]
    elder.last_name = d.get("last_name", "")[:100]
    elder.phone = d.get("phone", "")[:50] or None
    elder.gender = d["gender"][:50]
    if dob is not None:
        elder.date_of_birth = dob
    elder.address = d["address"][:500]
    elder.emergency_contact_name = d["emergency_contact_name"][:200]
    elder.emergency_contact_phone = d["emergency_contact_phone"][:50]
    attrs = dict(elder.custom_attributes or {})
    for k in EXTRA_FIELDS:
        attrs[k] = d.get(k, "")[:200]
    attrs[HOME_LOCATION_KEY] = location
    attrs[BENEFICIARIES_KEY] = extra
    attrs[CLIENT_CONFIRMED_KEY] = job.id
    elder.custom_attributes = attrs
    flag_modified(elder, "custom_attributes")
    if not job.location:
        job.location = elder.address[:500]
    db.commit()
    return client_info(db, elder, job)
