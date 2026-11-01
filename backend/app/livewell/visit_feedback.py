"""Phase 5 (#100 #106): visit ratings, NPS, visit voice notes and quality numbers.

* Rating: after a visit report, each family login can rate the visit 1–5 (once).
* NPS: every 90 days a family login is asked "How likely are you to recommend Kushalaya?"
  0–10 plus a reason. Dismissing it asks again after 30 days.
* Low ratings (≤ 2) and detractors (0–6) sit in the ops Dashboard "Needs attention" for the
  client's care manager until someone marks them reviewed.
* Voice notes: ≤ 60 s recordings on a visit. Staff in the client's team can hear them; the
  family only once a manager ticks "share with family".
* Quality numbers: % visits on time, % visits with KushLife, average family rating,
  incident count — per client and for the agency (the viewer's team).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.responses import raise_bad_request, raise_conflict, raise_not_found
from app.models.care_job import CareJob
from app.models.elder import Elder
from app.models.kushlife_quality import NpsResponse, VisitRating, VisitVoiceNote
from app.models.user import User

LOW_RATING = 2
DETRACTOR_MAX = 6
NPS_EVERY_DAYS = 90
NPS_SNOOZE_DAYS = 30
ON_TIME_GRACE = timedelta(minutes=15)
VOICE_MAX_BYTES = 3 * 1024 * 1024
VOICE_MAX_SECONDS = 60
VOICE_PER_JOB = 5
VOICE_TYPES = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/x-m4a": "m4a", "audio/aac": "aac"}
_VISIT_KINDS = ("visit", "install")


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    dt = _aware(dt)
    return dt.isoformat() if dt else None


def _name(e: Elder | None) -> str:
    return f"{e.first_name or ''} {e.last_name or ''}".strip() if e else ""


def _user_name(db: Session, user_id: int | None) -> str:
    u = db.get(User, user_id) if user_id else None
    return (f"{u.first_name or ''} {u.last_name or ''}".strip() or (u.email or "")) if u else ""


def job_id_from_visit_id(visit_id: str) -> int | None:
    if visit_id.startswith("job-") and visit_id[4:].isdigit():
        return int(visit_id[4:])
    return None


# --- ratings -------------------------------------------------------------------------


def _family_job(db: Session, elder: Elder, job_id: int) -> CareJob:
    job = db.get(CareJob, job_id)
    if not job or job.elder_id != elder.id or job.status == "cancelled":
        raise_not_found("Visit not found")
    return job


def my_ratings(db: Session, user: User, job_ids: list[int]) -> dict[int, VisitRating]:
    if not job_ids:
        return {}
    rows = db.query(VisitRating).filter(VisitRating.user_id == user.id, VisitRating.care_job_id.in_(job_ids)).all()
    return {r.care_job_id: r for r in rows}


def rate_visit(db: Session, user: User, elder: Elder, job_id: int, rating: int, comment: str = "") -> VisitRating:
    job = _family_job(db, elder, job_id)
    if job.status != "completed":
        raise_bad_request("Only completed visits can be rated")
    if not 1 <= int(rating) <= 5:
        raise_bad_request("Rating must be 1 to 5")
    if my_ratings(db, user, [job.id]):
        raise_conflict("You have already rated this visit")
    row = VisitRating(
        tenant_id=elder.tenant_id, elder_id=elder.id, care_job_id=job.id, user_id=user.id,
        rating=int(rating), comment=(comment or "").strip()[:1000],
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:  # double tap
        db.rollback()
        raise_conflict("You have already rated this visit")
    db.refresh(row)
    return row


def rating_dict(r: VisitRating) -> dict:
    return {"id": r.id, "job_id": r.care_job_id, "rating": r.rating, "comment": r.comment or "",
            "created_at": _iso(r.created_at), "reviewed_at": _iso(r.reviewed_at)}


# --- NPS -------------------------------------------------------------------------------


def nps_status(db: Session, user: User, elder: Elder, *, now: datetime | None = None) -> dict:
    """Due when there has been a completed visit, and no answer in 90 days (no dismissal in 30)."""
    now = now or datetime.now(timezone.utc)
    last = (
        db.query(NpsResponse)
        .filter(NpsResponse.user_id == user.id, NpsResponse.elder_id == elder.id)
        .order_by(NpsResponse.created_at.desc(), NpsResponse.id.desc())
        .first()
    )
    had_visit = (
        db.query(CareJob.id)
        .filter(CareJob.elder_id == elder.id, CareJob.status == "completed", CareJob.kind.in_(_VISIT_KINDS))
        .first()
        is not None
    )
    due = had_visit
    if last is not None:
        wait = NPS_EVERY_DAYS if last.score is not None else NPS_SNOOZE_DAYS
        due = had_visit and now - _aware(last.created_at) >= timedelta(days=wait)
    return {"due": bool(due), "last_score": last.score if last else None, "last_at": _iso(last.created_at) if last else None}


def answer_nps(db: Session, user: User, elder: Elder, score: int | None, reason: str = "",
               *, now: datetime | None = None) -> dict:
    if not nps_status(db, user, elder, now=now)["due"]:
        raise_conflict("Thanks — you've answered this recently")
    if score is not None and not 0 <= int(score) <= 10:
        raise_bad_request("Score must be 0 to 10")
    row = NpsResponse(
        tenant_id=elder.tenant_id, elder_id=elder.id, user_id=user.id,
        score=None if score is None else int(score), reason=(reason or "").strip()[:1000],
    )
    if now is not None:
        row.created_at = now
    db.add(row)
    db.commit()
    return {"ok": True, "score": row.score}


def nps_summary(db: Session, tenant_id: int | None, elder_ids: set[int] | None, *, days: int = 365) -> dict:
    """NPS = % promoters (9–10) − % detractors (0–6), latest answer per family login."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = db.query(NpsResponse).filter(NpsResponse.score.isnot(None), NpsResponse.created_at >= since)
    if tenant_id is not None:
        q = q.filter(NpsResponse.tenant_id == tenant_id)
    if elder_ids is not None:
        q = q.filter(NpsResponse.elder_id.in_(list(elder_ids) or [-1]))
    latest: dict[tuple[int, int], NpsResponse] = {}
    for r in q.order_by(NpsResponse.created_at, NpsResponse.id).all():
        latest[(r.user_id, r.elder_id)] = r
    scores = [r.score for r in latest.values()]
    n = len(scores)
    pro = sum(1 for s in scores if s >= 9)
    det = sum(1 for s in scores if s <= DETRACTOR_MAX)
    return {"responses": n, "promoters": pro, "passives": n - pro - det, "detractors": det,
            "nps": round((pro - det) * 100 / n) if n else None}


