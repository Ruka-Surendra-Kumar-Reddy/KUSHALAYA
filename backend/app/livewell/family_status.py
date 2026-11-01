"""One family status for an elder, worked out once on the server.

Home's status line, the digest and the details page all read this, so they
can't disagree ("4/4 checks OK" beside "slept poorly", or "Mobility: normal
for them" beside a care sheet that says "Assisted").
"""

from sqlalchemy.orm import Session

from app.models.elder import Elder


def _tone(word: str, level: str | None) -> str:
    w = (word or "").lower()
    if "calling" in w or level == "urgent":
        return "alert"
    if "watching" in w or level == "needs_attention":
        return "watch"
    return "ok"


def status_words(word: str | None) -> str:
    """Same words as Home's status line: "Small changes noted" -> "Well · small
    changes noted", "All good" -> "Well". Mirrors statusWords in
    frontend/lib/livewell/familyStatus.ts."""
    w = (word or "").strip()
    if not w or w.lower() == "all good":
        return "Well"
    if w.lower() == "small changes noted":
        return "Well · small changes noted"
    return w


def build_family_status(
    *,
    word: str,
    level: str | None,
    checks: dict | None,
    changes: list[str],
    last_visit_at: str | None,
    mobility_sheet: str | None,
    mobility_checkin: str | None,
) -> dict:
    """Pure part (easy to test): the status from already-loaded pieces."""
    vals = list((checks or {}).values())
    ok = sum(1 for v in vals if v == "ok")
    changes = [c for c in changes if c]
    # The care sheet (set by the care manager) wins; a check-in's "normal for
    # them" is only used when the sheet says nothing.
    mobility = (mobility_sheet or "").strip() or (mobility_checkin or "").replace("_", " ").strip()
    checks_text = f"{ok}/{len(vals)} checks OK" if vals else ""
    if checks_text and changes:
        checks_text += " · " + ", ".join(c[:1].lower() + c[1:] for c in changes)
    tone = _tone(word, level)
    return {
        "tone": tone,
        "word": word or "All good",
        "status_text": status_words(word),
        "changes": changes,
        "checks_ok": ok,
        "checks_total": len(vals),
        "checks_text": checks_text,
        "changes_text": ("Noted: " + ", ".join(changes)) if changes else "No changes noticed",
        "last_visit_at": last_visit_at,
        "mobility": mobility,
    }


def family_status(db: Session, elder: Elder) -> dict:
    """KushLife (latest visit checks + what the carer noted) + care level + mobility."""
    from app.livewell import kushlife
    from app.livewell.visit_service import HomeSafetyVisitService

    view = kushlife.kushlife_view(db, elder)
    visits = view.get("visits") or []
    latest = visits[0] if visits else {}
    care = HomeSafetyVisitService.care_status_for_elder(db, elder)
    snap = care.get("snapshot") or {}
    return build_family_status(
        word=view.get("status") or "",
        level=care.get("level"),
        checks=latest.get("checks") if isinstance(latest.get("checks"), dict) else None,
        changes=kushlife.reported_changes(visits),
        last_visit_at=latest.get("date"),
        mobility_sheet=getattr(elder, "mobility_status", None),
        mobility_checkin=snap.get("mobility"),
    )
