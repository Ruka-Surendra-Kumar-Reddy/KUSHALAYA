from datetime import date

from sqlalchemy.orm import Session

from app.models.caregiver import Caregiver
from app.models.caregiver_certification import CaregiverCertification
from app.models.caregiver_identity import CaregiverIdentity
from app.models.training_program import CaregiverProgramEnrollment, TrainingProgram


def _band(score: float) -> str:
    if score >= 90:
        return "GOLD"
    if score >= 75:
        return "SILVER"
    if score >= 60:
        return "BRONZE"
    return "NOT_READY"


class ReadinessService:

    @staticmethod
    def _academy_attrs(caregiver: Caregiver) -> dict:
        attrs = caregiver.custom_attributes or {}
        academy = attrs.get("academy")
        return academy if isinstance(academy, dict) else {}

    @staticmethod
    def verification_points(db: Session, caregiver: Caregiver) -> float:
        points = 0.0
        identity = (
            db.query(CaregiverIdentity)
            .filter(CaregiverIdentity.caregiver_id == caregiver.id)
            .first()
        )
        if identity and identity.verification_status in (
            "SUBMITTED",
            "VERIFIED",
            "APPROVED",
        ):
            points += 10
        if identity and identity.user_confirmed_at:
            points += 5

        if (caregiver.police_verification_status or "").upper() == "VERIFIED":
            points += 5

        today = date.today()
        verified_certs = (
            db.query(CaregiverCertification)
            .filter(
                CaregiverCertification.caregiver_id == caregiver.id,
                CaregiverCertification.verification_status == "VERIFIED",
            )
            .all()
        )
        if verified_certs:
            points += 5
            if any(
                c.expiry_date is None or c.expiry_date >= today for c in verified_certs
            ):
                points += 5

        return min(25.0, points)

    @staticmethod
    def training_points(db: Session, caregiver: Caregiver) -> float:
        enrollments = (
            db.query(CaregiverProgramEnrollment)
            .filter(CaregiverProgramEnrollment.caregiver_id == caregiver.id)
            .all()
        )
        completed = [e for e in enrollments if e.status == "COMPLETED"]
        if not completed:
            return 0.0

        programs = {
            p.id: p
            for p in db.query(TrainingProgram)
            .filter(
                TrainingProgram.id.in_({e.program_id for e in completed})
            )
            .all()
        }

        points = 0.0
        for enrollment in completed:
            program = programs.get(enrollment.program_id)
            if program and program.code == "FOUNDATION_CAREGIVER":
                points += 12.0
            else:
                points += 4.0

        return min(25.0, points)

    @staticmethod
    def assessment_points(db: Session, caregiver: Caregiver) -> float:
        enrollments = (
            db.query(CaregiverProgramEnrollment)
            .filter(
                CaregiverProgramEnrollment.caregiver_id == caregiver.id,
                CaregiverProgramEnrollment.status == "COMPLETED",
            )
            .all()
        )
        scores = [e.assessment_score for e in enrollments if e.assessment_score is not None]
        if scores:
            avg = sum(scores) / len(scores)
            base = min(20.0, 20.0 * (avg / 100.0))
            # Each additional completed program adds visible progress toward the cap.
            bonus = min(20.0 - base, max(0, len(scores) - 1) * 3.0)
            return min(20.0, base + bonus)

        academy = ReadinessService._academy_attrs(caregiver)
        stub = academy.get("assessment_score")
        if stub is not None:
            return min(20.0, float(stub))
        return 0.0

    @staticmethod
    def practical_points(caregiver: Caregiver) -> float:
        academy = ReadinessService._academy_attrs(caregiver)
        stub = academy.get("practical_score")
        if stub is not None:
            return min(20.0, float(stub))
        return 0.0

    @staticmethod
    def conduct_points(caregiver: Caregiver) -> float:
        academy = ReadinessService._academy_attrs(caregiver)
        stub = academy.get("conduct_score")
        if stub is not None:
            return min(10.0, float(stub))
        if (caregiver.police_verification_status or "").upper() == "VERIFIED":
            return 5.0
        return 0.0

    @staticmethod
    def compute(db: Session, caregiver: Caregiver) -> dict:
        breakdown = {
            "verification": round(
                ReadinessService.verification_points(db, caregiver), 1
            ),
            "training": round(ReadinessService.training_points(db, caregiver), 1),
            "assessment": round(ReadinessService.assessment_points(db, caregiver), 1),
            "practical": round(ReadinessService.practical_points(caregiver), 1),
            "conduct": round(ReadinessService.conduct_points(caregiver), 1),
        }
        total = round(sum(breakdown.values()), 1)
        recommendations: list[str] = []

        if breakdown["verification"] < 20:
            recommendations.append("Complete identity and police verification")
        if breakdown["training"] < 15:
            recommendations.append("Enroll in Foundation Caregiver Program")
        if breakdown["assessment"] < 10:
            recommendations.append("Complete program assessments")
        if breakdown["practical"] < 10:
            recommendations.append("Record practical demonstration score")
        if not recommendations and total < 90:
            recommendations.append("Complete Dementia Awareness Program")

        return {
            "readiness_score": total,
            "readiness_band": _band(total),
            "breakdown": breakdown,
            "recommendations": recommendations,
        }

    @staticmethod
    def employability(db: Session, caregiver: Caregiver) -> dict:
        readiness = ReadinessService.compute(db, caregiver)
        today = date.today()

        cert_pts = 0.0
        ext = (
            db.query(CaregiverCertification)
            .filter(
                CaregiverCertification.caregiver_id == caregiver.id,
                CaregiverCertification.verification_status == "VERIFIED",
            )
            .all()
        )
        for c in ext:
            if c.expiry_date is None or c.expiry_date >= today:
                cert_pts = 25.0
                break

        readiness_pts = min(20.0, readiness["readiness_score"] * 0.2)
        verification_pts = min(
            20.0, readiness["breakdown"]["verification"] * 0.8
        )
        exp_years = caregiver.years_experience or 0
        experience_pts = min(15.0, exp_years * 3.0)

        attrs = caregiver.custom_attributes or {}
        langs = attrs.get("languages") or []
        language_pts = 10.0 if isinstance(langs, list) and len(langs) >= 1 else 5.0

        market_pts = 5.0
        if readiness["readiness_band"] in ("GOLD", "SILVER"):
            market_pts = 10.0

        total = round(
            cert_pts
            + readiness_pts
            + verification_pts
            + experience_pts
            + language_pts
            + market_pts,
            1,
        )

        return {
            "employability_score": min(100.0, total),
            "recognized_certification": cert_pts,
            "readiness_component": readiness_pts,
            "verification_component": verification_pts,
            "experience": experience_pts,
            "language": language_pts,
            "market_demand": market_pts,
        }

    @staticmethod
    def update_stub_scores(
        db: Session,
        caregiver: Caregiver,
        practical_score: float | None,
        conduct_score: float | None,
    ) -> Caregiver:
        attrs = dict(caregiver.custom_attributes or {})
        academy = dict(attrs.get("academy") or {})
        if practical_score is not None:
            academy["practical_score"] = practical_score
        if conduct_score is not None:
            academy["conduct_score"] = conduct_score
        attrs["academy"] = academy
        caregiver.custom_attributes = attrs
        db.commit()
        db.refresh(caregiver)
        return caregiver