# --- Needs attention -----------------------------------------------------------------


def attention_rows(db: Session, elders: list[Elder]) -> list[dict]:
    """Low visit ratings and NPS detractors nobody has reviewed yet, newest first."""
    by_id = {e.id: e for e in elders}
    ids = list(by_id) or [-1]
    out = []
    for r in (
        db.query(VisitRating)
        .filter(VisitRating.elder_id.in_(ids), VisitRating.rating <= LOW_RATING, VisitRating.reviewed_at.is_(None))
        .order_by(VisitRating.created_at.desc())
        .limit(30)
        .all()
    ):
        out.append({"kind": "rating", "id": r.id, "elder_id": r.elder_id, "elder_name": _name(by_id[r.elder_id]),
                    "score": r.rating, "comment": r.comment or "", "job_id": r.care_job_id,
                    "by_name": _user_name(db, r.user_id), "created_at": _iso(r.created_at)})
    for r in (
        db.query(NpsResponse)
        .filter(NpsResponse.elder_id.in_(ids), NpsResponse.score.isnot(None),
                NpsResponse.score <= DETRACTOR_MAX, NpsResponse.reviewed_at.is_(None))
        .order_by(NpsResponse.created_at.desc())
        .limit(30)
        .all()
    ):
        out.append({"kind": "nps", "id": r.id, "elder_id": r.elder_id, "elder_name": _name(by_id[r.elder_id]),
                    "score": r.score, "comment": r.reason or "", "job_id": None,
                    "by_name": _user_name(db, r.user_id), "created_at": _iso(r.created_at)})
    out.sort(key=lambda x: x["created_at"] or "", reverse=True)
    return out


def mark_reviewed(db: Session, user: User, kind: str, row_id: int) -> dict:
    from app.core.rbac import assert_tenant_access
    from app.core.team_scope import assert_elder_in_team

    model = {"rating": VisitRating, "nps": NpsResponse}.get(kind)
    row = db.get(model, row_id) if model else None
    if not row:
        raise_not_found("Feedback not found")
    assert_tenant_access(user, row.tenant_id)
    assert_elder_in_team(db, user, row.elder_id)
    if row.reviewed_at is None:
        row.reviewed_at = datetime.now(timezone.utc)
        row.reviewed_by_user_id = user.id
        db.commit()
    return {"kind": kind, "id": row.id, "reviewed_at": _iso(row.reviewed_at)}


