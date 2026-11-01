"""Contract C orchestration — analyze photos once, cache by SHA-256."""

from __future__ import annotations

import secrets
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.core.storage import get_storage
from app.livewell.ai_config_service import get_ai_settings, normalize_ai_config
from app.livewell.ai_contracts import map_room_type, sha256_hex
from app.livewell.ai_defaults import DEFAULT_AI_CONFIG
from app.livewell.ai_vision_provider import get_vision_provider
from app.livewell.document_types import HOME_SAFETY_PHOTO
from app.livewell.stored_config import read_stored_config
from app.models.document import Document
from app.models.home_safety_vision_analysis import HomeSafetyVisionAnalysis
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.ai_visualization_contracts import (
    RoomAnalyzeRequest,
    RoomAnalyzeResponse,
    SourceImageRef,
)


def _new_analysis_job_id() -> str:
    return f"ANL-{secrets.token_hex(4).upper()}"


class HomeSafetyVisionAnalysisService:
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
            norm = normalize_ai_config(DEFAULT_AI_CONFIG)
        return norm

    @staticmethod
    def _assert_photos(db: Session, tenant_id: int, document_ids: list[int]) -> list[Document]:
        if not document_ids:
            raise_bad_request("At least one document_id is required")
        docs = (
            db.query(Document)
            .filter(
                Document.id.in_(document_ids),
                Document.tenant_id == tenant_id,
                Document.document_type == HOME_SAFETY_PHOTO,
            )
            .all()
        )
        by_id = {d.id: d for d in docs}
        missing = [i for i in document_ids if i not in by_id]
        if missing:
            raise_not_found(f"Assessment photo not found: {missing[0]}")
        return [by_id[i] for i in document_ids]

    @staticmethod
    def _allowed_codes(ai_cfg: dict, room_type: str) -> list[str]:
        room = room_type.strip().lower()
        codes: list[str] = []
        for row in ai_cfg.get("vision_finding_map") or []:
            if row.get("active") is False:
                continue
            row_room = (row.get("room_type") or "").strip().lower()
            if row_room and row_room != room:
                # Map entry/hallway aliases loosely
                aliases = {
                    "entry": {"entry", "entrance"},
                    "entrance": {"entry", "entrance"},
                }
                if row_room not in aliases.get(room, {room}):
                    continue
            code = str(row.get("finding_code") or "").strip()
            if code:
                codes.append(code)
        return list(dict.fromkeys(codes))

    @staticmethod
    def _map_suggestions(
        ai_cfg: dict,
        room_type: str,
        response: RoomAnalyzeResponse,
        *,
        assessor_confirm_min: int,
        auto_apply_min: int,
    ) -> list[dict]:
        room = room_type.strip().lower()
        by_code = {
            str(r.get("finding_code") or "").strip(): r
            for r in (ai_cfg.get("vision_finding_map") or [])
            if r.get("active") is not False
        }
        out: list[dict] = []
        for obs in response.observations:
            row = by_code.get(obs.observation_code)
            if not row:
                continue
            row_room = (row.get("room_type") or "").strip().lower()
            if row_room and row_room not in {room, "entry" if room == "entrance" else room}:
                if not (
                    room in ("entry", "entrance")
                    and row_room in ("entry", "entrance")
                ):
                    continue
            conf_pct = int(round(float(obs.confidence) * 100))
            min_conf = int(row.get("min_confidence") or assessor_confirm_min)
            auto_above = int(row.get("auto_apply_above") or auto_apply_min)
            if conf_pct < min_conf:
                continue
            out.append(
                {
                    "finding_code": obs.observation_code,
                    "solution_id": row.get("solution_id"),
                    "confidence": obs.confidence,
                    "confidence_percent": conf_pct,
                    "evidence": obs.evidence,
                    "photo_id": obs.photo_id,
                    "requires_human_verification": conf_pct < auto_above
                    or bool(obs.requires_human_verification),
                    "auto_apply_eligible": conf_pct >= auto_above,
                }
            )
        return out

    @staticmethod
    def get_cached_for_document(
        db: Session,
        user: User,
        document_id: int,
    ) -> dict | None:
        tenant = HomeSafetyVisionAnalysisService._tenant(db, user)
        try:
            row = (
                db.query(HomeSafetyVisionAnalysis)
                .filter(
                    HomeSafetyVisionAnalysis.tenant_id == tenant.id,
                    HomeSafetyVisionAnalysis.document_id == document_id,
                )
                .order_by(HomeSafetyVisionAnalysis.id.desc())
                .first()
            )
        except Exception:
            # Table missing until migrate/init_db — treat as no cache.
            db.rollback()
            return None
        if not row:
            return None
        return HomeSafetyVisionAnalysisService._row_to_dict(row)

    @staticmethod
    def analyze(
        db: Session,
        user: User,
        *,
        assessment_id: str,
        room_type: str,
        document_ids: list[int],
        force: bool = False,
        origin_session_id: str | None = None,
    ) -> dict:
        tenant = HomeSafetyVisionAnalysisService._tenant(db, user)
        ai_cfg = HomeSafetyVisionAnalysisService._ai_config(tenant)
        settings = get_ai_settings(ai_cfg)
        provider = get_vision_provider(settings)
        docs = HomeSafetyVisionAnalysisService._assert_photos(db, tenant.id, document_ids)

        storage = get_storage()
        image_bytes_by_photo_id: dict[str, bytes] = {}
        source_refs: list[SourceImageRef] = []
        primary_doc = docs[0]
        primary_sha: str | None = None

        for doc in docs:
            try:
                raw, _mime = storage.read(doc.storage_key)
            except Exception:
                raw = b""
            if not raw:
                continue
            digest = sha256_hex(raw) or ""
            if doc.id == primary_doc.id:
                primary_sha = digest
            photo_id = str(doc.id)
            image_bytes_by_photo_id[photo_id] = raw
            source_refs.append(
                SourceImageRef(
                    photo_id=photo_id,
                    download_url=f"/api/v1/home-safety/photos/{doc.id}/image",
                    sha256=digest or None,
                )
            )

        if not source_refs or not primary_sha:
            raise_bad_request("Could not read assessment photo bytes for analysis")

        model_version = provider.model_version()
        if not force:
            cached = (
                db.query(HomeSafetyVisionAnalysis)
                .filter(
                    HomeSafetyVisionAnalysis.tenant_id == tenant.id,
                    HomeSafetyVisionAnalysis.document_id == primary_doc.id,
                    HomeSafetyVisionAnalysis.sha256 == primary_sha,
                    HomeSafetyVisionAnalysis.model_version == model_version,
                )
                .first()
            )
            if cached:
                from app.services.session_activity_service import SessionActivityService

                result = HomeSafetyVisionAnalysisService._row_to_dict(cached, cache_hit=True)
                SessionActivityService.record_ai_or_system_event(
                    db,
                    action="AI vision returned (cache)",
                    summary=(
                        f"Cached vision result · assessment {assessment_id}"
                        f" · room {room_type} · status {cached.status}"
                    ),
                    event_kind="ai_result",
                    session_id=origin_session_id,
                    user_id=user.id,
                    tenant_id=tenant.id,
                    entity_type="assessment",
                    entity_id=assessment_id,
                    meta={
                        "cache_hit": True,
                        "status": cached.status,
                        "document_ids": document_ids,
                    },
                    commit=True,
                )
                return result
        else:
            db.query(HomeSafetyVisionAnalysis).filter(
                HomeSafetyVisionAnalysis.tenant_id == tenant.id,
                HomeSafetyVisionAnalysis.document_id == primary_doc.id,
                HomeSafetyVisionAnalysis.sha256 == primary_sha,
                HomeSafetyVisionAnalysis.model_version == model_version,
            ).delete(synchronize_session=False)

        if not provider.is_configured():
            raise_bad_request(
                "Vision provider is not configured. Set GEMINI_API_KEY or skip analysis."
            )

        assessor_min = int(settings.get("vision_assessor_confirm_min") or 60)
        auto_min = int(settings.get("vision_auto_apply_confidence_min") or 85)
        allowed = HomeSafetyVisionAnalysisService._allowed_codes(ai_cfg, room_type)
        request = RoomAnalyzeRequest(
            job_id=_new_analysis_job_id(),
            room_id=f"ROOM-{primary_doc.id}",
            room_type=map_room_type(room_type),
            source_images=source_refs,
        )
        response = provider.analyze_room(
            request,
            image_bytes_by_photo_id=image_bytes_by_photo_id,
            allowed_finding_codes=allowed,
            assessor_confirm_min=assessor_min / 100.0,
        )
        mapped = HomeSafetyVisionAnalysisService._map_suggestions(
            ai_cfg,
            room_type,
            response,
            assessor_confirm_min=assessor_min,
            auto_apply_min=auto_min,
        )

        row = HomeSafetyVisionAnalysis(
            tenant_id=tenant.id,
            document_id=primary_doc.id,
            assessment_id=(assessment_id or "").strip() or None,
            room_type=room_type.strip().lower(),
            sha256=primary_sha,
            provider=provider.name(),
            model_version=model_version,
            status=response.status,
            response_json=response.model_dump(mode="json"),
            mapped_suggestions=mapped,
            error_message=(
                "; ".join(response.limitations)
                if response.status == "FAILED" and response.limitations
                else None
            ),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        from app.services.session_activity_service import SessionActivityService

        result = HomeSafetyVisionAnalysisService._row_to_dict(row, cache_hit=False)
        SessionActivityService.record_ai_or_system_event(
            db,
            action="AI vision returned",
            summary=(
                f"Vision analysis · assessment {assessment_id}"
                f" · room {room_type} · status {row.status}"
                f" · provider {row.provider}"
            ),
            event_kind="ai_result",
            session_id=origin_session_id,
            user_id=user.id,
            tenant_id=tenant.id,
            entity_type="assessment",
            entity_id=assessment_id,
            meta={
                "cache_hit": False,
                "status": row.status,
                "provider": row.provider,
                "model_version": row.model_version,
                "document_ids": document_ids,
                "suggestion_count": len(mapped or []),
            },
            commit=True,
        )
        return result

    @staticmethod
    def analysis_snapshot_for_document(
        db: Session,
        tenant_id: int,
        document_id: int,
    ) -> dict:
        """Compact phase_snapshot.analysis block for visualization jobs."""
        skipped = {
            "status": "skipped",
            "note": (
                "Room analysis not run for this photo. "
                "Generate proceeds without vision observations."
            ),
        }
        try:
            row = (
                db.query(HomeSafetyVisionAnalysis)
                .filter(
                    HomeSafetyVisionAnalysis.tenant_id == tenant_id,
                    HomeSafetyVisionAnalysis.document_id == document_id,
                    HomeSafetyVisionAnalysis.status == "SUCCEEDED",
                )
                .order_by(HomeSafetyVisionAnalysis.id.desc())
                .first()
            )
        except Exception:
            # Missing table (pre-migrate) must not block Contract E / stub / upload.
            db.rollback()
            return {
                **skipped,
                "note": (
                    "Vision analysis cache table not available yet "
                    "(run backend migrate / init_db). Proceeding without analysis."
                ),
            }
        if not row:
            return skipped
        resp = row.response_json or {}
        return {
            "status": "succeeded",
            "provider": row.provider,
            "model_version": row.model_version,
            "cache_id": row.id,
            "observation_count": len(resp.get("observations") or []),
            "mapped_suggestions": row.mapped_suggestions or [],
            "limitations": resp.get("limitations") or [],
            "analyzed_at": (
                row.created_at.isoformat()
                if isinstance(row.created_at, datetime)
                else None
            ),
            "note": "Contract C vision analysis cached for this photo.",
        }

    @staticmethod
    def _row_to_dict(row: HomeSafetyVisionAnalysis, *, cache_hit: bool = False) -> dict:
        return {
            "id": row.id,
            "assessment_id": row.assessment_id,
            "document_id": row.document_id,
            "room_type": row.room_type,
            "sha256": row.sha256,
            "provider": row.provider,
            "model_version": row.model_version,
            "status": row.status,
            "response": row.response_json or {},
            "mapped_suggestions": row.mapped_suggestions or [],
            "error_message": row.error_message,
            "cache_hit": cache_hit,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
