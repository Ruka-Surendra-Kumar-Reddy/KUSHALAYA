"""Hard-delete a tenant and all tenant-scoped rows (pilot cleanup).

SafeHomeOps / LiveWell360 may not ship every workforce model — missing modules
are skipped. Global catalog product images are preserved.
"""

from __future__ import annotations

import importlib
from typing import Any

from sqlalchemy import delete, inspect, or_, select
from sqlalchemy.orm import Session

from app.core.responses import raise_bad_request, raise_not_found
from app.core.storage import get_storage
from app.models.audit_log import AuditLog
from app.models.caregiver import Caregiver
from app.models.caregiver_prospect import CaregiverProspect
from app.models.document import Document
from app.models.elder import Elder
from app.models.elder_location import ElderLocation
from app.models.elder_prospect import ElderProspect
from app.models.pipeline_activity import PipelineActivity
from app.models.tenant import Tenant as TenantModel
from app.models.user import User
from app.models.workflow_event import WorkflowEvent
from app.models.workflow_task import WorkflowTask

PROTECTED_TENANT_NAMES = frozenset({"Sunrise Elder Care"})


def _load(module: str, name: str) -> Any | None:
    try:
        return getattr(importlib.import_module(module), name)
    except (ImportError, ModuleNotFoundError, AttributeError):
        return None