def client_feedback(db: Session, elder: Elder) -> dict:
    ratings = (
        db.query(VisitRating).filter(VisitRating.elder_id == elder.id)
        .order_by(VisitRating.created_at.desc()).limit(30).all()
    )
    nps = (
        db.query(NpsResponse).filter(NpsResponse.elder_id == elder.id, NpsResponse.score.isnot(None))
        .order_by(NpsResponse.created_at.desc()).limit(20).all()
    )
    return {
        "ratings": [{**rating_dict(r), "by_name": _user_name(db, r.user_id)} for r in ratings],
        "nps": [{"id": r.id, "score": r.score, "reason": r.reason or "", "by_name": _user_name(db, r.user_id),
                 "created_at": _iso(r.created_at), "reviewed_at": _iso(r.reviewed_at)} for r in nps],
    }


# --- voice notes ---------------------------------------------------------------------


def _base_mime(content_type: str | None) -> str:
    return (content_type or "").split(";")[0].strip().lower()


def voice_dict(n: VisitVoiceNote, *, family: bool = False) -> dict:
    base = "/api/v1/home-safety/family/voice-notes" if family else "/api/v1/home-safety/voice-notes"
    out = {"id": n.id, "job_id": n.care_job_id, "duration_s": n.duration_s, "mime_type": n.mime_type,
           "created_at": _iso(n.created_at), "url": f"{base}/{n.id}/audio"}
    if not family:
        out.update({"recorded_by_name": n.recorded_by_name or "", "share_with_family": bool(n.share_with_family),
                    "shared_at": _iso(n.shared_at)})
    return out


_VOICE_CONTAINER = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "mp4", "audio/x-m4a": "mp4",
                    "audio/aac": "aac"}


def sniff_audio(content: bytes) -> str | None:
    """Container from the first bytes: webm (EBML), ogg, mp4/m4a (ftyp) or ADTS aac."""
    head = content[:16]
    if head.startswith(bytes.fromhex("1a45dfa3")):
        return "webm"
    if head.startswith(b"OggS"):
        return "ogg"
    if len(head) >= 8 and head[4:8] == b"ftyp":
        return "mp4"
    if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xF6) == 0xF0:
        return "aac"
    return None


