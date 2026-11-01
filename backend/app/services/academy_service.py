from datetime import date

from sqlalchemy.orm import Session

from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.models.caregiver import Caregiver
from app.models.caregiver_certification import CaregiverCertification
from app.models.qualification_pack import QualificationPack
from app.models.training_program import CaregiverProgramEnrollment, TrainingProgram
from app.models.user import User
from app.schemas.academy import (
    AcademyStubUpdate,
    CertificationCreate,
    CertificationUpdate,
    CompleteProgramRequest,
    EnrollProgramRequest,
)
from app.services.audit_service import AuditService
from app.services.readiness_service import ReadinessService


class AcademyService:

    @staticmethod
    def _caregiver(db: Session, caregiver_id: int, user: User) -> Caregiver:
        row = db.query(Caregiver).filter(Caregiver.id == caregiver_id).first()
        if not row:
            raise_not_found("Caregiver not found")
        assert_tenant_access(user, row.tenant_id)
        return row

    @staticmethod
    def list_qualification_packs(db: Session) -> list[QualificationPack]:
        return (
            db.query(QualificationPack)
            .filter(QualificationPack.status == "ACTIVE")
            .order_by(QualificationPack.qualification_pack_code)
            .all()
        )

    @staticmethod
    def list_training_programs(db: Session) -> list[TrainingProgram]:
        return (
            db.query(TrainingProgram)
            .filter(TrainingProgram.status == "ACTIVE")
            .order_by(TrainingProgram.code)
            .all()
        )

    @staticmethod
    def list_certifications(
        db: Session,
        caregiver_id: int,
        user: User,
    ) -> list[dict]:
        caregiver = AcademyService._caregiver(db, caregiver_id, user)
        today = date.today()
        rows = (
            db.query(CaregiverCertification)
            .filter(CaregiverCertification.caregiver_id == caregiver.id)
            .order_by(CaregiverCertification.created_at.desc())
            .all()
        )
        out = []
        for r in rows:
            expired = (
                r.expiry_date is not None
                and r.expiry_date < today
                and r.verification_status in ("VERIFIED", "EXPIRED")
            )
            out.append({"row": r, "is_expired": expired})
        return out

    @staticmethod
    def create_certification(
        db: Session,
        caregiver_id: int,
        data: CertificationCreate,
        user: User,
    ) -> CaregiverCertification:
        caregiver = AcademyService._caregiver(db, caregiver_id, user)
        row = CaregiverCertification(
            tenant_id=caregiver.tenant_id,
            caregiver_id=caregiver.id,
            certification_name=data.certification_name,
            qualification_pack_code=data.qualification_pack_code,
            issuing_body=data.issuing_body,
            issue_date=data.issue_date,
            expiry_date=data.expiry_date,
            certificate_number=data.certificate_number,
            certificate_url=data.certificate_url,
            document_id=data.document_id,
            verification_status="PENDING",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def update_certification(
        db: Session,
        cert_id: int,
        data: CertificationUpdate,
        user: User,
    ) -> CaregiverCertification:
        row = db.query(CaregiverCertification).filter(CaregiverCertification.id == cert_id).first()
        if not row:
            raise_not_found("Certification not found")
        assert_tenant_access(user, row.tenant_id)

        for field in (
            "certification_name",
            "issuing_body",
            "qualification_pack_code",
            "issue_date",
            "expiry_date",
            "certificate_number",
            "certificate_url",
        ):
            val = getattr(data, field)
            if val is not None:
                setattr(row, field, val)

        if data.verification_status is not None:
            status = data.verification_status.upper()
            if status not in {"PENDING", "VERIFIED", "REJECTED", "EXPIRED"}:
                raise_bad_request("Invalid verification_status")
            row.verification_status = status
            AuditService.log(
                db,
                tenant_id=row.tenant_id,
                user_id=user.id,
                entity_type="caregiver_certification",
                entity_id=row.id,
                action=f"cert_{status.lower()}",
            )

        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def list_enrollments(db: Session, caregiver_id: int, user: User) -> list[dict]:
        caregiver = AcademyService._caregiver(db, caregiver_id, user)
        rows = (
            db.query(CaregiverProgramEnrollment, TrainingProgram)
            .join(TrainingProgram, TrainingProgram.id == CaregiverProgramEnrollment.program_id)
            .filter(CaregiverProgramEnrollment.caregiver_id == caregiver.id)
            .all()
        )
        return [
            {
                "id": e.id,
                "program_id": p.id,
                "program_code": p.code,
                "program_name": p.name,
                "status": e.status,
                "assessment_score": e.assessment_score,
            }
            for e, p in rows
        ]

    @staticmethod
    def enroll(
        db: Session,
        caregiver_id: int,
        data: EnrollProgramRequest,
        user: User,
    ) -> CaregiverProgramEnrollment:
        caregiver = AcademyService._caregiver(db, caregiver_id, user)
        program = (
            db.query(TrainingProgram)
            .filter(TrainingProgram.code == data.program_code.upper())
            .first()
        )
        if not program:
            raise_not_found("Training program not found")

        existing = (
            db.query(CaregiverProgramEnrollment)
            .filter(
                CaregiverProgramEnrollment.caregiver_id == caregiver.id,
                CaregiverProgramEnrollment.program_id == program.id,
            )
            .first()
        )
        if existing:
            return existing

        row = CaregiverProgramEnrollment(
            tenant_id=caregiver.tenant_id,
            caregiver_id=caregiver.id,
            program_id=program.id,
            status="ENROLLED",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def complete_program(
        db: Session,
        caregiver_id: int,
        program_code: str,
        data: CompleteProgramRequest,
        user: User,
    ) -> CaregiverProgramEnrollment:
        caregiver = AcademyService._caregiver(db, caregiver_id, user)
        program = (
            db.query(TrainingProgram)
            .filter(TrainingProgram.code == program_code.upper())
            .first()
        )
        if not program:
            raise_not_found("Training program not found")

        row = (
            db.query(CaregiverProgramEnrollment)
            .filter(
                CaregiverProgramEnrollment.caregiver_id == caregiver.id,
                CaregiverProgramEnrollment.program_id == program.id,
            )
            .first()
        )
        if not row:
            row = CaregiverProgramEnrollment(
                tenant_id=caregiver.tenant_id,
                caregiver_id=caregiver.id,
                program_id=program.id,
                status="ENROLLED",
            )
            db.add(row)
            db.flush()

        row.status = "COMPLETED"
        row.assessment_score = data.assessment_score
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def marketplace(
        db: Session,
        user: User,
        *,
        readiness_min: float | None = None,
        band: str | None = None,
        qp_code: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        query = db.query(Caregiver).filter(Caregiver.status == "ACTIVE")
        tid = resolve_tenant_id(user)
        if tid is not None:
            query = query.filter(Caregiver.tenant_id == tid)

        caregivers = query.limit(500).all()
        results: list[dict] = []

        for cg in caregivers:
            if qp_code:
                has_qp = (
                    db.query(CaregiverCertification)
                    .filter(
                        CaregiverCertification.caregiver_id == cg.id,
                        CaregiverCertification.qualification_pack_code == qp_code,
                        CaregiverCertification.verification_status == "VERIFIED",
                    )
                    .first()
                )
                if not has_qp:
                    continue

            readiness = ReadinessService.compute(db, cg)
            if readiness_min is not None and readiness["readiness_score"] < readiness_min:
                continue
            if band and readiness["readiness_band"] != band.upper():
                continue

            emp = ReadinessService.employability(db, cg)
            attrs = cg.custom_attributes or {}
            langs = attrs.get("languages")
            lang_list = langs if isinstance(langs, list) else []

            id_status = "Pending"
            if (cg.police_verification_status or "").upper() == "VERIFIED":
                id_status = "Verified"

            results.append(
                {
                    "id": cg.id,
                    "first_name": cg.first_name,
                    "last_name": cg.last_name,
                    "years_experience": cg.years_experience,
                    "readiness_score": readiness["readiness_score"],
                    "readiness_band": readiness["readiness_band"],
                    "employability_score": emp["employability_score"],
                    "verification_status_summary": id_status,
                    "languages": [str(x) for x in lang_list],
                }
            )

        results.sort(key=lambda x: x["employability_score"], reverse=True)
        return results[:limit]