class TenantPurgeService:

    @staticmethod
    def delete_tenant(
        db: Session,
        tenant_id: int,
        confirm_name: str,
        *,
        allow_protected: bool = False,
    ) -> dict:
        tenant = db.query(TenantModel).filter(TenantModel.id == tenant_id).first()
        if not tenant:
            raise_not_found("Tenant not found")
        if tenant.name in PROTECTED_TENANT_NAMES and not allow_protected:
            raise_bad_request(
                f"Cannot delete protected tenant '{tenant.name}'. "
                "Use --allow-protected on delete_tenant CLI or reset_sunrise_demo, "
                "or remove the name from PROTECTED_TENANT_NAMES."
            )
        if confirm_name.strip() != tenant.name:
            raise_bad_request(
                "confirm_name must exactly match the tenant name (case-sensitive)"
            )

        counts: dict[str, int] = {}
        tid = tenant_id
        storage = get_storage()
        existing_tables = set(inspect(db.get_bind()).get_table_names())

        elder_ids = select(Elder.id).where(Elder.tenant_id == tid)
        caregiver_ids = select(Caregiver.id).where(Caregiver.tenant_id == tid)

        def bump(key: str, n: int) -> None:
            if n:
                counts[key] = counts.get(key, 0) + n

        def purge(key: str, model: Any, *criterion: Any) -> None:
            if model is None or getattr(model, "__tablename__", None) not in existing_tables:
                return
            bump(key, db.execute(delete(model).where(*criterion)).rowcount)

        def can_purge(model: Any, *columns: str) -> bool:
            if model is None:
                return False
            if getattr(model, "__tablename__", None) not in existing_tables:
                return False
            return all(hasattr(model, col) for col in columns)

        # --- LiveWell / SafeHome (always when tables exist) ---
        HomeSafetyAIJob = _load("app.models.home_safety_ai_job", "HomeSafetyAIJob")
        HomeSafetyVisionAnalysis = _load(
            "app.models.home_safety_vision_analysis", "HomeSafetyVisionAnalysis"
        )
        HomeSafetyAssessment = _load(
            "app.models.home_safety_assessment", "HomeSafetyAssessmentRecord"
        )
        purge(
            "home_safety_vision_analyses",
            HomeSafetyVisionAnalysis,
            HomeSafetyVisionAnalysis.tenant_id == tid if HomeSafetyVisionAnalysis else True,
        )
        purge(
            "home_safety_ai_jobs",
            HomeSafetyAIJob,
            HomeSafetyAIJob.tenant_id == tid if HomeSafetyAIJob else True,
        )
        purge(
            "home_safety_assessments",
            HomeSafetyAssessment,
            HomeSafetyAssessment.tenant_id == tid if HomeSafetyAssessment else True,
        )

        # --- Optional workforce / care tables ---
        RecommendationFeedback = _load(
            "app.models.recommendation_feedback", "RecommendationFeedback"
        )
        MatchResult = _load("app.models.match_result", "MatchResult")
        MatchRun = _load("app.models.match_run", "MatchRun")
        Match = _load("app.models.match", "Match")
        ElderRequirement = _load("app.models.elder_requirement", "ElderRequirement")
        FamilyServiceRequest = _load(
            "app.models.family_service_request", "FamilyServiceRequest"
        )
        LeaveRequest = _load("app.models.leave_request", "LeaveRequest")
        MonitoringAlert = _load("app.models.monitoring_alert", "MonitoringAlert")
        Incident = _load("app.models.incident", "Incident")
        CameraEvent = _load("app.models.camera_event", "CameraEvent")
        Invoice = _load("app.models.invoice", "Invoice")
        InvoiceLine = _load("app.models.invoice", "InvoiceLine")
        ElderBillingRate = _load("app.models.invoice", "ElderBillingRate")
        PayrollRun = _load("app.models.payroll_run", "PayrollRun")
        PayrollLine = _load("app.models.payroll_run", "PayrollLine")
        PayrollDeduction = _load("app.models.payroll_deduction", "PayrollDeduction")
        AttendanceAlert = _load("app.models.attendance_alert", "AttendanceAlert")
        AttendanceRecord = _load("app.models.attendance_record", "AttendanceRecord")
        ShiftSwapRequest = _load("app.models.shift_swap_request", "ShiftSwapRequest")
        VisitCareNote = _load("app.models.visit_care_note", "VisitCareNote")
        VisitChecklistLog = _load("app.models.visit_checklist_log", "VisitChecklistLog")
        Visit = _load("app.models.visit", "Visit")
        CarePlan = _load("app.models.care_plan", "CarePlan")
        CarePlanActivity = _load("app.models.care_plan", "CarePlanActivity")
        CarePlanActivityLog = _load("app.models.care_plan", "CarePlanActivityLog")
        CaregiverLocationEvent = _load(
            "app.models.caregiver_location_event", "CaregiverLocationEvent"
        )
        PlacementHistory = _load("app.models.placement_history", "PlacementHistory")
        Assignment = _load("app.models.assignment", "Assignment")
        CaregiverProgramEnrollment = _load(
            "app.models.training_program", "CaregiverProgramEnrollment"
        )
        CaregiverCertification = _load(
            "app.models.caregiver_certification", "CaregiverCertification"
        )
        CaregiverIdentity = _load("app.models.caregiver_identity", "CaregiverIdentity")
        CaregiverPayRate = _load("app.models.caregiver_pay_rate", "CaregiverPayRate")
        CaregiverRating = _load("app.models.caregiver_rating", "CaregiverRating")
        CaregiverDevice = _load("app.models.caregiver_device", "CaregiverDevice")
        CaregiverSkill = _load("app.models.caregiver_skill", "CaregiverSkill")
        USWorkforceCompliance = _load(
            "app.models.us_workforce_compliance", "USWorkforceCompliance"
        )
        PredictionResult = _load("app.models.prediction_result", "PredictionResult")
        ElderNotification = _load("app.models.elder_notification", "ElderNotification")
        ElderMessage = _load("app.models.elder_message", "ElderMessage")
        MonitoringConsent = _load("app.models.monitoring_consent", "MonitoringConsent")

        match_run_ids = None
        if MatchRun is not None and MatchRun.__tablename__ in existing_tables:
            match_run_ids = select(MatchRun.id).where(MatchRun.tenant_id == tid)
        match_result_ids = None
        if (
            MatchResult is not None
            and match_run_ids is not None
            and MatchResult.__tablename__ in existing_tables
        ):
            match_result_ids = select(MatchResult.id).where(
                MatchResult.match_run_id.in_(match_run_ids)
            )

        if RecommendationFeedback is not None and match_result_ids is not None:
            purge(
                "recommendation_feedback",
                RecommendationFeedback,
                RecommendationFeedback.match_result_id.in_(match_result_ids),
            )
        if MatchResult is not None and match_run_ids is not None:
            purge(
                "match_results",
                MatchResult,
                MatchResult.match_run_id.in_(match_run_ids),
            )
        if MatchRun is not None:
            purge("match_runs", MatchRun, MatchRun.tenant_id == tid)
        if Match is not None:
            purge(
                "matches",
                Match,
                or_(
                    Match.elder_id.in_(elder_ids),
                    Match.caregiver_id.in_(caregiver_ids),
                ),
            )
        if (
            ElderRequirement is not None
            and getattr(ElderRequirement, "__tablename__", None) in existing_tables
            and hasattr(ElderRequirement, "elder_id")
        ):
            purge(
                "elder_requirements",
                ElderRequirement,
                ElderRequirement.elder_id.in_(elder_ids),
            )

        purge("workflow_tasks", WorkflowTask, WorkflowTask.tenant_id == tid)
        purge("workflow_events", WorkflowEvent, WorkflowEvent.tenant_id == tid)
        purge("pipeline_activities", PipelineActivity, PipelineActivity.tenant_id == tid)
        if FamilyServiceRequest is not None:
            purge(
                "family_service_requests",
                FamilyServiceRequest,
                FamilyServiceRequest.tenant_id == tid,
            )
        if LeaveRequest is not None:
            purge("leave_requests", LeaveRequest, LeaveRequest.tenant_id == tid)
        if MonitoringAlert is not None:
            purge("monitoring_alerts", MonitoringAlert, MonitoringAlert.tenant_id == tid)
        if can_purge(Incident, "tenant_id"):
            purge("incidents", Incident, Incident.tenant_id == tid)
        if can_purge(CameraEvent, "tenant_id"):
            purge("camera_events", CameraEvent, CameraEvent.tenant_id == tid)

        invoice_ids = None
        if can_purge(Invoice, "id", "tenant_id"):
            invoice_ids = select(Invoice.id).where(Invoice.tenant_id == tid)
        if can_purge(InvoiceLine, "invoice_id") and invoice_ids is not None:
            purge("invoice_lines", InvoiceLine, InvoiceLine.invoice_id.in_(invoice_ids))
        if can_purge(Invoice, "tenant_id"):
            purge("invoices", Invoice, Invoice.tenant_id == tid)
        if can_purge(ElderBillingRate, "tenant_id"):
            purge(
                "elder_billing_rates",
                ElderBillingRate,
                ElderBillingRate.tenant_id == tid,
            )

        payroll_run_ids = None
        if PayrollRun is not None and PayrollRun.__tablename__ in existing_tables:
            payroll_run_ids = select(PayrollRun.id).where(PayrollRun.tenant_id == tid)
        if PayrollDeduction is not None and payroll_run_ids is not None:
            purge(
                "payroll_deductions",
                PayrollDeduction,
                PayrollDeduction.payroll_run_id.in_(payroll_run_ids),
            )
        if PayrollLine is not None and payroll_run_ids is not None:
            purge(
                "payroll_lines",
                PayrollLine,
                PayrollLine.payroll_run_id.in_(payroll_run_ids),
            )
        if PayrollRun is not None:
            purge("payroll_runs", PayrollRun, PayrollRun.tenant_id == tid)

        if AttendanceAlert is not None:
            purge("attendance_alerts", AttendanceAlert, AttendanceAlert.tenant_id == tid)
        if ShiftSwapRequest is not None:
            purge(
                "shift_swap_requests",
                ShiftSwapRequest,
                ShiftSwapRequest.tenant_id == tid,
            )
        if VisitCareNote is not None:
            purge("visit_care_notes", VisitCareNote, VisitCareNote.tenant_id == tid)
        if VisitChecklistLog is not None:
            purge(
                "visit_checklist_logs",
                VisitChecklistLog,
                VisitChecklistLog.tenant_id == tid,
            )
        if Visit is not None:
            purge("visits", Visit, Visit.tenant_id == tid)
        if AttendanceRecord is not None:
            purge(
                "attendance_records",
                AttendanceRecord,
                AttendanceRecord.tenant_id == tid,
            )

        care_plan_ids = None
        if CarePlan is not None and CarePlan.__tablename__ in existing_tables:
            care_plan_ids = select(CarePlan.id).where(CarePlan.tenant_id == tid)
        if CarePlanActivityLog is not None:
            purge(
                "care_plan_activity_logs",
                CarePlanActivityLog,
                CarePlanActivityLog.tenant_id == tid,
            )
        if CarePlanActivity is not None and care_plan_ids is not None:
            purge(
                "care_plan_activities",
                CarePlanActivity,
                CarePlanActivity.care_plan_id.in_(care_plan_ids),
            )
        if CarePlan is not None:
            purge("care_plans", CarePlan, CarePlan.tenant_id == tid)

        if CaregiverLocationEvent is not None:
            purge(
                "caregiver_location_events",
                CaregiverLocationEvent,
                CaregiverLocationEvent.tenant_id == tid,
            )
        if PlacementHistory is not None:
            purge("placement_history", PlacementHistory, PlacementHistory.tenant_id == tid)
        if Assignment is not None:
            purge("assignments", Assignment, Assignment.tenant_id == tid)
        if CaregiverProgramEnrollment is not None:
            purge(
                "caregiver_program_enrollments",
                CaregiverProgramEnrollment,
                CaregiverProgramEnrollment.tenant_id == tid,
            )
        if CaregiverCertification is not None:
            purge(
                "caregiver_certifications",
                CaregiverCertification,
                CaregiverCertification.tenant_id == tid,
            )
        if CaregiverIdentity is not None:
            purge(
                "caregiver_identities",
                CaregiverIdentity,
                CaregiverIdentity.tenant_id == tid,
            )
        if CaregiverPayRate is not None:
            purge("caregiver_pay_rates", CaregiverPayRate, CaregiverPayRate.tenant_id == tid)
        if CaregiverRating is not None:
            purge("caregiver_ratings", CaregiverRating, CaregiverRating.tenant_id == tid)
        if CaregiverDevice is not None:
            purge("caregiver_devices", CaregiverDevice, CaregiverDevice.tenant_id == tid)
        if CaregiverSkill is not None:
            purge(
                "caregiver_skills",
                CaregiverSkill,
                CaregiverSkill.caregiver_id.in_(caregiver_ids),
            )
        if USWorkforceCompliance is not None:
            purge(
                "us_workforce_compliance",
                USWorkforceCompliance,
                USWorkforceCompliance.tenant_id == tid,
            )
        if PredictionResult is not None:
            purge(
                "prediction_results",
                PredictionResult,
                PredictionResult.tenant_id == tid,
            )
        if ElderNotification is not None:
            purge(
                "elder_notifications",
                ElderNotification,
                ElderNotification.tenant_id == tid,
            )
        if ElderMessage is not None:
            purge("elder_messages", ElderMessage, ElderMessage.tenant_id == tid)
        purge("elder_locations", ElderLocation, ElderLocation.tenant_id == tid)
        if MonitoringConsent is not None:
            purge(
                "monitoring_consent",
                MonitoringConsent,
                MonitoringConsent.tenant_id == tid,
            )

        purge("elder_prospects", ElderProspect, ElderProspect.tenant_id == tid)
        purge(
            "caregiver_prospects",
            CaregiverProspect,
            CaregiverProspect.tenant_id == tid,
        )

        docs = db.query(Document).filter(Document.tenant_id == tid).all()
        for doc in docs:
            if doc.document_type == "HOME_SAFETY_CATALOG_IMAGE":
                continue
            if (doc.storage_key or "").startswith("catalog/"):
                continue
            try:
                storage.delete(doc.storage_key)
            except OSError:
                pass
        bump(
            "documents",
            db.execute(
                delete(Document).where(
                    Document.tenant_id == tid,
                    Document.document_type != "HOME_SAFETY_CATALOG_IMAGE",
                )
            ).rowcount,
        )
        (
            db.query(Document)
            .filter(
                Document.tenant_id == tid,
                Document.document_type == "HOME_SAFETY_CATALOG_IMAGE",
            )
            .update({Document.tenant_id: None}, synchronize_session=False)
        )

        bump("users", db.execute(delete(User).where(User.tenant_id == tid)).rowcount)
        bump("elders", db.execute(delete(Elder).where(Elder.tenant_id == tid)).rowcount)
        bump(
            "caregivers",
            db.execute(delete(Caregiver).where(Caregiver.tenant_id == tid)).rowcount,
        )
        bump(
            "audit_logs",
            db.execute(delete(AuditLog).where(AuditLog.tenant_id == tid)).rowcount,
        )

        SubscriptionInvoice = _load(
            "app.models.subscription_invoice", "SubscriptionInvoice"
        )
        TenantSubscription = _load(
            "app.models.tenant_subscription", "TenantSubscription"
        )
        if SubscriptionInvoice is not None:
            purge(
                "subscription_invoices",
                SubscriptionInvoice,
                SubscriptionInvoice.tenant_id == tid,
            )
        if TenantSubscription is not None:
            purge(
                "tenant_subscriptions",
                TenantSubscription,
                TenantSubscription.tenant_id == tid,
            )

        tenant_name = tenant.name
        db.delete(tenant)
        db.commit()

        return {
            "tenant_id": tenant_id,
            "tenant_name": tenant_name,
            "deleted_counts": counts,
        }