def add_voice_note(db: Session, user: User, job_id: int, *, file_name: str, content: bytes,
                   content_type: str | None, duration_s: int | None) -> dict:
    from app.core.storage import get_storage
    from app.livewell.care_jobs import _caregiver_job

    job = _caregiver_job(db, user, job_id)
    if job.status == "cancelled":
        raise_bad_request("This visit was cancelled")
    mime = _base_mime(content_type)
    if mime not in VOICE_TYPES:
        raise_bad_request("Voice notes must be audio (webm, ogg or mp4)")
    if not content:
        raise_bad_request("The recording is empty")
    if len(content) > VOICE_MAX_BYTES:
        from fastapi import HTTPException

        raise HTTPException(status_code=413, detail="The recording is too large (keep it under 60 seconds)")
    if sniff_audio(content) != _VOICE_CONTAINER[mime]:
        raise_bad_request("That file is not a playable voice recording")
    if duration_s is not None and not 0 < duration_s <= VOICE_MAX_SECONDS + 1:
        raise_bad_request("Keep voice notes to 60 seconds or less")
    # Lock the visit row so two uploads at once cannot both pass the 5-per-visit cap
    # (Postgres row lock; held until the commit below).
    db.query(CareJob.id).filter(CareJob.id == job.id).with_for_update().one()
    count = db.query(func.count(VisitVoiceNote.id)).filter(VisitVoiceNote.care_job_id == job.id).scalar() or 0
    if count >= VOICE_PER_JOB:
        raise_bad_request(f"A visit can have up to {VOICE_PER_JOB} voice notes")
    name = f"voice-note-{job.id}-{count + 1}.{VOICE_TYPES[mime]}"
    key, _url = get_storage().save(job.tenant_id, "elder", job.elder_id, name, content, mime)
    note = VisitVoiceNote(
        tenant_id=job.tenant_id, elder_id=job.elder_id, care_job_id=job.id, storage_key=key, mime_type=mime,
        size_bytes=len(content), duration_s=min(int(duration_s), VOICE_MAX_SECONDS) if duration_s else None,
        recorded_by_user_id=user.id,
        recorded_by_name=f"{user.first_name or ''} {user.last_name or ''}".strip() or (user.email or ""),
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return voice_dict(note)


def staff_voice_notes(db: Session, elder: Elder, limit: int = 30) -> list[dict]:
    rows = (
        db.query(VisitVoiceNote).filter(VisitVoiceNote.elder_id == elder.id)
        .order_by(VisitVoiceNote.created_at.desc(), VisitVoiceNote.id.desc()).limit(limit).all()
    )
    return [voice_dict(n) for n in rows]


def _staff_note(db: Session, user: User, note_id: int) -> VisitVoiceNote:
    from app.core.rbac import resolve_tenant_id
    from app.core.team_scope import team_elder_ids

    note = db.get(VisitVoiceNote, note_id)
    tid = resolve_tenant_id(user)
    team = team_elder_ids(db, user)
    if not note or (tid is not None and note.tenant_id != tid) or (team is not None and note.elder_id not in team):
        raise_not_found("Voice note not found")
    return note


def share_voice_note(db: Session, user: User, note_id: int, share: bool) -> dict:
    note = _staff_note(db, user, note_id)
    note.share_with_family = bool(share)
    note.shared_by_user_id = user.id if share else None
    note.shared_at = datetime.now(timezone.utc) if share else None
    db.commit()
    return voice_dict(note)


def _read(note: VisitVoiceNote) -> tuple[bytes, str]:
    from app.core.storage import get_storage

    content, _mime = get_storage().read(note.storage_key)
    return content, note.mime_type or "audio/webm"


def staff_audio(db: Session, user: User, note_id: int) -> tuple[bytes, str]:
    return _read(_staff_note(db, user, note_id))


def family_audio(db: Session, elder: Elder, note_id: int) -> tuple[bytes, str]:
    note = db.get(VisitVoiceNote, note_id)
    if not note or note.elder_id != elder.id or not note.share_with_family:
        raise_not_found("Voice note not found")
    return _read(note)


def family_voice_notes(db: Session, elder: Elder, job_id: int) -> list[dict]:
    rows = (
        db.query(VisitVoiceNote)
        .filter(VisitVoiceNote.elder_id == elder.id, VisitVoiceNote.care_job_id == job_id,
                VisitVoiceNote.share_with_family.is_(True))
        .order_by(VisitVoiceNote.id).all()
    )
    return [voice_dict(n, family=True) for n in rows]


# --- quality numbers -------------------------------------------------------------------


def _has_kushlife(report: dict | None) -> bool:
    from app.livewell.kushlife import _complete_legacy

    rep = report or {}
    return bool(rep.get("kushlife")) or _complete_legacy(rep.get("checks"))


def _quality(db: Session, elder_ids: list[int], since: datetime) -> dict:
    from app.models.incident_report import IncidentReport

    ids = elder_ids or [-1]
    jobs = (
        db.query(CareJob)
        .filter(CareJob.elder_id.in_(ids), CareJob.kind.in_(_VISIT_KINDS), CareJob.status == "completed",
                CareJob.completed_at >= since)
        .all()
    )
    timed = on_time = 0
    for j in jobs:
        arrived = _aware(j.checked_in_at or j.started_at)
        sched = _aware(j.scheduled_at)
        if arrived and sched:
            timed += 1
            on_time += 1 if arrived <= sched + ON_TIME_GRACE else 0
    with_kl = sum(1 for j in jobs if _has_kushlife(j.report))
    avg, n_ratings = (
        db.query(func.avg(VisitRating.rating), func.count(VisitRating.id))
        .filter(VisitRating.elder_id.in_(ids), VisitRating.created_at >= since).one()
    )
    incidents = (
        db.query(func.count(IncidentReport.id))
        .filter(IncidentReport.elder_id.in_(ids), IncidentReport.occurred_at >= since).scalar()
    ) or 0
    return {
        "visits_done": len(jobs),
        "on_time_pct": round(on_time * 100 / timed) if timed else None,
        "on_time_measured": timed,
        "kushlife_pct": round(with_kl * 100 / len(jobs)) if jobs else None,
        "avg_rating": round(float(avg), 1) if avg is not None else None,
        "ratings": int(n_ratings or 0),
        "incidents": int(incidents),
    }


def client_quality(db: Session, elder: Elder, *, days: int = 30) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    return {"days": days, **_quality(db, [elder.id], since),
            "nps": nps_summary(db, elder.tenant_id, {elder.id})}


def agency_quality(db: Session, user: User, *, days: int = 30) -> dict:
    """The viewer's team (whole agency for admins), with a row per client."""
    from app.core.rbac import resolve_tenant_id
    from app.core.team_scope import team_elder_ids

    tid = resolve_tenant_id(user)
    team = team_elder_ids(db, user)
    q = db.query(Elder).filter(Elder.status != "INACTIVE")
    if tid is not None:
        q = q.filter(Elder.tenant_id == tid)
    elders = [e for e in q.all() if team is None or e.id in team]
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = []
    for e in elders:
        qn = _quality(db, [e.id], since)
        if qn["visits_done"] or qn["ratings"] or qn["incidents"]:
            rows.append({"elder_id": e.id, "elder_name": _name(e), **qn})
    rows.sort(key=lambda r: r["elder_name"].lower())
    return {
        "days": days,
        "agency": _quality(db, [e.id for e in elders], since),
        "nps": nps_summary(db, tid, None if team is None else {e.id for e in elders}),
        "clients": rows,
    }
