"""WorkforceOS AI resume parsing — OCR + LLM/heuristic extraction for recruitment."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.pipeline_constants import ACTIVITY_NOTE
from app.core.rbac import resolve_tenant_id
from app.core.responses import raise_bad_request
from app.models.caregiver_prospect import CaregiverProspect
from app.models.user import User
from app.schemas.prospects import CaregiverProspectCreate
from app.services import azure_openai_service
from app.services.document_intelligence_service import DocumentIntelligenceService
from app.services.document_service import DocumentService
from app.services.prospect_service import ProspectService

logger = logging.getLogger(__name__)

RESUME_MIME_TYPES = frozenset({
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
})

ELDER_CARE_KEYWORDS = frozenset({
    "elder",
    "elderly",
    "geriatric",
    "home care",
    "caregiver",
    "nursing",
    "patient care",
    "mobility",
    "dementia",
    "palliative",
})

RESUME_JSON_SCHEMA_HINT = """{
  "first_name": "string or null",
  "last_name": "string or null",
  "email": "string or null",
  "phone": "string or null",
  "address": "string or null",
  "years_experience": "integer or null",
  "languages": ["string"],
  "skills": ["string"],
  "certifications": ["string"],
  "education": ["string"],
  "work_history": [{"title": "string", "employer": "string", "years": "string or null"}],
  "care_types": ["visit_based", "live_in", "companion"],
  "summary": "string or null",
  "candidate_score": "0-100 number",
  "score_reasons": ["string"]
}"""


class ResumeIntelligenceService:

    @staticmethod
    def _split_name(full_name: str | None) -> tuple[str | None, str | None]:
        if not full_name:
            return None, None
        parts = full_name.strip().split()
        if len(parts) < 2:
            return parts[0], None
        return parts[0], " ".join(parts[1:])

    @staticmethod
    def _parse_json_content(raw: str) -> dict:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        return json.loads(text)

    @staticmethod
    def _heuristic_parse(text: str) -> dict:
        email = None
        em = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
        if em:
            email = em.group(0)

        phone = None
        ph = re.search(r"(?:\+?\d[\d\s\-()]{8,}\d)", text)
        if ph:
            phone = re.sub(r"\s+", " ", ph.group(0).strip())

        years = None
        ym = re.search(
            r"(\d{1,2})\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)",
            text,
            re.I,
        )
        if ym:
            years = int(ym.group(1))

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        first_name, last_name = ResumeIntelligenceService._split_name(
            lines[0] if lines else None
        )

        languages: list[str] = []
        lang_block = re.search(
            r"languages?\s*:?\s*(.+)",
            text,
            re.I,
        )
        if lang_block:
            languages = [
                p.strip()
                for p in re.split(r"[,;|]", lang_block.group(1))
                if p.strip()
            ]

        skills: list[str] = []
        skill_block = re.search(r"skills?\s*:?\s*(.+)", text, re.I)
        if skill_block:
            skills = [
                p.strip()
                for p in re.split(r"[,;|]", skill_block.group(1))
                if p.strip()
            ]

        certifications: list[str] = []
        cert_block = re.search(
            r"certifications?\s*:?\s*(.+)",
            text,
            re.I,
        )
        if cert_block:
            certifications = [
                p.strip()
                for p in re.split(r"[,;|]", cert_block.group(1))
                if p.strip()
            ]

        lower = text.lower()
        care_hits = [k for k in ELDER_CARE_KEYWORDS if k in lower]
        score, reasons = ResumeIntelligenceService._score_fields(
            {
                "years_experience": years,
                "languages": languages,
                "skills": skills,
                "certifications": certifications,
                "email": email,
                "phone": phone,
                "summary": text[:500],
            },
            care_hits,
        )

        return {
            "fields": {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "address": None,
                "years_experience": years,
                "languages": languages,
                "skills": skills,
                "certifications": certifications,
                "education": [],
                "work_history": [],
                "care_types": ["visit_based"] if care_hits else [],
                "summary": lines[1] if len(lines) > 1 else None,
            },
            "candidate_score": score,
            "score_reasons": reasons,
            "provider": "heuristic",
            "model": None,
            "confidence": "low" if len(text) < 80 else "medium",
        }

    @staticmethod
    def _score_fields(fields: dict, care_hits: list[str] | None = None) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []

        years = fields.get("years_experience")
        if isinstance(years, int):
            if years >= 5:
                score += 25
                reasons.append(f"{years} years experience")
            elif years >= 2:
                score += 18
                reasons.append(f"{years} years experience")
            elif years >= 1:
                score += 10
                reasons.append(f"{years} year experience")

        certs = fields.get("certifications") or []
        if certs:
            score += min(20, 8 + len(certs) * 4)
            reasons.append(f"{len(certs)} certification(s)")

        langs = fields.get("languages") or []
        if langs:
            score += min(15, len(langs) * 5)
            reasons.append(f"{len(langs)} language(s)")

        skills = fields.get("skills") or []
        if skills:
            score += min(15, len(skills) * 3)
            reasons.append(f"{len(skills)} listed skill(s)")

        if fields.get("email") and fields.get("phone"):
            score += 10
            reasons.append("Contact details present")

        hits = care_hits or []
        summary = (fields.get("summary") or "").lower()
        if not hits:
            hits = [k for k in ELDER_CARE_KEYWORDS if k in summary]
        for sk in skills:
            if any(k in sk.lower() for k in ELDER_CARE_KEYWORDS):
                hits.append(sk)
        if hits:
            score += 15
            reasons.append("Elder care relevance")

        return round(min(100.0, score), 1), reasons

    @staticmethod
    def _llm_parse(text: str) -> dict | None:
        if not azure_openai_service.is_configured():
            return None
        prompt = (
            "Extract structured caregiver/worker resume data for an Indian elder-care "
            "agency. Return ONLY valid JSON matching this schema:\n"
            f"{RESUME_JSON_SCHEMA_HINT}\n\n"
            "Resume text:\n"
            f"{text[:12000]}"
        )
        try:
            raw = azure_openai_service.chat_completion(
                [
                    {
                        "role": "system",
                        "content": (
                            "You extract resume fields for workforce recruitment. "
                            "Respond with JSON only."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=1500,
            )
            parsed = ResumeIntelligenceService._parse_json_content(raw)
            fields = parsed.get("fields") or parsed
            score = parsed.get("candidate_score")
            reasons = parsed.get("score_reasons") or []
            if score is None:
                score, reasons = ResumeIntelligenceService._score_fields(fields)
            return {
                "fields": fields,
                "candidate_score": float(score),
                "score_reasons": reasons,
                "provider": "azure_openai",
                "model": "chat",
                "confidence": "high",
            }
        except Exception as exc:
            logger.warning("Resume LLM parse failed: %s", exc)
            return None

    @classmethod
    def parse_content(
        cls,
        content: bytes,
        content_type: str,
        file_name: str,
    ) -> dict:
        if content_type not in RESUME_MIME_TYPES:
            raise_bad_request(
                "Resume must be PDF, plain text, or DOCX"
            )

        raw_text, text_provider = DocumentIntelligenceService.extract_text(
            content,
            content_type,
        )
        if not raw_text.strip():
            raw_text = content.decode("utf-8", errors="replace") if content_type.startswith("text/") else ""
        if not raw_text.strip():
            raise_bad_request(
                "Could not extract text from resume. "
                "Configure DOCUMENT_INTELLIGENCE_ENDPOINT for PDF OCR."
            )

        structured = cls._llm_parse(raw_text) or cls._heuristic_parse(raw_text)
        return {
            **structured,
            "raw_text_preview": raw_text[:2000],
            "text_provider": text_provider,
            "file_name": file_name,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _apply_fields_to_prospect(
        prospect: CaregiverProspect,
        fields: dict,
        *,
        overwrite: bool,
    ) -> None:
        mapping = {
            "first_name": "first_name",
            "last_name": "last_name",
            "phone": "phone",
            "email": "email",
            "address": "address",
            "years_experience": "years_experience",
        }
        for src, dest in mapping.items():
            value = fields.get(src)
            if value is None:
                continue
            if overwrite or not getattr(prospect, dest):
                setattr(prospect, dest, value)

        extras: list[str] = []
        for key in ("skills", "certifications", "languages", "education"):
            vals = fields.get(key) or []
            if vals:
                extras.append(f"{key.title()}: {', '.join(str(v) for v in vals)}")
        if fields.get("summary"):
            extras.append(f"Summary: {fields['summary']}")
        if extras:
            block = "\n".join(extras)
            if prospect.notes:
                prospect.notes = f"{prospect.notes}\n\n[Resume]\n{block}"
            else:
                prospect.notes = f"[Resume]\n{block}"

    @classmethod
    def attach_to_prospect(
        cls,
        db: Session,
        prospect_id: int,
        content: bytes,
        content_type: str,
        file_name: str,
        user: User,
        *,
        apply_fields: bool = True,
        parsed: dict | None = None,
    ) -> dict:
        row = ProspectService.get_caregiver_prospect(db, prospect_id, user)
        if parsed is None:
            parsed = cls.parse_content(content, content_type, file_name)

        store_mime = content_type
        if store_mime not in {
            "application/pdf",
            "image/jpeg",
            "image/png",
            "text/plain",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }:
            store_mime = "application/pdf"

        doc = DocumentService.upload(
            db,
            user,
            "caregiver_prospect",
            row.id,
            "RESUME",
            file_name,
            content,
            store_mime,
        )
        ocr_payload = {
            "provider": parsed.get("provider"),
            "model": parsed.get("model"),
            "text_provider": parsed.get("text_provider"),
            "extracted_at": parsed.get("extracted_at"),
            "fields": parsed.get("fields"),
            "candidate_score": parsed.get("candidate_score"),
            "score_reasons": parsed.get("score_reasons"),
            "raw_text_preview": parsed.get("raw_text_preview"),
        }
        doc.ocr_extracted_json = ocr_payload
        doc.document_name = file_name

        row.resume_parsed_json = ocr_payload
        row.resume_score = parsed.get("candidate_score")
        row.resume_document_id = doc.id

        if apply_fields:
            cls._apply_fields_to_prospect(row, parsed.get("fields") or {}, overwrite=False)
            if not row.source:
                row.source = "resume_upload"

        from app.services.recruitment_placement_service import (
            RecruitmentPlacementService,
        )

        RecruitmentPlacementService.maybe_advance_stage_from_score(
            db,
            row,
            float(parsed.get("candidate_score") or 0),
            user,
        )

        ProspectService._log_activity(
            db,
            tenant_id=row.tenant_id,
            caregiver_prospect_id=row.id,
            activity_type=ACTIVITY_NOTE,
            body=(
                f"Resume parsed — candidate score "
                f"{parsed.get('candidate_score', 0):.0f}"
            ),
            actor=user,
            metadata={
                "resume_document_id": doc.id,
                "candidate_score": parsed.get("candidate_score"),
            },
        )
        db.commit()
        db.refresh(row)
        return {
            "prospect": ProspectService._caregiver_dict(db, row),
            "parse": cls._public_parse(parsed),
            "document_id": doc.id,
        }

    @classmethod
    def parse_and_create_prospect(
        cls,
        db: Session,
        content: bytes,
        content_type: str,
        file_name: str,
        user: User,
        *,
        source: str = "resume_upload",
    ) -> dict:
        tid = resolve_tenant_id(user)
        if tid is None:
            raise_bad_request("Tenant context required")

        parsed = cls.parse_content(content, content_type, file_name)
        fields = parsed.get("fields") or {}
        first = fields.get("first_name") or "Unknown"
        last = fields.get("last_name") or "Candidate"

        prospect = ProspectService.create_caregiver_prospect(
            db,
            CaregiverProspectCreate(
                first_name=first,
                last_name=last,
                phone=fields.get("phone"),
                email=fields.get("email"),
                address=fields.get("address"),
                source=source,
                years_experience=fields.get("years_experience"),
                notes=fields.get("summary"),
            ),
            user,
        )
        return cls.attach_to_prospect(
            db,
            prospect["id"],
            content,
            content_type,
            file_name,
            user,
            apply_fields=True,
            parsed=parsed,
        )

    @staticmethod
    def _public_parse(parsed: dict) -> dict:
        return {
            "provider": parsed.get("provider"),
            "model": parsed.get("model"),
            "text_provider": parsed.get("text_provider"),
            "confidence": parsed.get("confidence"),
            "candidate_score": parsed.get("candidate_score"),
            "score_reasons": parsed.get("score_reasons") or [],
            "fields": parsed.get("fields") or {},
            "raw_text_preview": parsed.get("raw_text_preview"),
            "extracted_at": parsed.get("extracted_at"),
        }
