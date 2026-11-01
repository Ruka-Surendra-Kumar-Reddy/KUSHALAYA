"""Recruitment pipeline polish — auto-stage, skill mapping, placement fit."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.pipeline_constants import ACTIVITY_STAGE_CHANGE
from app.core.rbac import resolve_tenant_id
from app.core.responses import raise_bad_request
from app.models.assignment import Assignment
from app.models.caregiver import Caregiver
from app.models.caregiver_prospect import CaregiverProspect
from app.models.caregiver_skill import CaregiverSkill
from app.models.elder import Elder
from app.models.elder_requirement import ElderRequirement
from app.models.skill import Skill
from app.models.user import User
from app.services.auto_scheduling_service import AutoSchedulingService
from app.services.matching.scoring import score_caregiver
from app.services.prospect_service import ProspectService
from app.services.scheduling_service import SchedulingService

SCREENING_SCORE = 70.0
INTERVIEW_SCORE = 85.0


def _normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


class RecruitmentPlacementService:

    @staticmethod
    def _resume_fields(prospect: CaregiverProspect) -> dict:
        parsed = prospect.resume_parsed_json or {}
        return parsed.get("fields") or {}

    @classmethod
    def match_resume_skill_ids(
        cls,
        db: Session,
        fields: dict,
    ) -> list[tuple[int, bool, str | None]]:
        """Map parsed skills/certifications to tenant skill catalog."""
        labels: list[tuple[str, bool]] = []
        for skill in fields.get("skills") or []:
            if skill:
                labels.append((str(skill), False))
        for cert in fields.get("certifications") or []:
            if cert:
                labels.append((str(cert), True))

        if not labels:
            return []

        catalog = db.query(Skill).all()
        matched: list[tuple[int, bool, str | None]] = []
        used: set[int] = set()

        for label, is_cert in labels:
            norm = _normalize_label(label)
            if not norm:
                continue
            for skill in catalog:
                if skill.id in used:
                    continue
                names = [
                    _normalize_label(skill.name),
                    _normalize_label(skill.code.replace("_", " ")),
                    _normalize_label(skill.code),
                ]
                if any(n and (n in norm or norm in n) for n in names):
                    matched.append(
                        (skill.id, is_cert, label if is_cert else None)
                    )
                    used.add(skill.id)
                    break

        return matched

    @classmethod
    def apply_resume_skills_to_caregiver(
        cls,
        db: Session,
        caregiver_id: int,
        prospect: CaregiverProspect,
    ) -> int:
        fields = cls._resume_fields(prospect)
        mappings = cls.match_resume_skill_ids(db, fields)
        if not mappings:
            return 0

        existing = {
            row.skill_id
            for row in db.query(CaregiverSkill.skill_id)
            .filter(CaregiverSkill.caregiver_id == caregiver_id)
            .all()
        }

        added = 0
        for skill_id, certified, cert_ref in mappings:
            if skill_id in existing:
                continue
            db.add(
                CaregiverSkill(
                    caregiver_id=caregiver_id,
                    skill_id=skill_id,
                    experience_years=prospect.years_experience,
                    certified=certified,
                    certification_reference=cert_ref,
                )
            )
            added += 1
        return added

    @classmethod
    def resume_custom_attributes(cls, prospect: CaregiverProspect) -> dict:
        fields = cls._resume_fields(prospect)
        attrs: dict = {}
        langs = fields.get("languages") or []
        if langs:
            attrs["languages"] = langs
        care_types = fields.get("care_types") or []
        if care_types:
            attrs["availability"] = {"care_type": care_types[0]}
        return attrs

    @classmethod
    def maybe_advance_stage_from_score(
        cls,
        db: Session,
        prospect: CaregiverProspect,
        score: float,
        actor: User,
    ) -> str | None:
        """Auto-advance APPLIED prospects based on resume score."""
        if prospect.stage != "APPLIED" or prospect.status != "OPEN":
            return None

        new_stage: str | None = None
        if score >= INTERVIEW_SCORE:
            new_stage = "INTERVIEW"
        elif score >= SCREENING_SCORE:
            new_stage = "SCREENING"

        if not new_stage:
            return None

        old_stage = prospect.stage
        prospect.stage = new_stage
        ProspectService._log_activity(
            db,
            tenant_id=prospect.tenant_id,
            caregiver_prospect_id=prospect.id,
            activity_type=ACTIVITY_STAGE_CHANGE,
            body=(
                f"Auto-advanced to {new_stage} "
                f"(resume score {score:.0f})"
            ),
            actor=actor,
            metadata={
                "from": old_stage,
                "to": new_stage,
                "auto": True,
                "resume_score": score,
            },
        )
        return new_stage

    @classmethod
    def _prospect_as_caregiver(cls, prospect: CaregiverProspect) -> Caregiver:
        fields = cls._resume_fields(prospect)
        attrs = cls.resume_custom_attributes(prospect)
        return Caregiver(
            id=0,
            tenant_id=prospect.tenant_id,
            first_name=prospect.first_name,
            last_name=prospect.last_name,
            years_experience=(
                prospect.years_experience or fields.get("years_experience")
            ),
            custom_attributes=attrs or None,
            status="ACTIVE",
        )

    @classmethod
    def _synthetic_skills(
        cls,
        db: Session,
        fields: dict,
    ) -> list[CaregiverSkill]:
        return [
            CaregiverSkill(
                caregiver_id=0,
                skill_id=skill_id,
                certified=certified,
                certification_reference=cert_ref,
            )
            for skill_id, certified, cert_ref in cls.match_resume_skill_ids(
                db,
                fields,
            )
        ]

    @classmethod
    def suggest_placements(
        cls,
        db: Session,
        prospect: CaregiverProspect,
        user: User,
        *,
        limit: int = 5,
        min_score: float = 40.0,
    ) -> dict:
        tid = resolve_tenant_id(user)
        if tid is None:
            raise_bad_request("Tenant context required")
        if prospect.tenant_id != tid and user.role != "SYSTEM_ADMIN":
            raise_bad_request("Prospect not in your tenant")

        uncovered_rows = AutoSchedulingService._uncovered_clients(db, tid)
        uncovered_ids = {r["elder_id"] for r in uncovered_rows}

        assigned_elder_ids = {
            row[0]
            for row in db.query(Assignment.elder_id)
            .filter(
                Assignment.tenant_id == tid,
                Assignment.status == "ACTIVE",
            )
            .all()
        }

        elder_query = db.query(Elder).filter(Elder.tenant_id == tid)
        if assigned_elder_ids:
            elder_query = elder_query.filter(Elder.id.in_(assigned_elder_ids))
        elders = elder_query.all()

        if not elders and uncovered_rows:
            elders = (
                db.query(Elder)
                .filter(
                    Elder.tenant_id == tid,
                    Elder.id.in_([r["elder_id"] for r in uncovered_rows]),
                )
                .all()
            )

        caregiver = cls._prospect_as_caregiver(prospect)
        fields = cls._resume_fields(prospect)
        synthetic_skills = cls._synthetic_skills(db, fields)

        suggestions: list[dict] = []
        for elder in elders:
            requirements = (
                db.query(ElderRequirement)
                .filter(ElderRequirement.elder_id == elder.id)
                .all()
            )
            skill_ids = {r.skill_id for r in requirements}
            skills_by_id = {
                s.id: s
                for s in db.query(Skill).filter(Skill.id.in_(skill_ids)).all()
            } if skill_ids else {}

            scored = score_caregiver(
                elder,
                caregiver,
                requirements,
                synthetic_skills,
                skills_by_id,
                [],
                None,
                0,
            )
            if scored["match_score"] < min_score:
                continue

            suggestions.append(
                {
                    "elder_id": elder.id,
                    "elder_name": SchedulingService._display_name(
                        elder.first_name,
                        elder.last_name,
                    ),
                    "match_score": scored["match_score"],
                    "reasons": scored["reasons"][:6],
                    "uncovered": elder.id in uncovered_ids,
                    "care_level": elder.care_level,
                }
            )

        suggestions.sort(
            key=lambda s: (-s["match_score"], not s["uncovered"]),
        )

        return {
            "prospect_id": prospect.id,
            "prospect_name": SchedulingService._display_name(
                prospect.first_name,
                prospect.last_name,
            ),
            "resume_score": prospect.resume_score,
            "uncovered_clients": len(uncovered_rows),
            "suggestions": suggestions[:limit],
        }
