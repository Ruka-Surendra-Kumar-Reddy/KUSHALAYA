"""SafeHome 360™ assessment persistence — tenant DB (cross-device sync)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_conflict, raise_not_found
from app.livewell.customer_link import HomeSafetyCustomerLink
from app.livewell.family_elder_link import ensure_elder_for_prospect
from app.livewell.family_publish import (
    independence_score_from_payload,
    publish_assessment_to_family,
)
from app.livewell.rule_engine_defaults import (
    ecm_recommended,
    recommend_membership,
    risk_band_for_score,
)
from app.livewell.scoring import (
    cognitive_risk_from_payload,
    content_hash,
    effective_rubric,
    family_abroad_from_payload,
    lives_alone_from_payload,
    score_assessment,
)
from app.livewell.stored_config import read_stored_config
from app.models.home_safety_assessment import HomeSafetyAssessmentRecord
from app.models.tenant import Tenant
from app.models.user import User


logger = logging.getLogger(__name__)

# Record status for a draft that "Start a new one" replaced: hidden from lists.
DISCARDED = "discarded"

HISTORY_CAP = 10
LOCKED_MESSAGE = "Assessment is completed and locked. Reopen it to edit."


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _optional_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "y")


def _profile_flag(payload: dict, profile: dict, *keys: str):
    for key in keys:
        if payload.get(key) is not None:
            return payload.get(key)
        if profile.get(key) is not None:
            return profile.get(key)
    return None


def _score_payload_server_side(payload: dict, workflow_config: dict | None) -> dict:
    """Recompute Independence Score + domain scores from ratings and the effective rubric.

    The client-reported value is kept as ``clientReportedScore``. When the payload
    carries no ratings at all (legacy / imported records) the server cannot score
    it, so the client value is trusted and ``scoringSource`` says so.
    """
    client_score = independence_score_from_payload(payload)
    categories, rubric_source = effective_rubric(workflow_config)
    result = score_assessment(payload, categories)
    if result["rated_count"] == 0:
        return {
            **payload,
            "clientReportedScore": client_score,
            "scoringSource": "client",
        }
    server_score = int(result["independence_score"])
    if client_score is not None and abs(client_score - server_score) > 1:
        logger.warning(
            "assessment %s: client-reported Independence Score %s differs from server %s (rubric=%s)",
            payload.get("id"),
            client_score,
            server_score,
            rubric_source,
        )
    return {
        **payload,
        "independenceScore": server_score,
        "clientReportedScore": client_score,
        "familyDomainScores": result["domain_scores"],
        "domainScores": result["domain_score_map"],
        "criticalFindings": result["critical_unsafe"],
        "scoringSource": f"server:{rubric_source}",
        "serverScoredAt": _utc_now().isoformat(),
    }


def _stamp_rule_recommendations(payload: dict, workflow_config: dict | None = None) -> dict:
    """When completing, stamp membership/ECM/risk from spreadsheet rule_engine (or defaults)."""
    score = independence_score_from_payload(payload)
    if score is None:
        return payload
    profile = payload.get("residentProfile") if isinstance(payload.get("residentProfile"), dict) else {}
    re_cfg = read_stored_config(workflow_config or {}).get("rule_engine") or {}
    membership_rules = re_cfg.get("membership_rules") or None
    ecm_rules = re_cfg.get("ecm_rules") or None
    risk_rules = re_cfg.get("risk_rules") or None
    customised = bool(membership_rules or ecm_rules or risk_rules)

    lives_alone = lives_alone_from_payload(payload)
    family_abroad = family_abroad_from_payload(payload)
    family_requests_ecm = _optional_bool(
        _profile_flag(payload, profile, "familyRequestsEcm", "family_requests_ecm")
    )
    cognitive_risk = cognitive_risk_from_payload(payload)
    mobility_risk = _profile_flag(payload, profile, "mobilityRisk", "mobility_risk")
    health_complexity = _profile_flag(
        payload, profile, "healthComplexity", "health_complexity"
    )
    critical_unsafe = bool(payload.get("criticalFindings"))

    band = risk_band_for_score(score, risk_rules, critical_unsafe=critical_unsafe)
    return {
        **payload,
        "recommended_membership_id": recommend_membership(
            independence_score=score,
            lives_alone=lives_alone,
            family_abroad=family_abroad,
            mobility_risk=mobility_risk,
            cognitive_risk=cognitive_risk,
            health_complexity=health_complexity,
            rules=membership_rules,
        ),
        "ecm_recommended": ecm_recommended(
            independence_score=score,
            lives_alone=lives_alone,
            family_abroad=family_abroad,
            family_requests_ecm=family_requests_ecm,
            cognitive_risk=cognitive_risk,
            rules=ecm_rules,
        ),
        "risk_band": band.get("band"),
        "risk_band_label": band.get("label"),
        "risk_escalation_level": band.get("escalation_level"),
        "ruleEngineSource": "tenant" if customised else "default",
    }


def _version_entry(user: User, payload: dict, reason: str) -> dict:
    name = " ".join(
        part
        for part in (getattr(user, "first_name", ""), getattr(user, "last_name", ""))
        if part
    ).strip()
    return {
        "at": _utc_now().isoformat(),
        "by": user.id,
        "by_name": name or getattr(user, "email", ""),
        "payload_hash": content_hash(payload),
        "independenceScore": independence_score_from_payload(payload),
        "reason": reason,
    }



def _versions_list(raw) -> list:
    """Version history as a list. Some rows hold it as a JSON string ("[]")."""
    if isinstance(raw, str):
        import json

        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    return [v for v in (raw or []) if isinstance(v, dict)]

class HomeSafetyAssessmentService:

    @staticmethod
    def _tenant(db: Session, user: User) -> Tenant:
        tid = resolve_tenant_id(user)
        if tid is None:
            raise_bad_request("Tenant required")
        tenant = db.query(Tenant).filter(Tenant.id == tid).first()
        if not tenant:
            raise_bad_request("Tenant not found")
        assert_tenant_access(user, tenant.id)
        return tenant

    @staticmethod
    def list_assessments(db: Session, user: User, full: bool = False) -> list[dict]:
        tenant = HomeSafetyAssessmentService._tenant(db, user)
        rows = (
            db.query(HomeSafetyAssessmentRecord)
            .filter(
                HomeSafetyAssessmentRecord.tenant_id == tenant.id,
                # Drafts replaced by "Start a new one" (assessment_start.start).
                HomeSafetyAssessmentRecord.status != DISCARDED,
            )
            .order_by(HomeSafetyAssessmentRecord.updated_at.desc())
            .all()
        )
        out: list[dict] = []
        for row in rows:
            payload = row.payload or {}
            out.append(
                {
                    "assessment_id": row.assessment_id,
                    "status": row.status,
                    "client_first_name": payload.get("clientFirstName") or "",
                    "client_last_name": payload.get("clientLastName") or "",
                    "client_address": payload.get("clientAddress") or "",
                    "updated_at": row.updated_at.isoformat() if row.updated_at else "",
                    "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                    "prospect_id": row.prospect_id if row.prospect_id is not None else payload.get("prospectId"),
                    "elder_id": row.elder_id if row.elder_id is not None else payload.get("elderId"),
                    **({"payload": payload} if full else {}),
                }
            )
        return out

    @staticmethod
    def get_assessment(db: Session, user: User, assessment_id: str) -> dict:
        tenant = HomeSafetyAssessmentService._tenant(db, user)
        row = (
            db.query(HomeSafetyAssessmentRecord)
            .filter(
                HomeSafetyAssessmentRecord.tenant_id == tenant.id,
                HomeSafetyAssessmentRecord.assessment_id == assessment_id,
            )
            .first()
        )
        if not row:
            raise_not_found("Assessment not found")
        return HomeSafetyAssessmentService._row_to_dict(row)

    @staticmethod
    def upsert_assessment(db: Session, user: User, payload: dict) -> dict:
        tenant = HomeSafetyAssessmentService._tenant(db, user)
        assessment_id = str(payload.get("id") or "").strip()
        if not assessment_id:
            raise_bad_request("Assessment id is required")

        status = str(payload.get("status") or "draft").strip().lower()
        if status not in ("draft", "completed"):
            raise_bad_request("Invalid assessment status")

        payload = dict(payload)
        reopen = bool(payload.pop("reopen", False))

        if status == "completed":
            payload = _score_payload_server_side(payload, tenant.workflow_config)
            payload = _stamp_rule_recommendations(payload, tenant.workflow_config)

        completed_at = _parse_iso(payload.get("completedAt"))

        config_version = payload.get("configurationVersionId") or payload.get(
            "configuration_version_id"
        )
        if config_version is not None:
            config_version = str(config_version).strip() or None

        prospect_id, elder_id = HomeSafetyCustomerLink.resolve_customer(
            db,
            tenant.id,
            prospect_id=_optional_int(payload.get("prospectId")),
            elder_id=_optional_int(payload.get("elderId")),
            assessment_id=assessment_id,
            require=False,
        )
        if prospect_id or elder_id:
            payload = {
                **payload,
                "prospectId": prospect_id,
                "elderId": elder_id,
            }
            HomeSafetyCustomerLink.validate_assessment_photos(
                db,
                tenant.id,
                photos=payload.get("photos") or [],
                prospect_id=prospect_id,
                elder_id=elder_id,
            )

        row = (
            db.query(HomeSafetyAssessmentRecord)
            .filter(
                HomeSafetyAssessmentRecord.tenant_id == tenant.id,
                HomeSafetyAssessmentRecord.assessment_id == assessment_id,
            )
            .first()
        )
        if row is None:
            row = HomeSafetyAssessmentRecord(
                assessment_id=assessment_id,
                tenant_id=tenant.id,
                created_by_user_id=user.id,
                status=status,
                payload=payload,
                completed_at=completed_at,
                configuration_version_id=config_version,
                versions=[_version_entry(user, payload, "completed")] if status == "completed" else [],
                history=[],
            )
            db.add(row)
        else:
            previous = row.payload if isinstance(row.payload, dict) else {}
            # versions / history are large deferred text columns: load and rewrite them only
            # when this save adds to them (completing, or reopening a completed one). Parse
            # history like versions: list(<text>) used to split it into characters, so it
            # doubled on every save (272 MB rows; saves outlived the worker health-check).
            touch_history = row.status == "completed" or status == "completed"
            versions = _versions_list(row.versions) if touch_history else []
            history = _versions_list(row.history) if touch_history else []
            if row.status == "completed":
                # Locked: content changes need an explicit reopen from the client.
                # Ids, timestamps, photos, quote/PO and publish stamps are free.
                changed = content_hash(previous) != content_hash(payload) or status != "completed"
                if changed and not reopen:
                    raise_conflict(LOCKED_MESSAGE)
                if changed:
                    history.append(
                        {
                            "at": _utc_now().isoformat(),
                            "by": user.id,
                            "payload_hash": content_hash(previous),
                            "independenceScore": independence_score_from_payload(previous),
                            "payload": previous,
                        }
                    )
                    history = history[-HISTORY_CAP:]
                    versions.append(_version_entry(user, payload, "reopened"))
            elif status == "completed":
                versions.append(_version_entry(user, payload, "completed"))
            row.status = status
            row.payload = payload
            row.completed_at = completed_at
            if touch_history:
                row.versions = versions
                row.history = history
                flag_modified(row, "versions")
                flag_modified(row, "history")
            if config_version is not None:
                row.configuration_version_id = config_version

        if status == "completed":
            server_scored = str(payload.get("scoringSource") or "").startswith("server")
            row.server_score = (
                int(payload["independenceScore"])
                if server_scored and payload.get("independenceScore") is not None
                else None
            )
            row.client_reported_score = _optional_int(payload.get("clientReportedScore"))

        HomeSafetyCustomerLink.sync_assessment_customer_columns(row, payload)
        HomeSafetyCustomerLink.backfill_ai_jobs_for_assessment(
            db,
            tenant.id,
            assessment_id,
            prospect_id=row.prospect_id,
            elder_id=row.elder_id,
        )

        if status == "completed" and row.elder_id:
            publish_assessment_to_family(
                db,
                elder_id=row.elder_id,
                tenant_id=tenant.id,
                payload=payload,
            )

        db.commit()
        db.refresh(row)

        # After save: auto-convert prospect → elder (absorb lead) and publish for family.
        if status == "completed" and row.prospect_id and not row.elder_id:
            try:
                prospect_id = int(row.prospect_id)
                new_elder_id = ensure_elder_for_prospect(
                    db, user, prospect_id, auto_from_assessment=True
                )
                row.elder_id = new_elder_id
                row.prospect_id = None
                payload = {
                    **(row.payload or {}),
                    **payload,
                    "elderId": new_elder_id,
                    "prospectId": None,
                }
                row.payload = payload
                publish_assessment_to_family(
                    db,
                    elder_id=new_elder_id,
                    tenant_id=tenant.id,
                    payload=payload,
                )
                db.commit()
                db.refresh(row)
            except Exception:
                db.rollback()
                db.refresh(row)

        return HomeSafetyAssessmentService._row_to_dict(row)

    @staticmethod
    def delete_assessment(db: Session, user: User, assessment_id: str) -> None:
        from app.livewell.photo_service import HomeSafetyPhotoService

        tenant = HomeSafetyAssessmentService._tenant(db, user)
        row = (
            db.query(HomeSafetyAssessmentRecord)
            .filter(
                HomeSafetyAssessmentRecord.tenant_id == tenant.id,
                HomeSafetyAssessmentRecord.assessment_id == assessment_id,
            )
            .first()
        )
        if not row:
            raise_not_found("Assessment not found")

        HomeSafetyPhotoService.delete_for_assessment(
            db,
            tenant_id=tenant.id,
            assessment_id=assessment_id,
            payload=row.payload if isinstance(row.payload, dict) else None,
        )
        db.delete(row)
        db.commit()

    @staticmethod
    def _row_to_dict(row: HomeSafetyAssessmentRecord) -> dict:
        return {
            "assessment_id": row.assessment_id,
            "status": row.status,
            "payload": row.payload or {},
            "prospect_id": row.prospect_id,
            "elder_id": row.elder_id,
            "configuration_version_id": row.configuration_version_id,
            "updated_at": row.updated_at.isoformat() if row.updated_at else "",
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "locked": row.status == "completed",
            "server_score": row.server_score,
            "client_reported_score": row.client_reported_score,
            "versions": _versions_list(row.versions),
        }
