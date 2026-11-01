"""Safe Home family app — dashboard data for children & family members."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.livewell.brand import with_brand
from app.livewell.family_alert_text import clean_family_summary
from app.livewell.visit_service import HomeSafetyVisitService
from app.models.user import User
from app.services.elder_portal_service import ElderPortalService


def _empty_score() -> dict:
    return {
        "total": 0,
        "max_total": 100,
        "grade": "—",
        "grade_label": "No published assessment yet",
        "band_status": None,
        "assessed_at": None,
        "summary": with_brand(
            "Your LiveWell360 team has not published a LiveWell360 Safety Score for this "
            "home yet. It appears here after a completed assessment is linked to this senior."
        ),
        "is_demo": False,
        "has_published_score": False,
    }


def _score_from_block(sh: dict) -> dict:
    score = sh.get("safety_score") if isinstance(sh.get("safety_score"), dict) else None
    if not score:
        return _empty_score()
    is_demo = bool(score.get("is_demo"))
    return {
        "total": int(score.get("total", 0) or 0),
        "max_total": int(score.get("max_total", 100) or 100),
        "grade": score.get("grade") or "—",
        "grade_label": score.get("grade_label") or "",
        "band_status": score.get("band_status"),
        "assessed_at": score.get("assessed_at"),
        "summary": clean_family_summary(score.get("summary")),
        "is_demo": is_demo,
        "has_published_score": not is_demo and score.get("total") is not None,
        # Band capped by critical findings: families see "Some urgent fixes needed (N)".
        "urgent_fix_count": (
            len(score.get("critical_findings") or []) or 1
            if score.get("capped_by_critical_item")
            else 0
        ),
        # The one urgent list (hero "Fix first", What we found, /plan, Home's count).
        "critical_findings": _critical_findings(score),
    }


def _critical_findings(score: dict) -> list[dict]:
    rows = score.get("critical_findings") if score.get("capped_by_critical_item") else None
    out: list[dict] = []
    for f in rows or []:
        if isinstance(f, dict) and str(f.get("label") or "").strip():
            out.append(
                {
                    "id": str(f.get("id") or ""),
                    "label": str(f.get("label")).strip(),
                    "area": str(f.get("category") or "").lstrip("0123456789. ").strip(),
                }
            )
    return out


def _solution_links() -> dict[str, dict]:
    """Solution id -> library row (rubric ids it fixes, wording, points)."""
    from app.livewell.solution_service import DEFAULT_SOLUTIONS

    return {
        str(s.get("id")): s
        for s in DEFAULT_SOLUTIONS.get("solutions") or []
        if isinstance(s, dict) and s.get("id")
    }


def align_plan_urgency(items: list[dict], critical: list[dict], links: dict[str, dict] | None = None) -> list[dict]:
    """/plan's "Urgent" = the assessment's critical findings, nothing else.

    A plan item is critical only when it fixes a critical finding (the library's
    rubricItemIds); a "critical" item that fixes none drops to high. A critical
    finding no plan item covers gets its own item from the library (or its label),
    so pathway and rugs are on the plan too.
    """
    from app.livewell.solution_id_aliases import resolve_solution_id

    links = _solution_links() if links is None else links
    crit_ids = [str(c.get("id") or "") for c in critical if c.get("id")]
    covered: set[str] = set()
    out: list[dict] = []
    for it in items:
        row = dict(it)
        sol_id = str(row.get("id") or "")
        sol_id = sol_id if sol_id in links else resolve_solution_id(sol_id)
        fixes = {str(x) for x in (links.get(sol_id, {}).get("rubricItemIds") or [])}
        hit = fixes.intersection(crit_ids)
        if hit:
            row["priority"] = "critical"
            covered |= hit
        elif row.get("priority") == "critical":
            row["priority"] = "high"
        out.append(row)
    for c in critical:
        cid = str(c.get("id") or "")
        if not cid or cid in covered:
            continue
        sol = next((s for s in links.values() if cid in (s.get("rubricItemIds") or [])), None)
        if sol and any(o.get("id") == sol.get("id") for o in out):
            continue
        covered.add(cid)
        out.append(
            {
                "id": str(sol.get("id")) if sol else f"finding-{cid}",
                "title": str((sol or {}).get("finding") or c.get("label") or "Urgent fix"),
                "priority": "critical",
                "why": (str((sol or {}).get("riskDescription") or "").strip() or None),
                "actions": [str(a) for a in ((sol or {}).get("recommendedSolutions") or []) if str(a).strip()],
                "score_gain": int((sol or {}).get("scoreImprovement") or 0),
                "status": "open",
                "domain": c.get("area") or None,
                "estimated_cost": (str((sol or {}).get("estimatedCost") or "").strip() or None),
            }
        )
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    out.sort(key=lambda r: (rank.get(r.get("priority") or "", 9), -int(r.get("score_gain") or 0)))
    return out


def _plan_items(sh: dict) -> list[dict]:
    plan = sh.get("improvement_plan") if isinstance(sh.get("improvement_plan"), dict) else {}
    items = plan.get("items") if isinstance(plan, dict) else []
    if not isinstance(items, list):
        return []
    out: list[dict] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "id": str(row.get("id") or ""),
                "title": str(row.get("title") or "Improvement"),
                "priority": str(row.get("priority") or "medium"),
                "why": row.get("why"),
                "actions": list(row.get("actions") or []),
                "score_gain": int(row.get("score_gain") or 0),
                "status": str(row.get("status") or "open"),
                "domain": row.get("domain"),
                "estimated_cost": row.get("estimated_cost"),
            }
        )
    return out


def _parse_iso(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _stability_history(sh: dict) -> list[dict]:
    """Visit stability scores for family trend (centered at 50). Backfills from visits if needed."""
    rows = sh.get("stability_score_history") if isinstance(sh.get("stability_score_history"), list) else []
    out: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            score = int(row.get("score"))
        except (TypeError, ValueError):
            continue
        score = max(0, min(100, score))
        visit_id = str(row.get("visit_id") or "")
        visited = row.get("visited_at")
        key = visit_id or f"{visited}:{score}"
        if key in seen:
            continue
        seen.add(key)
        delta = row.get("delta_from_baseline")
        try:
            delta_i = int(delta) if delta is not None else score - 50
        except (TypeError, ValueError):
            delta_i = score - 50
        out.append(
            {
                "score": score,
                "visited_at": visited,
                "visit_id": visit_id or None,
                "delta_from_baseline": delta_i,
                "band": str(row.get("band") or "") or None,
            }
        )

    if not out:
        visits = sh.get("visits") if isinstance(sh.get("visits"), list) else []
        for v in visits:
            if not isinstance(v, dict):
                continue
            status = str(v.get("status") or "completed").lower()
            if status not in ("completed", "done"):
                continue
            try:
                score = int(v.get("stability_score"))
            except (TypeError, ValueError):
                continue
            score = max(0, min(100, score))
            visit_id = str(v.get("id") or "")
            key = visit_id or f"{v.get('visited_at')}:{score}"
            if key in seen:
                continue
            seen.add(key)
            stab = v.get("stability") if isinstance(v.get("stability"), dict) else {}
            delta = stab.get("delta_from_baseline")
            try:
                delta_i = int(delta) if delta is not None else score - 50
            except (TypeError, ValueError):
                delta_i = score - 50
            out.append(
                {
                    "score": score,
                    "visited_at": v.get("visited_at"),
                    "visit_id": visit_id or None,
                    "delta_from_baseline": delta_i,
                    "band": stab.get("band"),
                }
            )

    out.sort(
        key=lambda row: _parse_iso(row.get("visited_at"))
        or datetime.min.replace(tzinfo=timezone.utc)
    )
    return out[-24:]


def _stability_delta(history: list[dict]) -> int | None:
    if len(history) < 2:
        return None
    try:
        return int(history[-1]["score"]) - int(history[-2]["score"])
    except (KeyError, TypeError, ValueError):
        return None


class HomeSafetyFamilyService:

    @staticmethod
    def _safe_home_block(elder) -> dict:
        attrs = elder.custom_attributes or {}
        block = attrs.get("safe_home")
        if isinstance(block, dict):
            return block
        return {}

    @staticmethod
    def _parse_dt(value) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _score_response(score: dict) -> dict:
        return {
            "total": int(score.get("total", 0)),
            "max_total": int(score.get("max_total", 100)),
            "grade": score.get("grade", "—"),
            "grade_label": score.get("grade_label", ""),
            "band_status": score.get("band_status"),
            "assessed_at": HomeSafetyFamilyService._parse_dt(score.get("assessed_at")),
            "summary": clean_family_summary(score.get("summary")),
            "is_demo": bool(score.get("is_demo")),
            "has_published_score": bool(score.get("has_published_score")),
            "urgent_fix_count": int(score.get("urgent_fix_count") or 0),
            "critical_findings": list(score.get("critical_findings") or []),
        }

    @staticmethod
    def _domain_scores(sh: dict) -> list[dict]:
        rows = sh.get("domain_scores") if isinstance(sh.get("domain_scores"), list) else []
        out = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            out.append(
                {
                    "id": str(row.get("id") or ""),
                    "title": str(row.get("title") or ""),
                    "score": int(row.get("score") or 0),
                    "max_points": int(row.get("max_points") or 0),
                    "earned_points": float(row.get("earned_points") or 0),
                }
            )
        return out

    @staticmethod
    def _care_pathway(sh: dict) -> dict | None:
        raw = sh.get("care_pathway") if isinstance(sh.get("care_pathway"), dict) else None
        if not raw:
            return None
        return {
            "membership_id": raw.get("membership_id"),
            "membership_label": raw.get("membership_label"),
            "ecm_recommended": bool(raw.get("ecm_recommended")),
            "ecm_note": raw.get("ecm_note"),
        }

    @staticmethod
    def dashboard(db: Session, user: User) -> dict:
        me = ElderPortalService.portal_me(db, user)
        elder = ElderPortalService.get_linked_elder(db, user)
        sh = HomeSafetyFamilyService._safe_home_block(elder)
        score = _score_from_block(sh)
        wellness = sh.get("wellness_reports") or []
        plan_items = _plan_items(sh)
        open_items = [i for i in plan_items if i.get("status") != "done"]

        last_visit = HomeSafetyVisitService.last_visit_at(elder)
        visit_count = HomeSafetyVisitService.visit_count(elder)
        upcoming = HomeSafetyVisitService.list_upcoming_for_family(db, user, limit=5)
        # Booked jobs (visits, assessments, installs) count as upcoming too.
        from app.livewell.care_jobs import family_jobs

        # Drop past items (UTC-normalised) BEFORE sorting, then take the first
        # future one — a stale "upcoming" row used to hide a real booking.
        now_utc = datetime.now(timezone.utc)
        future = []
        for v in [*upcoming, *family_jobs(db, user)[0]]:
            when = _parse_iso(v.get("visited_at"))
            if when is None:
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if when > now_utc:
                future.append((when, v))
        future.sort(key=lambda pair: pair[0])
        next_visit = future[0][1] if future else None

        care = ElderPortalService.care_status(db, user)
        unread = care.get("unread_notifications", 0)

        plan_meta = sh.get("improvement_plan") if isinstance(sh.get("improvement_plan"), dict) else {}
        stability_history = _stability_history(sh)
        stability_delta = _stability_delta(stability_history)
        latest_stability = stability_history[-1] if stability_history else None

        from app.livewell.family_visualizations import list_approved_visualizations_for_elder

        all_visuals = list_approved_visualizations_for_elder(
            db, tenant_id=elder.tenant_id, elder_id=elder.id, limit=50
        )

        safety = HomeSafetyFamilyService._score_response(score)
        safety["domain_scores"] = HomeSafetyFamilyService._domain_scores(sh)
        safety["care_pathway"] = HomeSafetyFamilyService._care_pathway(sh)

        care_status = HomeSafetyVisitService.care_status_for_elder(db, elder)
        if care_status and latest_stability:
            care_status = {
                **care_status,
                "stability_score": latest_stability.get("score"),
                "stability_delta_from_baseline": latest_stability.get("delta_from_baseline"),
                "stability_band": latest_stability.get("band"),
            }

        return {
            "parent_name": f"{me['first_name']} {me['last_name']}".strip(),
            # The signed-in family member, for the dashboard greeting.
            "viewer_first_name": (user.first_name or "").strip() or None,
            # The signed-in person is the elder (self account): "Here is how you are doing".
            "viewer_is_elder": (user.portal_relationship or "").strip().lower() == "self"
            or (
                bool((user.first_name or "").strip())
                and f"{user.first_name} {user.last_name or ''}".strip().lower()
                == f"{elder.first_name} {elder.last_name or ''}".strip().lower()
            ),
            "senior_name": f"{elder.first_name} {elder.last_name}".strip(),
            "senior_address": elder.address,
            "safety": safety,
            "unread_alerts": unread,
            "last_visit_at": last_visit,
            "wellness_count": len(wellness) if isinstance(wellness, list) else 0,
            "visit_count": visit_count,
            "has_published_score": bool(score.get("has_published_score")),
            "top_priorities": open_items[:3],
            "plan_item_count": len(open_items),
            "projected_score": plan_meta.get("projected_score"),
            "stability_score_history": [
                {
                    **row,
                    "visited_at": HomeSafetyFamilyService._parse_dt(row.get("visited_at")),
                }
                for row in stability_history
            ],
            "stability_score_delta": stability_delta,
            "latest_stability_score": latest_stability.get("score") if latest_stability else None,
            "approved_visual_count": len(all_visuals),
            "preview_visuals": all_visuals[:3],
            "domain_scores": safety["domain_scores"],
            "care_pathway": safety["care_pathway"],
            "share_brief": clean_family_summary(sh.get("share_brief") or score.get("summary")),
            "estimated_cost_note": plan_meta.get("estimated_cost_note"),
            "next_visit_at": next_visit.get("visited_at") if next_visit else None,
            "next_visit_label": (
                f"{next_visit.get('visit_type')}"
                + (f" · {next_visit.get('staff_name')}" if next_visit and next_visit.get("staff_name") else "")
                if next_visit
                else None
            ),
            "open_incidents": int(care.get("open_incidents") or 0),
            "unread_messages_hint": 0,
            "active_elder_id": elder.id,
            "elders": me.get("elders") or [],
            "care_status": care_status,
            **HomeSafetyFamilyService._home_extras(db, user, elder, care),
        }

    @staticmethod
    def _home_extras(db: Session, user: User, elder, care: dict) -> dict:
        """Phase 2E Home: care team contact, last visit card and "Needs you"."""
        from app.livewell.care_team_contact import get_contact
        from app.models.tenant import Tenant

        contact = get_contact(db.get(Tenant, elder.tenant_id))

        last = None
        try:
            now = datetime.now(timezone.utc)
            done = []
            for v in HomeSafetyVisitService.list_for_family(db, user, days=365):
                when = _parse_iso(v.get("visited_at"))
                if when and when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                if when and when <= now and str(v.get("status") or "").lower() == "completed":
                    done.append((when, v))
            # Care jobs (KushLife visits) count too, so "last visit" is truly the latest.
            try:
                from app.livewell.care_jobs import family_jobs

                for v in family_jobs(db, user)[1]:
                    when = _parse_iso(v.get("visited_at"))
                    if when and when.tzinfo is None:
                        when = when.replace(tzinfo=timezone.utc)
                    if when and when <= now and str(v.get("status") or "").lower() == "completed":
                        done.append((when, v))
            except Exception:  # noqa: BLE001
                pass
            if done:
                when, v = max(done, key=lambda pair: pair[0])
                photo = None
                try:
                    from app.livewell.family_care_hub import _job_photo_ids
                    from app.livewell.visit_reports import family_photo_items

                    vid = str(v.get("id") or "")
                    ids = _job_photo_ids(db, vid) if vid.startswith("job-") else v.get("photo_ids")
                    items = family_photo_items(db, elder, ids) if ids else []
                    photo = items[0] if items else None
                except Exception:  # noqa: BLE001 - photos never break Home
                    photo = None
                last = {
                    "id": str(v.get("id") or ""),
                    "visited_at": when,
                    "visit_type": v.get("visit_type") or "Visit",
                    "staff_name": v.get("staff_name") or None,
                    "summary": v.get("summary") or None,
                    "photo": photo,
                }
        except Exception:  # noqa: BLE001 - the home page must still load
            last = None

        needs: list[dict] = []
        quotes = 0
        try:
            from app.livewell.family_service_requests import FamilyServiceRequestService

            quotes += sum(
                1
                for r in FamilyServiceRequestService.list_for_family(db, user)
                if r.get("payment_status") == "awaiting_approval" and r.get("status") != "cancelled"
            )
        except Exception:  # noqa: BLE001
            pass
        if quotes:
            needs.append({
                "kind": "quote",
                "title": "A price is waiting for your approval" if quotes == 1
                else f"{quotes} prices are waiting for your approval",
                "action": "Review and approve",
                "href": "/kushalaya/family/services",
            })
        # Quotes sent from ops (orders): one row each, with the GST-inclusive total.
        try:
            from app.core.money import format_minor
            from app.livewell.commerce import list_family_quotes

            for q in list_family_quotes(db, user):
                if q.get("needs_action"):
                    needs.append({
                        "kind": "quote",
                        "id": q.get("id"),
                        "title": f"Approve quote: {format_minor(int(q.get('total_paise') or 0))} incl. GST",
                        "action": "Review and pay",
                        "href": "/kushalaya/family/services#quotes",
                    })
        except Exception:  # noqa: BLE001 - the home page must still load
            pass
        open_sos = int(care.get("open_incidents") or 0)
        if open_sos:
            needs.append({
                "kind": "sos",
                "title": "An SOS is open",
                "action": "See what is happening",
                "href": "/kushalaya/family/alerts",
            })
        try:
            from app.livewell.family_care_hub import FamilyCareHubService

            urgent = sum(
                1
                for a in FamilyCareHubService.list_alerts(db, user)
                if not a.get("read_at") and a.get("severity") in ("critical", "high", "urgent")
            )
        except Exception:  # noqa: BLE001 - the home page must still load
            urgent = 0
        if urgent:
            needs.append({
                "kind": "alert",
                "title": "An urgent alert is unread" if urgent == 1
                else f"{urgent} urgent alerts are unread",
                "action": "Read alerts",
                "href": "/kushalaya/family/alerts",
            })
        return {"care_team_contact": contact, "last_visit": last, "needs_you": needs}

    @staticmethod
    def list_elders(db: Session, user: User) -> dict:
        from app.livewell.family_elder_access import elders_payload

        ElderPortalService.get_linked_elder(db, user)
        linked = elders_payload(db, user)
        return {
            "active_elder_id": user.elder_id,
            "elders": linked,
        }

    @staticmethod
    def set_active_elder(db: Session, user: User, elder_id: int) -> dict:
        from app.livewell.family_elder_access import set_active_elder

        elder = set_active_elder(db, user, elder_id)
        return HomeSafetyFamilyService.list_elders(db, user) | {
            "senior_name": f"{elder.first_name} {elder.last_name}".strip(),
        }

    @staticmethod
    def staff_link_family_user(
        db: Session,
        actor: User,
        *,
        elder_id: int,
        email: str,
        set_active: bool = False,
    ) -> dict:
        """Link an existing family portal user to another elder (same tenant)."""
        from app.core.responses import raise_bad_request, raise_not_found
        from app.core.rbac import CARE_MANAGER, ELDER_PORTAL, SYSTEM_ADMIN, TENANT_ADMIN
        from app.livewell.family_elder_access import ensure_family_elder_link, elders_payload
        from app.models.elder import Elder

        if actor.role not in {SYSTEM_ADMIN, TENANT_ADMIN, CARE_MANAGER}:
            raise_bad_request("Only admins can link family users to elders")

        elder = db.query(Elder).filter(Elder.id == elder_id).first()
        if not elder:
            raise_not_found("Elder not found")
        if actor.role != SYSTEM_ADMIN and actor.tenant_id != elder.tenant_id:
            raise_bad_request("Cannot link across tenants")

        email_n = (email or "").strip().lower()
        member = db.query(User).filter(User.email == email_n).first()
        if not member:
            raise_not_found("Family user not found")
        if member.role != ELDER_PORTAL:
            raise_bad_request("User is not a family portal account")
        if member.tenant_id != elder.tenant_id:
            raise_bad_request("Family user belongs to another organization")

        ensure_family_elder_link(db, member, elder)
        if set_active or member.elder_id is None:
            member.elder_id = elder.id
        db.commit()
        db.refresh(member)
        return {
            "user_id": member.id,
            "email": member.email,
            "active_elder_id": member.elder_id,
            "elders": elders_payload(db, member),
        }

    @staticmethod
    def staff_unlink_family_user(
        db: Session,
        actor: User,
        *,
        link_id: int,
        request=None,
    ) -> dict:
        """Remove a family login's access to one elder. Tenant-scoped through the elder."""
        from app.core.rbac import CARE_MANAGER, SYSTEM_ADMIN, TENANT_ADMIN
        from app.core.responses import WorkforceHTTPError, raise_not_found
        from app.livewell.family_elder_access import unlink_family_user
        from app.models.elder import Elder
        from app.models.family_elder_link import FamilyElderLink

        if actor.role not in {SYSTEM_ADMIN, TENANT_ADMIN, CARE_MANAGER}:
            raise WorkforceHTTPError("Only admins can unlink family users", status_code=403)
        link = db.query(FamilyElderLink).filter(FamilyElderLink.id == link_id).first()
        if not link:
            raise_not_found("Family link not found")
        elder = db.query(Elder).filter(Elder.id == link.elder_id).first()
        member = db.query(User).filter(User.id == link.user_id).first()
        if not elder or not member:
            raise_not_found("Family link not found")
        if actor.role != SYSTEM_ADMIN and actor.tenant_id != elder.tenant_id:
            raise_not_found("Family link not found")
        unlink_family_user(db, member, elder, commit=False)
        if request is not None:
            from app.services.session_activity_service import SessionActivityService

            SessionActivityService.record_user_action(
                db,
                request=request,
                user=actor,
                action="Unlinked family user",
                summary=f"{member.email} unlinked from {elder.first_name} {elder.last_name}".strip(),
                entity_type="elder",
                entity_id=str(elder.id),
                commit=False,
            )
        db.commit()
        return {"link_id": link_id, "user_id": member.id, "elder_id": elder.id, "removed": True}

    @staticmethod
    def safety_score(db: Session, user: User) -> dict:
        elder = ElderPortalService.get_linked_elder(db, user)
        sh = HomeSafetyFamilyService._safe_home_block(elder)
        base = HomeSafetyFamilyService._score_response(_score_from_block(sh))
        base["domain_scores"] = HomeSafetyFamilyService._domain_scores(sh)
        base["care_pathway"] = HomeSafetyFamilyService._care_pathway(sh)
        return base

    @staticmethod
    def share_brief(db: Session, user: User) -> dict:
        elder = ElderPortalService.get_linked_elder(db, user)
        sh = HomeSafetyFamilyService._safe_home_block(elder)
        score = _score_from_block(sh)
        text = clean_family_summary(str(sh.get("share_brief") or score.get("summary") or "")) or ""
        if not text:
            text = (
                f"LiveWell360 Family update for {elder.first_name} {elder.last_name}. "
                "No published assessment yet."
            )
        return {"text": text, "senior_name": f"{elder.first_name} {elder.last_name}".strip()}

    @staticmethod
    def improvement_plan(db: Session, user: User) -> dict:
        elder = ElderPortalService.get_linked_elder(db, user)
        sh = HomeSafetyFamilyService._safe_home_block(elder)
        plan = sh.get("improvement_plan") if isinstance(sh.get("improvement_plan"), dict) else {}
        score = _score_from_block(sh)
        items = _plan_items(sh)
        if items:
            items = align_plan_urgency(items, score.get("critical_findings") or [])
        return {
            "assessment_id": plan.get("assessment_id"),
            "current_score": plan.get("current_score") if plan.get("current_score") is not None else score.get("total"),
            "projected_score": plan.get("projected_score"),
            "finding_count": plan.get("finding_count") or len(items),
            "published_at": HomeSafetyFamilyService._parse_dt(plan.get("published_at")),
            "items": items,
            "has_plan": bool(items),
            "estimated_cost_note": plan.get("estimated_cost_note"),
        }

    @staticmethod
    def wellness_reports(db: Session, user: User) -> list[dict]:
        elder = ElderPortalService.get_linked_elder(db, user)
        sh = HomeSafetyFamilyService._safe_home_block(elder)
        out = []
        for row in sh.get("wellness_reports") or []:
            if not isinstance(row, dict):
                continue
            out.append(
                {
                    "id": str(row.get("id", "")),
                    "date": HomeSafetyFamilyService._parse_dt(row.get("date"))
                    or datetime.now(timezone.utc),
                    "visit_type": row.get("visit_type", "Wellness visit"),
                    "summary": row.get("summary", ""),
                    "family_message": row.get("family_message") or None,
                    "assessor_name": row.get("assessor_name"),
                    "highlights": list(row.get("highlights") or []),
                }
            )
        out.sort(key=lambda r: r["date"], reverse=True)
        return out

    @staticmethod
    def visit_history(db: Session, user: User, *, days: int = 60) -> list[dict]:
        return HomeSafetyVisitService.list_for_family(db, user, days=days)

    @staticmethod
    def visit_detail(db: Session, user: User, visit_id: str) -> dict:
        return HomeSafetyVisitService.get_for_family(db, user, visit_id)

    @staticmethod
    def visualizations(db: Session, user: User) -> list[dict]:
        from app.livewell.family_visualizations import list_approved_visualizations_for_elder

        elder = ElderPortalService.get_linked_elder(db, user)
        return list_approved_visualizations_for_elder(
            db, tenant_id=elder.tenant_id, elder_id=elder.id, limit=48
        )

    @staticmethod
    def staff_improvement_plan(db: Session, user: User, elder_id: int) -> dict:
        from app.core.rbac import assert_tenant_access, resolve_tenant_id
        from app.core.responses import raise_bad_request, raise_not_found
        from app.models.elder import Elder

        tid = resolve_tenant_id(user)
        if tid is None:
            raise_bad_request("Tenant required")
        elder = (
            db.query(Elder)
            .filter(Elder.id == elder_id, Elder.tenant_id == tid)
            .first()
        )
        if not elder:
            raise_not_found("Elder not found")
        assert_tenant_access(user, elder.tenant_id)
        sh = HomeSafetyFamilyService._safe_home_block(elder)
        plan = sh.get("improvement_plan") if isinstance(sh.get("improvement_plan"), dict) else {}
        items = _plan_items(sh)
        score = _score_from_block(sh)
        return {
            "assessment_id": plan.get("assessment_id"),
            "current_score": plan.get("current_score") if plan.get("current_score") is not None else score.get("total"),
            "projected_score": plan.get("projected_score"),
            "finding_count": plan.get("finding_count") or len(items),
            "published_at": HomeSafetyFamilyService._parse_dt(plan.get("published_at")),
            "items": items,
            "has_plan": bool(items),
            "estimated_cost_note": plan.get("estimated_cost_note"),
        }

    @staticmethod
    def update_plan_item_status(
        db: Session,
        user: User,
        *,
        elder_id: int,
        item_id: str,
        status: str,
    ) -> dict:
        """Staff: set improvement plan item status (open | scheduled | done)."""
        from sqlalchemy.orm.attributes import flag_modified

        from app.core.rbac import assert_tenant_access, resolve_tenant_id
        from app.core.responses import raise_bad_request, raise_not_found
        from app.models.elder import Elder

        status_n = str(status or "").strip().lower()
        if status_n not in ("open", "scheduled", "done"):
            raise_bad_request("status must be open, scheduled, or done")

        tid = resolve_tenant_id(user)
        if tid is None:
            raise_bad_request("Tenant required")
        elder = (
            db.query(Elder)
            .filter(Elder.id == elder_id, Elder.tenant_id == tid)
            .first()
        )
        if not elder:
            raise_not_found("Elder not found")
        assert_tenant_access(user, elder.tenant_id)

        attrs = dict(elder.custom_attributes or {})
        block = dict(attrs.get("safe_home") or {}) if isinstance(attrs.get("safe_home"), dict) else {}
        plan = dict(block.get("improvement_plan") or {}) if isinstance(block.get("improvement_plan"), dict) else {}
        items = list(plan.get("items") or [])
        if not isinstance(items, list):
            items = []

        found = False
        updated_item = None
        new_items = []
        for row in items:
            if not isinstance(row, dict):
                continue
            item = dict(row)
            if str(item.get("id") or "") == str(item_id):
                item["status"] = status_n
                found = True
                updated_item = item
            new_items.append(item)

        if not found:
            raise_not_found("Plan item not found")

        plan["items"] = new_items
        block["improvement_plan"] = plan
        attrs["safe_home"] = block
        elder.custom_attributes = attrs
        flag_modified(elder, "custom_attributes")
        db.commit()
        db.refresh(elder)

        return {
            "id": str(updated_item.get("id") or item_id),
            "title": str(updated_item.get("title") or "Improvement"),
            "priority": str(updated_item.get("priority") or "medium"),
            "why": updated_item.get("why"),
            "actions": list(updated_item.get("actions") or []),
            "score_gain": int(updated_item.get("score_gain") or 0),
            "status": status_n,
            "domain": updated_item.get("domain"),
        }

    @staticmethod
    def photos(db: Session, user: User) -> list[dict]:
        from app.livewell.photo_service import HomeSafetyPhotoService

        items = HomeSafetyPhotoService.list_for_family_user(db, user)
        activity = ElderPortalService.activity_summary(db, user)
        for e in activity.get("recent_events") or []:
            url = e.get("snapshot_url")
            if not url:
                continue
            items.append(
                {
                    "id": e["id"],
                    "caption": e.get("event_type", "Monitoring snapshot"),
                    "url": url,
                    "taken_at": e.get("event_timestamp"),
                    "source": "monitoring",
                }
            )
        items.sort(
            key=lambda p: p.get("taken_at") or "",
            reverse=True,
        )
        return items

    @staticmethod
    def alerts(db: Session, user: User) -> list[dict]:
        from app.livewell.family_care_hub import FamilyCareHubService

        return FamilyCareHubService.list_alerts(db, user)

    @staticmethod
    def emergency_contacts(db: Session, user: User) -> list[dict]:
        elder = ElderPortalService.get_linked_elder(db, user)
        sh = HomeSafetyFamilyService._safe_home_block(elder)
        contacts: list[dict] = []
        if elder.emergency_contact_name:
            contacts.append(
                {
                    "name": elder.emergency_contact_name,
                    "phone": elder.emergency_contact_phone,
                    "relationship": "Primary emergency",
                    "is_primary": True,
                }
            )
        for row in sh.get("extra_contacts") or []:
            if not isinstance(row, dict):
                continue
            contacts.append(
                {
                    "name": row.get("name", ""),
                    "phone": row.get("phone"),
                    "relationship": row.get("relationship"),
                    "is_primary": bool(row.get("is_primary")),
                }
            )
        if elder.phone:
            contacts.append(
                {
                    "name": f"{elder.first_name} {elder.last_name}".strip(),
                    "phone": elder.phone,
                    "relationship": "Senior (at home)",
                    "is_primary": False,
                }
            )
        # Never list the signed-in person as their own emergency contact.
        import re as _re

        from app.livewell.family_my_details import _family_phones

        digits = lambda v: _re.sub(r"\D", "", str(v or ""))[-10:]  # noqa: E731
        my_name = f"{user.first_name or ''} {user.last_name or ''}".strip().lower()
        my_phones = {digits(_family_phones(elder).get(str(user.id))), digits(getattr(user, "phone", None))} - {""}
        return [
            c
            for c in contacts
            if not (
                (my_name and str(c.get("name") or "").strip().lower() == my_name)
                or (digits(c.get("phone")) and digits(c.get("phone")) in my_phones)
            )
        ]
