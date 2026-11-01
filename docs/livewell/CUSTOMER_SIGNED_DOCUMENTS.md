# Kushalaya — Customer Signed Documents (Hyderabad Pilot)

Paper-first workflow: print filled forms → wet signature → upload scan/photo into Kushalaya.

> Templates are operational drafts. Have Indian counsel review before production use.

## Assessor flow

1. Open an assessment → **Review** (or `/livewell/assess/{id}/documents`).
2. **Print / view pack** — customer fields are filled from the assessment; signature lines are blank.
3. Customer signs on paper and keeps originals.
4. On the same page, **Upload wet-signed scan or photo** (PDF / JPEG / PNG). Choose the matching document type.
5. Files are stored on object storage (R2 when configured) and linked to the elder/prospect + assessment.

## Document types

| Code | Packet |
|------|--------|
| `LW_SERVICE_AGREEMENT` | Enrollment |
| `LW_PRIVACY_DPDP_CONSENT` | Enrollment |
| `LW_PHOTO_VIDEO_AI_CONSENT` | Enrollment |
| `LW_HEALTH_EMERGENCY_AUTH` | Enrollment |
| `LW_HOME_ASSESSMENT_CONSENT` | Assessment |
| `LW_EMERGENCY_INFO_SHEET` | Assessment deliverable (catalog EMG-001) — print, post in home, upload photo |
| `LW_QUOTE_ACCEPTANCE` | Installation |
| `LW_WORK_COMPLETION_CERT` | Completion |

### Emergency Information Sheet

Sold with Safety Assessment. Not a consent form — a filled sheet for the home.

1. Collect required intake fields (resident name, address, phone, primary contact name + phone, preferred hospital, allergies or “None”).
2. **Print Emergency Information Sheet** from Customer documents (or documents pack filter).
3. Post in the home; complete any blank lines by hand if needed.
4. Upload a photo under document type `LW_EMERGENCY_INFO_SHEET`.

Metadata on each upload (`ocr_extracted_json`): `form_code`, `template_version` (`2026.08-HYD`), `signature_method=paper_scan`, `signature_status`, `signed_at`, `assessment_id`, `assessor_user_id`.

## APIs

| Method | Path |
|--------|------|
| POST | `/api/v1/home-safety/signed-docs` (multipart: `file`, `form_code`, `assessment_id`, `prospect_id`/`elder_id`) |
| GET | `/api/v1/home-safety/signed-docs/by-assessment/{assessment_id}` |
| GET | `/api/v1/home-safety/signed-docs/{id}/file` |

## Signature roadmap

| Phase | `signature_method` |
|-------|--------------------|
| 1 (now) | `paper_scan` |
| 2 | `otp_remote` |
| 3 | `esign` |

## Code

- Templates: `frontend/lib/livewell/customerDocumentTemplates.ts`
- Upload UI: `frontend/components/livewell/CustomerDocumentsPanel.tsx`
- Print page: `frontend/app/livewell/(portal)/assess/[id]/documents/page.tsx`
- Backend: `backend/app/livewell/signed_doc_service.py`, `backend/app/api/v1/home_safety_signed_docs.py`
