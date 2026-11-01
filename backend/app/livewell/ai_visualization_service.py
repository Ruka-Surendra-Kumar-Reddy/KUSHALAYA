"""AI visualization job lifecycle — create, dispatch stub provider, review."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.livewell.ai_contracts import build_contract_bundle
from app.livewell.ai_config_service import get_ai_settings, normalize_ai_config
from app.livewell.ai_prompt_builder import build_prompt_bundle, build_room_preview_prompt
from fastapi import HTTPException

from app.livewell.ai_room_preview import (
    assert_job_in_team,
    check_render_caps,
    job_progress,
    room_similarity,
    strip_exif,
    watermark,
)
from app.livewell.ai_provider import AIProvider, get_ai_provider
from app.livewell.ai_usage import record_ai_usage
from app.livewell.ai_vision_service import HomeSafetyVisionAnalysisService
from app.livewell.config_keys import AI_CONFIG_KEY
from app.livewell.customer_link import HomeSafetyCustomerLink
from app.livewell.document_types import HOME_SAFETY_AI_CONCEPT, HOME_SAFETY_PHOTO
from app.core.storage import get_storage
from app.livewell.photo_service import HomeSafetyPhotoService
from app.livewell.stored_config import read_stored_config
from app.livewell.solution_service import HomeSafetySolutionService
from app.models.document import Document
from app.models.home_safety_ai_job import HomeSafetyAIJob
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.ai_visualization_contracts import ReviewDecision
from app.services.session_activity_service import SessionActivityService

TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})
REVIEW_ACTIONS = frozenset({"approve", "reject", "regenerate"})
REVIEW_DECISION_MAP = {
    "approve": ReviewDecision.APPROVED,
    "reject": ReviewDecision.REJECTED,
    "regenerate": ReviewDecision.CHANGES_REQUESTED,
}


def _new_public_id() -> str:
    return f"AIJ-{secrets.token_hex(4).upper()}"


def _append_event(job: HomeSafetyAIJob, event: str, detail: dict | None = None) -> None:
    log = list(job.event_log or [])
    entry: dict = {"event": event, "at": datetime.now(timezone.utc).isoformat()}
    if detail:
        entry["detail"] = detail
    log.append(entry)
    job.event_log = log


def _staff_photo_url(document_id: int) -> str:
    return f"/api/v1/home-safety/photos/{document_id}/image"


@dataclass
class _JobBuildContext:
    tenant: Tenant
    user: User
    ai_cfg: dict
    settings: dict
    solutions: dict
    provider: AIProvider


class HomeSafetyAIVisualizationService:

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
    def _ai_config(tenant: Tenant) -> dict:
        stored = read_stored_config(tenant.workflow_config or {})
        cfg = stored.get("ai_config") or {}
        norm = normalize_ai_config(cfg)
        if not norm.get("prompt_templates"):
            from app.livewell.ai_defaults import DEFAULT_AI_CONFIG

            norm = normalize_ai_config(DEFAULT_AI_CONFIG)
        return norm

    @staticmethod
    def _assert_photo(db: Session, tenant_id: int, document_id: int) -> Document:
        doc = (
            db.query(Document)
            .filter(
                Document.id == document_id,
                Document.tenant_id == tenant_id,
                Document.document_type == HOME_SAFETY_PHOTO,
            )
            .first()
        )
        if not doc:
            raise_not_found("Assessment photo not found")
        return doc

    @staticmethod
    def _derive_current_phase(job: HomeSafetyAIJob) -> str:
        if job.status == "failed":
            return "failed"
        if job.review_status == "approved":
            return "complete"
        if job.review_status == "rejected":
            return "rejected"
        if job.status == "needs_review":
            return "review"
        if job.status in ("queued", "running", "validating"):
            return "render"
        if job.status == "awaiting_provider":
            return "render"
        if job.status == "completed":
            return "complete"
        # contracts built but still early
        for entry in job.event_log or []:
            if isinstance(entry, dict) and entry.get("event") == "contracts_built":
                return "render"
        return "assessment"

    @staticmethod
    def _phase_snapshot_from_bundle(bundle, *, analysis: dict | None = None) -> dict:
        assessment = bundle.assessment
        room = assessment.rooms[0] if assessment.rooms else None
        recs = bundle.recommendations
        plan = bundle.plan
        render = bundle.render_request
        return {
            "assessment": {
                "assessment_id": assessment.assessment_id,
                "independence_score": assessment.independence_score,
                "domain_scores": assessment.domain_scores,
                "room_id": room.room_id if room else None,
                "room_type": room.room_type.value if room else None,
                "photo_ids": room.photo_ids if room else [],
                "findings": [
                    {
                        "finding_id": f.finding_id,
                        "finding_code": f.finding_code,
                        "severity": f.severity.value,
                        "requires_visualization": f.requires_visualization,
                    }
                    for f in (room.findings if room else [])
                ],
            },
            "recommendations": {
                "recommendation_set_id": recs.recommendation_set_id,
                "rule_config_version": recs.rule_config_version,
                "items": [
                    {
                        "recommendation_id": item.recommendation_id,
                        "solution_code": item.solution_code,
                        "product_code": item.product_code,
                        "priority": item.priority.value,
                        "visualization_mode": item.visualization_mode.value,
                        "label": item.label,
                    }
                    for room_rec in recs.room_recommendations
                    for item in room_rec.items
                ],
            },
            "analysis": analysis
            or {
                "status": "skipped",
                "note": (
                    "Room analysis not run for this photo. "
                    "Generate proceeds without vision observations."
                ),
            },
            "plan": {
                "visualization_plan_id": plan.visualization_plan_id,
                "disclosure_required": plan.disclosure_required,
                "preservation_constraints": plan.preservation_constraints,
                "render_items": [
                    {
                        "render_item_id": item.render_item_id,
                        "recommendation_id": item.recommendation_id,
                        "product_code": item.product_code,
                        "operation": item.operation.value,
                        "approval_status": item.approval_status.value,
                        "label": item.label,
                    }
                    for item in plan.render_items
                ],
            },
            "render": {
                "job_id": render.job_id if render else None,
                "profile": render.generation.profile if render else None,
                "item_count": len(render.render_items) if render else 0,
                "provider_pending": True,
            },
        }

    @staticmethod
    def _normalize_solution_ids(approved_solution_ids: list[str] | None) -> list[str]:
        return sorted(
            {
                str(s).strip()
                for s in (approved_solution_ids or [])
                if str(s).strip()
            }
        )

    @staticmethod
    def _solution_ids_match(left: list[str] | None, right: list[str] | None) -> bool:
        return HomeSafetyAIVisualizationService._normalize_solution_ids(
            left
        ) == HomeSafetyAIVisualizationService._normalize_solution_ids(right)

    @staticmethod
    def _normalize_product_codes(product_codes: list[str] | None) -> list[str]:
        return sorted(
            {
                str(c).strip()
                for c in (product_codes or [])
                if str(c).strip()
            }
        )

    @staticmethod
    def _phase_snapshot_from_job(job: HomeSafetyAIJob) -> dict:
        for entry in reversed(list(job.event_log or [])):
            if not isinstance(entry, dict):
                continue
            if entry.get("event") != "contracts_built":
                continue
            detail = entry.get("detail") or {}
            snap = detail.get("phase_snapshot")
            if isinstance(snap, dict):
                return snap
        return {}

    @staticmethod
    def _products_from_phase_snapshot(job: HomeSafetyAIJob) -> tuple[list[str], list[str]]:
        """Fallback codes/labels from plan render items when products_selected is missing."""
        snap = HomeSafetyAIVisualizationService._phase_snapshot_from_job(job)
        plan = snap.get("plan") if isinstance(snap, dict) else None
        items = (plan or {}).get("render_items") if isinstance(plan, dict) else None
        if not isinstance(items, list):
            return [], []
        codes: list[str] = []
        labels: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            code = str(item.get("product_code") or "").strip()
            if not code:
                continue
            label = str(item.get("label") or "").strip()
            codes.append(code)
            labels.append(f"{label} ({code})" if label else code)
        return (
            list(dict.fromkeys(codes)),
            list(dict.fromkeys(labels)),
        )

    @staticmethod
    def _explicit_product_codes(job: HomeSafetyAIJob) -> list[str]:
        """Codes the user picked (products_selected), without the plan fallback."""
        for entry in reversed(list(job.event_log or [])):
            if isinstance(entry, dict) and entry.get("event") == "products_selected":
                return HomeSafetyAIVisualizationService._normalize_product_codes(
                    (entry.get("detail") or {}).get("product_codes") or []
                )
        return []

    @staticmethod
    def _preview_checks(job: HomeSafetyAIJob) -> dict:
        for entry in reversed(list(job.event_log or [])):
            if not isinstance(entry, dict):
                continue
            if entry.get("event") == "manual_concept_uploaded":
                return {}
            if entry.get("event") == "preview_checks":
                return entry.get("detail") or {}
        return {}

    @staticmethod
    def _job_product_codes(job: HomeSafetyAIJob) -> list[str]:
        for entry in reversed(list(job.event_log or [])):
            if not isinstance(entry, dict):
                continue
            if entry.get("event") == "products_selected":
                detail = entry.get("detail") or {}
                codes = HomeSafetyAIVisualizationService._normalize_product_codes(
                    detail.get("product_codes") or []
                )
                if codes:
                    return codes
        codes, _labels = HomeSafetyAIVisualizationService._products_from_phase_snapshot(
            job
        )
        return codes

    @staticmethod
    def _job_product_labels(job: HomeSafetyAIJob) -> list[str]:
        """Human-readable product names selected for the after photo (selection order)."""
        for entry in reversed(list(job.event_log or [])):
            if not isinstance(entry, dict):
                continue
            if entry.get("event") == "products_selected":
                detail = entry.get("detail") or {}
                labels = [
                    str(lab).strip()
                    for lab in (detail.get("product_labels") or [])
                    if str(lab).strip()
                ]
                if labels:
                    return list(dict.fromkeys(labels))
                codes = [
                    str(c).strip()
                    for c in (detail.get("product_codes") or [])
                    if str(c).strip()
                ]
                if codes:
                    return list(dict.fromkeys(codes))
        _codes, labels = HomeSafetyAIVisualizationService._products_from_phase_snapshot(
            job
        )
        return labels

    @staticmethod
    def _find_cached_render_job(
        db: Session,
        tenant_id: int,
        *,
        assessment_id: str,
        source_document_id: int,
        package_level: str,
        approved_solution_ids: list[str],
        provider_name: str,
        approved_product_codes: list[str] | None = None,
    ) -> HomeSafetyAIJob | None:
        """Reuse a successful Contract E render for the same photo+tier+solutions+products+provider."""
        level = package_level.strip().lower()
        provider = (provider_name or "").strip()
        if not provider:
            return None
        want_products = HomeSafetyAIVisualizationService._normalize_product_codes(
            approved_product_codes
        )
        candidates = (
            db.query(HomeSafetyAIJob)
            .filter(
                HomeSafetyAIJob.tenant_id == tenant_id,
                HomeSafetyAIJob.assessment_id == assessment_id.strip(),
                HomeSafetyAIJob.source_document_id == source_document_id,
                HomeSafetyAIJob.package_level == level,
                HomeSafetyAIJob.provider == provider,
                HomeSafetyAIJob.status.in_(("needs_review", "completed")),
                HomeSafetyAIJob.review_status != "rejected",
                HomeSafetyAIJob.generated_document_id.isnot(None),
            )
            .order_by(HomeSafetyAIJob.id.desc())
            .all()
        )
        for job in candidates:
            if not HomeSafetyAIVisualizationService._solution_ids_match(
                job.approved_solution_ids,
                approved_solution_ids,
            ):
                continue
            if (
                HomeSafetyAIVisualizationService._explicit_product_codes(job)
                != want_products
            ):
                continue
            return job
        return None

    @staticmethod
    def _job_to_dict(job: HomeSafetyAIJob, *, cache_hit: bool = False) -> dict:
        contracts: dict = {}
        phase_snapshot: dict = {}
        render_callback: dict = {}
        for entry in list(job.event_log or []):
            if not isinstance(entry, dict):
                continue
            if entry.get("event") == "contracts_built":
                contracts = entry.get("detail") or {}
                phase_snapshot = contracts.get("phase_snapshot") or phase_snapshot
            if entry.get("event") == "render_callback":
                render_callback = entry.get("detail") or {}
        current_phase = HomeSafetyAIVisualizationService._derive_current_phase(job)
        return {
            "ai_job_id": job.public_id,
            "id": job.id,
            "assessment_id": job.assessment_id,
            "prospect_id": job.prospect_id,
            "elder_id": job.elder_id,
            "room_type": job.room_type,
            "package_level": job.package_level,
            "source_document_id": job.source_document_id,
            "status": job.status,
            "provider": job.provider,
            "provider_job_id": job.provider_job_id,
            "original_image_url": job.original_image_url,
            "generated_document_id": job.generated_document_id,
            "generated_image_url": job.generated_image_url,
            "prompt_text": job.prompt_text,
            "negative_prompt_text": job.negative_prompt_text,
            "workflow_name": job.workflow_name,
            "workflow_version": job.workflow_version,
            "model_name": job.model_name,
            "approved_solution_ids": job.approved_solution_ids or [],
            "product_codes": HomeSafetyAIVisualizationService._job_product_codes(job),
            "product_labels": HomeSafetyAIVisualizationService._job_product_labels(job),
            "generation_time_seconds": job.generation_time_seconds,
            "retry_count": job.retry_count or 0,
            "error_code": job.error_code,
            "error_message": job.error_message,
            "review_status": job.review_status,
            "reviewed_by_user_id": job.reviewed_by_user_id,
            "reviewed_at": job.reviewed_at,
            "review_notes": job.review_notes,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "event_log": job.event_log or [],
            "visualization_plan_id": contracts.get("visualization_plan_id"),
            "recommendation_set_id": contracts.get("recommendation_set_id"),
            "render_job_id": contracts.get("render_job_id"),
            "current_phase": current_phase,
            "phase_snapshot": phase_snapshot,
            "render_callback": render_callback,
            "cache_hit": cache_hit,
            "progress": job_progress(job),
            "similarity_score": job.similarity_score,
            "render_attempts": job.render_attempts or 0,
            "regenerated_from": job.regenerated_from,
            "checks": HomeSafetyAIVisualizationService._preview_checks(job),
        }

    @staticmethod
    def _supersede_jobs_for_tier(
        db: Session,
        tenant_id: int,
        *,
        assessment_id: str,
        source_document_id: int,
        package_level: str,
    ) -> None:
        """Cancel prior jobs for the same photo + tier so only one active prompt remains."""
        level = package_level.strip().lower()
        existing = (
            db.query(HomeSafetyAIJob)
            .filter(
                HomeSafetyAIJob.tenant_id == tenant_id,
                HomeSafetyAIJob.assessment_id == assessment_id,
                HomeSafetyAIJob.source_document_id == source_document_id,
                HomeSafetyAIJob.package_level == level,
                HomeSafetyAIJob.status != "cancelled",
            )
            .all()
        )
        for prior in existing:
            prior.status = "cancelled"
            _append_event(prior, "superseded", {"package_level": level})

    @staticmethod
    def _load_job_context(db: Session, user: User) -> _JobBuildContext:
        tenant = HomeSafetyAIVisualizationService._tenant(db, user)
        ai_cfg = HomeSafetyAIVisualizationService._ai_config(tenant)
        settings = get_ai_settings(ai_cfg)
        solutions = HomeSafetySolutionService.get_solutions(db, user)
        provider = get_ai_provider(settings)
        return _JobBuildContext(
            tenant=tenant,
            user=user,
            ai_cfg=ai_cfg,
            settings=settings,
            solutions=solutions,
            provider=provider,
        )

    @staticmethod
    def _modification_labels(solutions_lib: dict, approved_solution_ids: list[str]) -> list[str]:
        by_id = {
            str(s.get("id") or "").strip(): s
            for s in (solutions_lib.get("solutions") or [])
            if isinstance(s, dict)
        }
        labels: list[str] = []
        for sid in approved_solution_ids:
            row = by_id.get(str(sid).strip())
            if not row:
                if sid:
                    labels.append(str(sid))
                continue
            recs = row.get("recommendedSolutions") or row.get("recommended_solutions") or []
            if isinstance(recs, list) and recs:
                labels.append(str(recs[0]))
            else:
                labels.append(str(row.get("finding") or row.get("name") or sid))
        return labels

    @staticmethod
    def _persist_generated_image(
        db: Session,
        ctx: _JobBuildContext,
        job: HomeSafetyAIJob,
        source_doc: Document,
        *,
        image_bytes: bytes,
        content_type: str,
        is_stub: bool,
    ) -> None:
        # Persist without DocumentService.upload() — that helper commits the
        # session and would interrupt multi-tier job creation mid-batch.
        ext = ".png" if "png" in (content_type or "").lower() else ".jpg"
        file_name = f"{job.public_id}_concept{ext}"
        storage = get_storage()
        storage_key, storage_url = storage.save(
            ctx.tenant.id,
            source_doc.entity_type,
            source_doc.entity_id,
            file_name,
            image_bytes,
            content_type or "image/png",
        )
        gen_doc = Document(
            tenant_id=ctx.tenant.id,
            entity_type=source_doc.entity_type,
            entity_id=source_doc.entity_id,
            document_type=HOME_SAFETY_AI_CONCEPT,
            document_name=(
                f"AI concept · {job.room_type} · {job.package_level}"
            )[:255],
            file_name=file_name,
            storage_key=storage_key,
            storage_url=storage_url,
            mime_type=content_type or "image/png",
            file_size_bytes=len(image_bytes),
            verification_status="APPROVED",
            uploaded_by_user_id=ctx.user.id,
            ocr_extracted_json={
                "assessment_id": job.assessment_id,
                "room_type": job.room_type,
                "package_level": job.package_level,
                "ai_job_id": job.public_id,
                "role": "ai_concept",
                "is_stub": bool(is_stub),
                "source_document_id": source_doc.id,
            },
        )
        db.add(gen_doc)
        db.flush()
        job.generated_document_id = gen_doc.id
        job.generated_image_url = _staff_photo_url(gen_doc.id)

    @staticmethod
    def _active_tiers_for_photo(
        db: Session,
        tenant_id: int,
        *,
        assessment_id: str,
        source_document_id: int,
    ) -> set[str]:
        rows = (
            db.query(HomeSafetyAIJob.package_level)
            .filter(
                HomeSafetyAIJob.tenant_id == tenant_id,
                HomeSafetyAIJob.assessment_id == assessment_id,
                HomeSafetyAIJob.source_document_id == source_document_id,
                HomeSafetyAIJob.status != "cancelled",
            )
            .all()
        )
        return {r[0].strip().lower() for r in rows if r[0]}

    @staticmethod
    def _build_job(
        db: Session,
        ctx: _JobBuildContext,
        *,
        assessment_id: str,
        room_type: str,
        package_level: str,
        source_document_id: int,
        approved_solution_ids: list[str],
        doc: Document,
        prospect_id: int | None = None,
        elder_id: int | None = None,
        force: bool = False,
        approved_product_codes: list[str] | None = None,
        product_labels: list[str] | None = None,
        origin_session_id: str | None = None,
        defer: bool = False,
    ) -> tuple[HomeSafetyAIJob, bool]:
        resolved_prospect, resolved_elder = HomeSafetyCustomerLink.resolve_customer(
            db,
            ctx.tenant.id,
            prospect_id=prospect_id,
            elder_id=elder_id,
            assessment_id=assessment_id,
            source_document_id=source_document_id,
            require=True,
        )
        HomeSafetyCustomerLink.assert_photo_belongs_to_customer(
            db,
            ctx.tenant.id,
            source_document_id,
            prospect_id=resolved_prospect,
            elder_id=resolved_elder,
        )
        if resolved_elder:
            from app.core.team_scope import assert_elder_in_team

            assert_elder_in_team(db, ctx.user, resolved_elder)

        provider = ctx.provider
        solution_ids = list(dict.fromkeys(approved_solution_ids))
        product_codes = HomeSafetyAIVisualizationService._normalize_product_codes(
            approved_product_codes
        )
        product_label_list = [
            str(lab).strip() for lab in (product_labels or []) if str(lab).strip()
        ]
        if not force:
            cached = HomeSafetyAIVisualizationService._find_cached_render_job(
                db,
                ctx.tenant.id,
                assessment_id=assessment_id,
                source_document_id=source_document_id,
                package_level=package_level,
                approved_solution_ids=solution_ids,
                provider_name=provider.name(),
                approved_product_codes=product_codes,
            )
            if cached is not None:
                _append_event(
                    cached,
                    "render_cache_hit",
                    {
                        "provider": provider.name(),
                        "package_level": package_level.strip().lower(),
                    },
                )
                if origin_session_id and not cached.origin_session_id:
                    cached.origin_session_id = origin_session_id.strip()
                record_ai_usage(
                    db,
                    tenant_id=ctx.tenant.id,
                    feature="room_preview",
                    provider=provider.name(),
                    cache_hit=True,
                    user_id=ctx.user.id,
                    ref=cached.public_id,
                )
                SessionActivityService.record_ai_or_system_event(
                    db,
                    action="AI visualization returned (cache)",
                    summary=(
                        f"Cached concept · job {cached.public_id}"
                        f" · {cached.package_level} · room {cached.room_type}"
                    ),
                    event_kind="ai_result",
                    session_id=origin_session_id or cached.origin_session_id,
                    user_id=ctx.user.id,
                    tenant_id=cached.tenant_id,
                    entity_type="ai_job",
                    entity_id=cached.public_id,
                    meta={"cache_hit": True, "status": cached.status},
                    commit=False,
                )
                return cached, True

        regen_map = check_render_caps(
            db,
            ctx.tenant.id,
            ctx.settings,
            assessment_id=assessment_id,
            source_document_id=source_document_id,
            tiers=[package_level],
        )
        regenerated_from = regen_map.get(package_level.strip().lower())

        HomeSafetyAIVisualizationService._supersede_jobs_for_tier(
            db,
            ctx.tenant.id,
            assessment_id=assessment_id,
            source_document_id=source_document_id,
            package_level=package_level,
        )

        try:
            bundle = build_prompt_bundle(
                ctx.ai_cfg,
                room_type=room_type,
                package_level=package_level,
                approved_solution_ids=solution_ids,
                solutions_lib=ctx.solutions,
            )
        except ValueError as exc:
            if not product_label_list:
                raise_bad_request(str(exc))
            # Room preview of a room with no tenant template: the preview prompt is enough.
            bundle = {
                "prompt_text": "",
                "negative_prompt_text": "",
                "workflow_name": "room_preview_v1",
                "workflow_version": 1,
                "model_name": "flux-kontext",
                "draft_width": 1024,
                "draft_height": 1024,
            }

        if product_label_list:
            # Products picked: one room-preserving edit prompt (names only, no client data).
            prompt_text = build_room_preview_prompt(
                room_type=room_type,
                package_level=package_level,
                product_names=product_label_list,
            )
        else:
            prompt_text = str(bundle["prompt_text"] or "")

        job = HomeSafetyAIJob(
            public_id=_new_public_id(),
            tenant_id=ctx.tenant.id,
            assessment_id=assessment_id.strip(),
            prospect_id=resolved_prospect,
            elder_id=resolved_elder,
            room_type=room_type.strip().lower(),
            package_level=package_level.strip().lower(),
            source_document_id=source_document_id,
            status="queued",
            progress_stage="queued",
            render_attempts=0,
            regenerated_from=regenerated_from,
            original_image_url=_staff_photo_url(source_document_id),
            prompt_text=prompt_text,
            negative_prompt_text=bundle["negative_prompt_text"],
            workflow_name=bundle["workflow_name"],
            workflow_version=bundle["workflow_version"],
            model_name=bundle["model_name"],
            approved_solution_ids=solution_ids,
            review_status="pending",
            event_log=[],
            origin_session_id=(origin_session_id or "").strip() or None,
        )
        db.add(job)
        db.flush()
        _append_event(
            job,
            "job_created",
            {
                "assessment_id": assessment_id,
                "created_by_user_id": ctx.user.id,
                "width": int(bundle["draft_width"]),
                "height": int(bundle["draft_height"]),
                **({"regenerated_from": regenerated_from} if regenerated_from else {}),
            },
        )
        SessionActivityService.record_ai_or_system_event(
            db,
            action="AI visualization job created",
            summary=(
                f"Queued {job.package_level} concept for assessment {job.assessment_id}"
                f" · photo #{job.source_document_id} · room {job.room_type}"
            ),
            event_kind="system",
            session_id=job.origin_session_id,
            user_id=ctx.user.id,
            tenant_id=job.tenant_id,
            entity_type="ai_job",
            entity_id=job.public_id,
            meta={"status": "queued", "package_level": job.package_level},
            commit=False,
        )
        if product_codes or product_label_list:
            _append_event(
                job,
                "products_selected",
                {
                    "product_codes": product_codes,
                    "product_labels": product_label_list,
                },
            )

        job.provider = ctx.provider.name()
        if defer:
            _append_event(job, "queued_for_worker", {"provider": job.provider})
            return job, False
        HomeSafetyAIVisualizationService._render(db, ctx, job, doc)
        return job, False

    @staticmethod
    def _job_render_inputs(job: HomeSafetyAIJob) -> tuple[int, int, list[str]]:
        width, height = 1024, 1024
        for entry in job.event_log or []:
            if isinstance(entry, dict) and entry.get("event") == "job_created":
                d = entry.get("detail") or {}
                width = int(d.get("width") or width)
                height = int(d.get("height") or height)
                break
        labels: list[str] = []
        for entry in reversed(list(job.event_log or [])):
            if isinstance(entry, dict) and entry.get("event") == "products_selected":
                labels = [
                    str(x).strip()
                    for x in ((entry.get("detail") or {}).get("product_labels") or [])
                    if str(x).strip()
                ]
                break
        return width, height, labels

    @staticmethod
    def _render(
        db: Session,
        ctx: _JobBuildContext,
        job: HomeSafetyAIJob,
        doc: Document,
        on_stage=None,
    ) -> None:
        """Call the provider for a created job: privacy strip, render, room + product checks,
        one automatic retry, watermark, save. Runs inline (legacy) or in the worker."""
        from app.livewell.ai_preview_qa import check_products

        def stage(name: str) -> None:
            job.progress_stage = name
            if on_stage:
                on_stage(name)

        provider = ctx.provider
        job.provider = provider.name()
        job.status = "running"
        if not job.started_at:
            job.started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        stage("preparing")

        width, height, product_label_list = HomeSafetyAIVisualizationService._job_render_inputs(job)
        solution_ids = list(job.approved_solution_ids or [])
        product_codes = HomeSafetyAIVisualizationService._explicit_product_codes(job)
        resolved_prospect, resolved_elder = job.prospect_id, job.elder_id

        storage = get_storage()
        try:
            source_bytes, _mime = storage.read(doc.storage_key)
        except Exception:
            source_bytes = b""
        # Privacy: only the pixels leave the server — EXIF/GPS removed, size capped.
        clean_bytes = strip_exif(bytes(source_bytes or b""))

        modification_labels = (
            product_label_list
            if product_label_list
            else HomeSafetyAIVisualizationService._modification_labels(
                ctx.solutions,
                solution_ids,
            )
        )
        rule_version = str(
            (ctx.ai_cfg.get("settings") or {}).get("rule_config_version")
            or ctx.settings.get("rule_config_version")
            or "local"
        )
        try:
            bundle_contracts = build_contract_bundle(
                assessment_id=job.assessment_id,
                elder_id=resolved_elder or resolved_prospect,
                assessor_id=ctx.user.id,
                room_type=job.room_type,
                photo_id=str(job.source_document_id),
                download_url=job.original_image_url or "",
                approved_solution_ids=solution_ids,
                modification_labels=modification_labels,
                source_image_bytes=clean_bytes,
                package_level=job.package_level,
                prompt_text=job.prompt_text,
                negative_prompt_text=job.negative_prompt_text,
                rule_config_version=rule_version,
                width=width,
                height=height,
                job_id=f"JOB-RENDER-{job.public_id}",
            )
        except ValueError as exc:
            job.status = "failed"
            job.error_code = "UNSAFE_OR_UNSUPPORTED_PLAN"
            job.error_message = str(exc)
            job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
            _append_event(job, "contract_build_failed", {"error": str(exc)})
            stage("failed")
            return

        # Stamp product codes onto plan/render items when assessor picked catalog products.
        if product_codes:
            for i, item in enumerate(bundle_contracts.plan.render_items):
                if i < len(product_codes):
                    item.product_code = product_codes[i]
            if bundle_contracts.render_request:
                for i, item in enumerate(bundle_contracts.render_request.render_items):
                    if i < len(product_codes) and item.product is not None:
                        item.product.product_code = product_codes[i]
                    elif i < len(product_codes):
                        from app.schemas.ai_visualization_contracts import RenderProductRef

                        item.product = RenderProductRef(product_code=product_codes[i])

        analysis_snap = HomeSafetyVisionAnalysisService.analysis_snapshot_for_document(
            db, ctx.tenant.id, job.source_document_id
        )
        _append_event(
            job,
            "contracts_built",
            {
                "visualization_plan_id": bundle_contracts.plan.visualization_plan_id,
                "recommendation_set_id": bundle_contracts.recommendations.recommendation_set_id,
                "render_job_id": bundle_contracts.render_request.job_id
                if bundle_contracts.render_request
                else None,
                "assessment_id": bundle_contracts.assessment.assessment_id,
                "approved_render_items": len(bundle_contracts.plan.approved_items()),
                "phase_snapshot": HomeSafetyAIVisualizationService._phase_snapshot_from_bundle(
                    bundle_contracts,
                    analysis=analysis_snap,
                ),
            },
        )

        assert bundle_contracts.render_request is not None
        render_request = bundle_contracts.render_request
        preview_mode = bool(product_label_list)
        extra = {"preview_mode": preview_mode, "product_names": product_label_list}

        def attempt(prompt: str):
            render_request.prompt_text = prompt
            job.render_attempts = int(job.render_attempts or 0) + 1
            _append_event(
                job,
                "provider_request_sent",
                {"provider": provider.name(), "contract": "E", "attempt": job.render_attempts},
            )
            res = provider.submit_render(
                render_request, source_image_bytes=clean_bytes, extra={**extra, "attempt": job.render_attempts}
            )
            record_ai_usage(
                db,
                tenant_id=job.tenant_id,
                feature="room_preview",
                provider=provider.name(),
                model=res.model_used or job.model_name,
                status="ok" if res.status == "completed" else "failed",
                user_id=ctx.user.id,
                ref=job.public_id,
            )
            return res

        stage("generating")
        result = attempt(job.prompt_text or "")

        if preview_mode and result.status == "completed" and result.generated_image_bytes:
            try:
                min_sim = float(ctx.settings.get("room_similarity_min") or 0.5)
            except (TypeError, ValueError):
                min_sim = 0.5

            def check(res):
                stage("checking")
                sim = room_similarity(clean_bytes, res.generated_image_bytes)
                qa = check_products(res.generated_image_bytes, product_label_list, before=clean_bytes)
                if qa.get("status") == "checked" or qa.get("reason") == "qa_failed":
                    record_ai_usage(
                        db,
                        tenant_id=job.tenant_id,
                        feature="room_preview",
                        provider="gemini",
                        model=qa.get("model"),
                        status="ok" if qa.get("status") == "checked" else "failed",
                        user_id=ctx.user.id,
                        ref=job.public_id,
                    )
                return sim, qa

            def score(sim, qa):
                present = sum(1 for i in qa.get("items") or [] if i.get("present"))
                return (present, -len(qa.get("changes") or []), sim if sim is not None else 0.0)

            sim, qa = check(result)
            changes = list(qa.get("changes") or [])
            room_changed = (sim is not None and sim < min_sim) or bool(changes)
            missing = list(qa.get("missing") or [])
            if room_changed or missing:
                stage("retrying")
                _append_event(
                    job,
                    "auto_retry",
                    {"similarity": sim, "room_changed": room_changed, "missing": missing, "changes": changes},
                )
                strict = build_room_preview_prompt(
                    room_type=job.room_type,
                    package_level=job.package_level,
                    product_names=product_label_list,
                    strict=True,
                    missing=missing or None,
                    unwanted=changes or None,
                )
                second = attempt(strict)
                if second.status == "completed" and second.generated_image_bytes:
                    sim2, qa2 = check(second)
                    if score(sim2, qa2) >= score(sim, qa):
                        result, sim, qa = second, sim2, qa2
                        job.prompt_text = strict
            job.similarity_score = sim
            _append_event(
                job,
                "preview_checks",
                {
                    "similarity": sim,
                    "similarity_min": min_sim,
                    "room_changed": (sim is not None and sim < min_sim) or bool(qa.get("changes")),
                    "qa": qa,
                    "attempts": job.render_attempts,
                },
            )

        job.provider_job_id = result.provider_job_id
        job.generation_time_seconds = result.generation_time_seconds
        job.error_code = result.error_code
        job.error_message = result.error_message

        if result.render_accepted:
            _append_event(
                job,
                "render_accepted",
                result.render_accepted.model_dump(mode="json"),
            )
        if result.render_callback:
            _append_event(
                job,
                "render_callback",
                {
                    "job_id": result.render_callback.job_id,
                    "status": result.render_callback.status.value
                    if hasattr(result.render_callback.status, "value")
                    else result.render_callback.status,
                    "candidate_count": len(result.render_callback.outputs),
                    "is_stub": bool(
                        result.render_callback.provenance
                        and result.render_callback.provenance.is_stub
                    ),
                },
            )

        if result.status == "awaiting_provider":
            job.status = "awaiting_provider"
            _append_event(job, "provider_not_configured")
            SessionActivityService.record_ai_or_system_event(
                db,
                action="AI provider not configured",
                summary=(
                    f"Visualization job {job.public_id} waiting — provider unavailable"
                ),
                event_kind="ai_result",
                session_id=job.origin_session_id,
                user_id=ctx.user.id,
                tenant_id=job.tenant_id,
                entity_type="ai_job",
                entity_id=job.public_id,
                meta={"status": job.status, "provider": provider.name()},
                commit=False,
            )
            stage("failed")
        elif result.status == "completed" and (
            result.generated_image_bytes or result.generated_image_url
        ):
            stage("saving")
            if result.generated_image_bytes:
                # Brand mark on every generated image, burnt in when saved.
                marked, marked_type = watermark(result.generated_image_bytes)
                HomeSafetyAIVisualizationService._persist_generated_image(
                    db,
                    ctx,
                    job,
                    doc,
                    image_bytes=marked,
                    content_type=marked_type or result.generated_content_type or "image/png",
                    is_stub=bool(result.is_stub),
                )
            else:
                job.generated_image_url = result.generated_image_url
            job.status = "needs_review"
            _append_event(
                job,
                "workflow_completed",
                {"is_stub": bool(result.is_stub), "provider": provider.name()},
            )
            SessionActivityService.record_ai_or_system_event(
                db,
                action="AI visualization returned",
                summary=(
                    f"Concept ready for review · job {job.public_id}"
                    f" · {job.package_level} · room {job.room_type}"
                    + (" (stub)" if result.is_stub else "")
                ),
                event_kind="ai_result",
                session_id=job.origin_session_id,
                user_id=ctx.user.id,
                tenant_id=job.tenant_id,
                entity_type="ai_job",
                entity_id=job.public_id,
                meta={
                    "status": job.status,
                    "provider": provider.name(),
                    "is_stub": bool(result.is_stub),
                    "generation_time_seconds": job.generation_time_seconds,
                },
                commit=False,
            )
            stage("done")
        elif result.status == "failed":
            job.status = "failed"
            _append_event(job, "workflow_failed", {"error_code": result.error_code})
            SessionActivityService.record_ai_or_system_event(
                db,
                action="AI visualization failed",
                summary=(
                    f"Job {job.public_id} failed"
                    + (f": {job.error_message}" if job.error_message else "")
                ),
                event_kind="ai_result",
                session_id=job.origin_session_id,
                user_id=ctx.user.id,
                tenant_id=job.tenant_id,
                entity_type="ai_job",
                entity_id=job.public_id,
                meta={
                    "status": "failed",
                    "error_code": job.error_code,
                    "error_message": job.error_message,
                },
                commit=False,
            )
            stage("failed")
        else:
            job.status = result.status or "queued"
            SessionActivityService.record_ai_or_system_event(
                db,
                action="AI visualization status update",
                summary=f"Job {job.public_id} → {job.status}",
                event_kind="ai_result",
                session_id=job.origin_session_id,
                user_id=ctx.user.id,
                tenant_id=job.tenant_id,
                entity_type="ai_job",
                entity_id=job.public_id,
                meta={"status": job.status},
                commit=False,
            )
        job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def list_jobs(
        db: Session,
        user: User,
        *,
        assessment_id: str | None = None,
        prospect_id: int | None = None,
        status: str | None = None,
        review_status: str | None = None,
        limit: int = 100,
        elder_id: int | None = None,
    ) -> list[dict]:
        tenant = HomeSafetyAIVisualizationService._tenant(db, user)
        q = db.query(HomeSafetyAIJob).filter(HomeSafetyAIJob.tenant_id == tenant.id)
        if assessment_id:
            q = q.filter(HomeSafetyAIJob.assessment_id == assessment_id)
        if prospect_id is not None:
            q = q.filter(HomeSafetyAIJob.prospect_id == prospect_id)
        if status:
            q = q.filter(HomeSafetyAIJob.status == status)
        else:
            q = q.filter(HomeSafetyAIJob.status != "cancelled")
        if review_status:
            q = q.filter(HomeSafetyAIJob.review_status == review_status)
        if elder_id is not None:
            q = q.filter(HomeSafetyAIJob.elder_id == elder_id)
        rows = q.order_by(HomeSafetyAIJob.created_at.desc()).limit(limit * 2).all()
        visible = []
        for j in rows:
            try:
                assert_job_in_team(db, user, j)
            except HTTPException:
                continue
            visible.append(j)
        return [HomeSafetyAIVisualizationService._job_to_dict(j) for j in visible[:limit]]

    @staticmethod
    def get_job(db: Session, user: User, public_id: str) -> dict:
        tenant = HomeSafetyAIVisualizationService._tenant(db, user)
        job = (
            db.query(HomeSafetyAIJob)
            .filter(
                HomeSafetyAIJob.tenant_id == tenant.id,
                HomeSafetyAIJob.public_id == public_id,
            )
            .first()
        )
        if not job:
            raise_not_found("AI job not found")
        assert_job_in_team(db, user, job)
        return HomeSafetyAIVisualizationService._job_to_dict(job)

    @staticmethod
    def create_job(
        db: Session,
        user: User,
        *,
        assessment_id: str,
        room_type: str,
        package_level: str,
        source_document_id: int,
        approved_solution_ids: list[str],
        prospect_id: int | None = None,
        elder_id: int | None = None,
        force: bool = False,
        origin_session_id: str | None = None,
        approved_product_codes: list[str] | None = None,
        product_labels: list[str] | None = None,
        defer: bool = False,
    ) -> dict:
        ctx = HomeSafetyAIVisualizationService._load_job_context(db, user)
        doc = HomeSafetyAIVisualizationService._assert_photo(
            db, ctx.tenant.id, source_document_id
        )
        job, cache_hit = HomeSafetyAIVisualizationService._build_job(
            db,
            ctx,
            assessment_id=assessment_id,
            room_type=room_type,
            package_level=package_level,
            source_document_id=source_document_id,
            approved_solution_ids=approved_solution_ids,
            doc=doc,
            prospect_id=prospect_id,
            elder_id=elder_id,
            force=force,
            origin_session_id=origin_session_id,
            approved_product_codes=approved_product_codes,
            product_labels=product_labels,
            defer=defer,
        )
        db.commit()
        db.refresh(job)
        if defer and not cache_hit and job.status == "queued":
            from app.livewell.ai_render_queue import submit

            submit(db, job.id, job.tenant_id)
            db.refresh(job)
        return HomeSafetyAIVisualizationService._job_to_dict(job, cache_hit=cache_hit)

    @staticmethod
    def generate_for_photo(
        db: Session,
        user: User,
        *,
        assessment_id: str,
        source_document_id: int,
        room_type: str,
        approved_solution_ids: list[str],
        tiers: list[str] | None = None,
        only_missing: bool = True,
        force: bool = False,
        prospect_id: int | None = None,
        elder_id: int | None = None,
        approved_product_codes: list[str] | None = None,
        product_labels: list[str] | None = None,
        origin_session_id: str | None = None,
        defer: bool = False,
    ) -> list[dict]:
        ctx = HomeSafetyAIVisualizationService._load_job_context(db, user)
        doc = HomeSafetyAIVisualizationService._assert_photo(
            db, ctx.tenant.id, source_document_id
        )

        active_tiers = [
            t["id"]
            for t in ctx.ai_cfg.get("tiers") or []
            if t.get("active", True)
        ]
        selected = [t.strip().lower() for t in (tiers or active_tiers) if t.strip()]
        if not selected:
            selected = ["essential", "comfort", "premium"]

        if only_missing and not force:
            have = HomeSafetyAIVisualizationService._active_tiers_for_photo(
                db,
                ctx.tenant.id,
                assessment_id=assessment_id,
                source_document_id=source_document_id,
            )
            selected = [t for t in selected if t not in have]

        if not selected:
            return []

        solution_ids = list(dict.fromkeys(approved_solution_ids))
        product_codes = HomeSafetyAIVisualizationService._normalize_product_codes(
            approved_product_codes
        )
        product_label_list = [
            str(lab).strip() for lab in (product_labels or []) if str(lab).strip()
        ]
        provider_name = ctx.provider.name()
        cached_pairs: list[tuple[HomeSafetyAIJob, bool]] = []
        tiers_to_render: list[str] = []
        for tier in selected:
            if not force:
                cached = HomeSafetyAIVisualizationService._find_cached_render_job(
                    db,
                    ctx.tenant.id,
                    assessment_id=assessment_id,
                    source_document_id=source_document_id,
                    package_level=tier,
                    approved_solution_ids=solution_ids,
                    provider_name=provider_name,
                    approved_product_codes=product_codes,
                )
                if cached is not None:
                    _append_event(
                        cached,
                        "render_cache_hit",
                        {
                            "provider": provider_name,
                            "package_level": tier,
                        },
                    )
                    record_ai_usage(
                        db,
                        tenant_id=ctx.tenant.id,
                        feature="room_preview",
                        provider=provider_name,
                        cache_hit=True,
                        user_id=ctx.user.id,
                        ref=cached.public_id,
                    )
                    cached_pairs.append((cached, True))
                    continue
            tiers_to_render.append(tier)

        # Caps (photos × tiers, regenerations, daily) are checked per tier in _build_job.
        built: list[tuple[HomeSafetyAIJob, bool]] = list(cached_pairs)
        for tier in tiers_to_render:
            job, cache_hit = HomeSafetyAIVisualizationService._build_job(
                db,
                ctx,
                assessment_id=assessment_id,
                room_type=room_type,
                package_level=tier,
                source_document_id=source_document_id,
                approved_solution_ids=solution_ids,
                doc=doc,
                prospect_id=prospect_id,
                elder_id=elder_id,
                force=force,
                approved_product_codes=product_codes,
                product_labels=product_label_list,
                origin_session_id=origin_session_id,
                defer=defer,
            )
            built.append((job, cache_hit))

        db.commit()
        if defer:
            from app.livewell.ai_render_queue import submit

            for job, cache_hit in built:
                if not cache_hit and job.status == "queued":
                    submit(db, job.id, job.tenant_id)
        out: list[dict] = []
        for job, cache_hit in built:
            db.refresh(job)
            out.append(
                HomeSafetyAIVisualizationService._job_to_dict(job, cache_hit=cache_hit)
            )
        return out

    @staticmethod
    def upload_concept_image(
        db: Session,
        user: User,
        *,
        assessment_id: str,
        source_document_id: int,
        room_type: str,
        package_level: str,
        file_name: str,
        content: bytes,
        content_type: str,
        approved_solution_ids: list[str] | None = None,
        prospect_id: int | None = None,
        elder_id: int | None = None,
        ai_job_id: str | None = None,
        approved_product_codes: list[str] | None = None,
        product_labels: list[str] | None = None,
        origin_session_id: str | None = None,
    ) -> dict:
        """Attach a manually uploaded after/concept photo to a visualization job.

        Creates a new job when none exists for the photo+tier, or replaces the
        concept image on an existing job. Manual uploads are non-stub and
        eligible for report merge after human approval.
        """
        if not content:
            raise_bad_request("Image file is required")
        mime = (content_type or "").lower()
        if mime and not mime.startswith("image/"):
            raise_bad_request("Concept upload must be an image file")

        ctx = HomeSafetyAIVisualizationService._load_job_context(db, user)
        product_codes = HomeSafetyAIVisualizationService._normalize_product_codes(
            approved_product_codes
        )
        product_label_list = [
            str(lab).strip() for lab in (product_labels or []) if str(lab).strip()
        ]
        doc = HomeSafetyAIVisualizationService._assert_photo(
            db, ctx.tenant.id, source_document_id
        )
        level = (package_level or "essential").strip().lower()
        room = (room_type or "").strip().lower()
        if not room:
            raise_bad_request("room_type is required")

        job: HomeSafetyAIJob | None = None
        if ai_job_id:
            job = (
                db.query(HomeSafetyAIJob)
                .filter(
                    HomeSafetyAIJob.tenant_id == ctx.tenant.id,
                    HomeSafetyAIJob.public_id == ai_job_id.strip(),
                )
                .first()
            )
            if not job:
                raise_not_found("AI job not found")
            if job.source_document_id != source_document_id:
                raise_bad_request("Job does not match the selected source photo")
        else:
            job = (
                db.query(HomeSafetyAIJob)
                .filter(
                    HomeSafetyAIJob.tenant_id == ctx.tenant.id,
                    HomeSafetyAIJob.assessment_id == assessment_id.strip(),
                    HomeSafetyAIJob.source_document_id == source_document_id,
                    HomeSafetyAIJob.package_level == level,
                    HomeSafetyAIJob.status != "cancelled",
                )
                .order_by(HomeSafetyAIJob.id.desc())
                .first()
            )

        solution_ids = list(
            dict.fromkeys(
                [
                    str(s).strip()
                    for s in (approved_solution_ids or (job.approved_solution_ids if job else []) or [])
                    if str(s).strip()
                ]
            )
        )

        if job is None:
            resolved_prospect, resolved_elder = HomeSafetyCustomerLink.resolve_customer(
                db,
                ctx.tenant.id,
                prospect_id=prospect_id,
                elder_id=elder_id,
                assessment_id=assessment_id,
                source_document_id=source_document_id,
                require=True,
            )
            HomeSafetyCustomerLink.assert_photo_belongs_to_customer(
                db,
                ctx.tenant.id,
                source_document_id,
                prospect_id=resolved_prospect,
                elder_id=resolved_elder,
            )
            HomeSafetyAIVisualizationService._supersede_jobs_for_tier(
                db,
                ctx.tenant.id,
                assessment_id=assessment_id,
                source_document_id=source_document_id,
                package_level=level,
            )
            job = HomeSafetyAIJob(
                public_id=_new_public_id(),
                tenant_id=ctx.tenant.id,
                assessment_id=assessment_id.strip(),
                prospect_id=resolved_prospect,
                elder_id=resolved_elder,
                room_type=room,
                package_level=level,
                source_document_id=source_document_id,
                status="needs_review",
                provider="manual_upload",
                original_image_url=_staff_photo_url(source_document_id),
                approved_solution_ids=solution_ids,
                review_status="pending",
                event_log=[],
                model_name="manual",
                workflow_name="manual_upload",
                origin_session_id=(origin_session_id or "").strip() or None,
            )
            db.add(job)
            db.flush()
            _append_event(job, "job_created", {"assessment_id": assessment_id, "manual": True})
        else:
            job.provider = "manual_upload"
            job.model_name = "manual"
            if origin_session_id and not job.origin_session_id:
                job.origin_session_id = origin_session_id.strip()
            if solution_ids:
                job.approved_solution_ids = solution_ids
            if room:
                job.room_type = room

        HomeSafetyAIVisualizationService._persist_generated_image(
            db,
            ctx,
            job,
            doc,
            image_bytes=content,
            content_type=content_type or "image/jpeg",
            is_stub=False,
        )
        # Mark metadata as manual upload (non-stub) for report merge.
        if job.generated_document_id:
            gen_doc = (
                db.query(Document)
                .filter(Document.id == job.generated_document_id)
                .first()
            )
            if gen_doc and isinstance(gen_doc.ocr_extracted_json, dict):
                meta = dict(gen_doc.ocr_extracted_json)
                meta["is_stub"] = False
                meta["role"] = "manual_concept"
                meta["source"] = "assessor_upload"
                gen_doc.ocr_extracted_json = meta

        job.status = "needs_review"
        job.review_status = "pending"
        job.reviewed_at = None
        job.reviewed_by_user_id = None
        job.review_notes = None
        job.error_code = None
        job.error_message = "Manual after/concept photo uploaded by assessor."
        if product_codes or product_label_list:
            _append_event(
                job,
                "products_selected",
                {
                    "product_codes": product_codes,
                    "product_labels": product_label_list,
                },
            )
        _append_event(
            job,
            "manual_concept_uploaded",
            {
                "file_name": file_name,
                "content_type": content_type,
                "bytes": len(content),
                "is_stub": False,
            },
        )
        _append_event(
            job,
            "render_callback",
            {
                "job_id": job.public_id,
                "status": "SUCCEEDED",
                "candidate_count": 1,
                "is_stub": False,
                "provider": "manual_upload",
            },
        )
        SessionActivityService.record_ai_or_system_event(
            db,
            action="Concept photo ready for review",
            summary=(
                f"Manual after photo attached · job {job.public_id}"
                f" · {job.package_level} · room {job.room_type}"
            ),
            event_kind="ai_result",
            session_id=job.origin_session_id or origin_session_id,
            user_id=ctx.user.id,
            tenant_id=job.tenant_id,
            entity_type="ai_job",
            entity_id=job.public_id,
            meta={"status": job.status, "provider": "manual_upload"},
            commit=False,
        )
        db.commit()
        db.refresh(job)
        return HomeSafetyAIVisualizationService._job_to_dict(job)

    @staticmethod
    def review_job(
        db: Session,
        user: User,
        public_id: str,
        *,
        action: str,
        notes: str | None = None,
        defer: bool = False,
    ) -> dict:
        if action not in REVIEW_ACTIONS:
            raise_bad_request(f"Invalid review action: {action}")

        tenant = HomeSafetyAIVisualizationService._tenant(db, user)
        job = (
            db.query(HomeSafetyAIJob)
            .filter(
                HomeSafetyAIJob.tenant_id == tenant.id,
                HomeSafetyAIJob.public_id == public_id,
            )
            .first()
        )
        if not job:
            raise_not_found("AI job not found")
        assert_job_in_team(db, user, job)

        if action == "approve":
            if job.status not in ("needs_review", "awaiting_provider"):
                raise_bad_request("Job is not ready for approval")
            qa = HomeSafetyAIVisualizationService._preview_checks(job).get("qa") or {}
            missing = qa.get("missing") or []
            if missing:
                raise_bad_request(
                    "Not shown in the image: " + ", ".join(missing)
                    + ". Regenerate, remove those items, or upload your own after photo."
                )
            changes = qa.get("changes") or []
            if changes:
                raise_bad_request(
                    "The picture changed the room: " + "; ".join(changes)
                    + ". Regenerate or upload your own after photo."
                )
            if not job.generated_document_id:
                raise_bad_request(
                    "Upload or generate an after/concept photo before approving"
                )
            job.review_status = "approved"
            job.status = "completed"
            job.reviewed_by_user_id = user.id
            job.reviewed_at = datetime.now(timezone.utc)
            job.review_notes = notes
            _append_event(
                job,
                "human_review_approved",
                {"decision": REVIEW_DECISION_MAP[action].value},
            )
            SessionActivityService.record_ai_or_system_event(
                db,
                action="AI visualization approved (system)",
                summary=(
                    f"Job {job.public_id} completed — family can view after publish"
                ),
                event_kind="system",
                session_id=job.origin_session_id,
                user_id=user.id,
                tenant_id=job.tenant_id,
                entity_type="ai_job",
                entity_id=job.public_id,
                meta={"review_status": "approved", "status": "completed"},
                commit=False,
            )
        elif action == "reject":
            job.review_status = "rejected"
            job.reviewed_by_user_id = user.id
            job.reviewed_at = datetime.now(timezone.utc)
            job.review_notes = notes
            _append_event(
                job,
                "human_review_rejected",
                {"decision": REVIEW_DECISION_MAP[action].value},
            )
            SessionActivityService.record_ai_or_system_event(
                db,
                action="AI visualization rejected (system)",
                summary=f"Job {job.public_id} rejected",
                event_kind="system",
                session_id=job.origin_session_id,
                user_id=user.id,
                tenant_id=job.tenant_id,
                entity_type="ai_job",
                entity_id=job.public_id,
                meta={"review_status": "rejected"},
                commit=False,
            )
        elif action == "regenerate":
            # Explicit re-run always calls the render provider (skips Contract E cache).
            return HomeSafetyAIVisualizationService.create_job(
                db,
                user,
                assessment_id=job.assessment_id,
                room_type=job.room_type,
                package_level=job.package_level,
                source_document_id=job.source_document_id,
                approved_solution_ids=list(job.approved_solution_ids or []),
                prospect_id=job.prospect_id,
                elder_id=job.elder_id,
                force=True,
                origin_session_id=job.origin_session_id,
                approved_product_codes=HomeSafetyAIVisualizationService._explicit_product_codes(job),
                product_labels=HomeSafetyAIVisualizationService._job_render_inputs(job)[2],
                defer=defer,
            )

        db.commit()
        db.refresh(job)
        return HomeSafetyAIVisualizationService._job_to_dict(job)

    @staticmethod
    def read_source_photo(
        db: Session,
        user: User,
        document_id: int,
    ) -> tuple[bytes, str, str]:
        return HomeSafetyPhotoService.read_for_staff(db, user, document_id)
