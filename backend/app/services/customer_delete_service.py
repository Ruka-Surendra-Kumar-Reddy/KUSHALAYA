"""Hard-delete clients (elders) and elder prospects for tenant admins."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.rbac import ADMIN_ROLES, assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.core.storage import get_storage
from app.models.document import Document
from app.models.elder import Elder
from app.models.elder_prospect import ElderProspect
from app.models.home_safety_assessment import HomeSafetyAssessmentRecord
from app.models.home_safety_ai_job import HomeSafetyAIJob
from app.models.pipeline_activity import PipelineActivity
from app.models.user import User

try:
    from app.models.family_elder_link import FamilyElderLink
except ImportError:  # pragma: no cover
    FamilyElderLink = None  # type: ignore[misc, assignment]


def _require_admin(user: User) -> None:
    if user.role not in ADMIN_ROLES:
        raise_bad_request("Only tenant or system admins can permanently delete")


def _table_exists(db: Session, name: str) -> bool:
    return inspect(db.get_bind()).has_table(name)


def _sql_ident(name: str) -> str:
    return '"' + name.replace('"', "") + '"'


def _release_document_refs(db: Session, *, entity_type: str, entity_id: int) -> None:
    """Rows that point at the client's photos: AI before/after jobs and photo analyses.

    A job or analysis cannot exist without its source photo, so it goes with it; a
    generated picture reference is just cleared.
    """
    ids = [
        int(r[0])
        for r in db.query(Document.id)
        .filter(Document.entity_type == entity_type, Document.entity_id == entity_id)
        .all()
    ]
    if not ids:
        return
    id_list = ", ".join(str(i) for i in ids)
    if _table_exists(db, "home_safety_ai_jobs"):
        db.execute(text(f"UPDATE home_safety_ai_jobs SET generated_document_id = NULL WHERE generated_document_id IN ({id_list})"))
        db.execute(text(f"DELETE FROM home_safety_ai_jobs WHERE source_document_id IN ({id_list})"))
    if _table_exists(db, "home_safety_vision_analyses"):
        db.execute(text(f"DELETE FROM home_safety_vision_analyses WHERE document_id IN ({id_list})"))


def _delete_documents(db: Session, *, entity_type: str, entity_id: int) -> int:
    rows = (
        db.query(Document)
        .filter(Document.entity_type == entity_type, Document.entity_id == entity_id)
        .all()
    )
    storage = get_storage()
    n = 0
    for doc in rows:
        try:
            storage.delete(doc.storage_key)
        except Exception:
            pass
        db.delete(doc)
        n += 1
    return n


def _purge_visit_graph(db: Session, elder_id: int) -> None:
    """Visits may be referenced by swap requests — clear those first when tables exist."""
    if not _table_exists(db, "visits"):
        return
    visit_ids = [
        int(row[0])
        for row in db.execute(
            text('SELECT id FROM "visits" WHERE elder_id = :eid'),
            {"eid": elder_id},
        ).fetchall()
    ]
    if visit_ids and _table_exists(db, "shift_swap_requests"):
        placeholders = ", ".join(str(v) for v in visit_ids)
        db.execute(
            text(f'DELETE FROM "shift_swap_requests" WHERE visit_id IN ({placeholders})')
        )
    try:
        with db.begin_nested():
            db.execute(
                text(
                    'UPDATE "visits" SET attendance_record_id = NULL WHERE elder_id = :eid'
                ),
                {"eid": elder_id},
            )
    except ProgrammingError:
        pass
    db.execute(text('DELETE FROM "visits" WHERE elder_id = :eid'), {"eid": elder_id})


# Statutory records that must never be removed by a client delete. GST invoices
# and their number counters have to be kept for years; a client with invoices is
# erased with DPDP "Delete personal data" instead (which keeps the invoices).
PROTECTED_TABLES = frozenset({"tax_invoices", "invoice_counters"})


def _has_tax_invoices(db: Session, elder_id: int) -> bool:
    if not _table_exists(db, "tax_invoices"):
        return False
    row = db.execute(
        text("SELECT 1 FROM tax_invoices WHERE elder_id = :eid LIMIT 1"), {"eid": elder_id}
    ).first()
    return row is not None


def _clear_all_elder_foreign_keys(db: Session, elder_id: int) -> list[str]:
    """Nullify or delete every row that FKs to this elder (only tables that exist).

    Never touches PROTECTED_TABLES.
    """
    bind = db.get_bind()
    insp = inspect(bind)
    touched: list[str] = []

    actions: list[tuple[str, str, bool]] = []
    for table_name in insp.get_table_names():
        if table_name == "elders" or table_name in PROTECTED_TABLES:
            continue
        col_meta = {c["name"]: c for c in insp.get_columns(table_name)}
        for fk in insp.get_foreign_keys(table_name):
            if fk.get("referred_table") != "elders":
                continue
            for col in fk.get("constrained_columns") or []:
                nullable = bool(col_meta.get(col, {}).get("nullable", True))
                actions.append((table_name, col, nullable))

    # Non-nullable DELETE first, then nullable UPDATE NULL
    for table_name, col, nullable in sorted(actions, key=lambda a: (a[2], a[0], a[1])):
        if table_name == "visits":
            # Handled in _purge_visit_graph for dependency order
            continue
        tbl = _sql_ident(table_name)
        c = _sql_ident(col)
        try:
            with db.begin_nested():
                if nullable:
                    db.execute(
                        text(f"UPDATE {tbl} SET {c} = NULL WHERE {c} = :eid"),
                        {"eid": elder_id},
                    )
                else:
                    db.execute(
                        text(f"DELETE FROM {tbl} WHERE {c} = :eid"),
                        {"eid": elder_id},
                    )
            touched.append(f"{table_name}.{col}")
        except ProgrammingError:
            continue
    return touched


class CustomerDeleteService:
    @staticmethod
    def permanently_delete_elder_prospect(
        db: Session,
        prospect_id: int,
        user: User,
    ) -> dict:
        _require_admin(user)
        row = db.query(ElderProspect).filter(ElderProspect.id == prospect_id).first()
        if not row:
            raise_not_found("Prospect not found")
        assert_tenant_access(user, row.tenant_id)
        tid = resolve_tenant_id(user)
        if tid is not None and row.tenant_id != tid:
            raise_not_found("Prospect not found")

        db.query(PipelineActivity).filter(
            PipelineActivity.elder_prospect_id == row.id
        ).delete(synchronize_session=False)

        db.query(HomeSafetyAssessmentRecord).filter(
            HomeSafetyAssessmentRecord.prospect_id == row.id
        ).update({HomeSafetyAssessmentRecord.prospect_id: None}, synchronize_session=False)
        if _table_exists(db, "home_safety_ai_jobs"):
            db.query(HomeSafetyAIJob).filter(HomeSafetyAIJob.prospect_id == row.id).update(
                {HomeSafetyAIJob.prospect_id: None}, synchronize_session=False
            )

        docs = _delete_documents(db, entity_type="elder_prospect", entity_id=row.id)
        name = f"{row.first_name} {row.last_name}".strip()
        pid = row.id
        db.delete(row)
        db.commit()
        return {
            "deleted": "elder_prospect",
            "id": pid,
            "name": name,
            "documents_removed": docs,
        }

    @staticmethod
    def permanently_delete_elder(
        db: Session,
        elder_id: int,
        user: User,
    ) -> dict:
        _require_admin(user)
        elder = db.query(Elder).filter(Elder.id == elder_id).first()
        if not elder:
            raise_not_found("Client not found")
        assert_tenant_access(user, elder.tenant_id)
        tid = resolve_tenant_id(user)
        if tid is not None and elder.tenant_id != tid:
            raise_not_found("Client not found")
        if _has_tax_invoices(db, elder.id):
            raise_bad_request(
                "This client has tax invoices — use Delete personal data (DPDP) instead"
            )

        db.query(User).filter(User.elder_id == elder.id).update(
            {User.elder_id: None}, synchronize_session=False
        )
        if FamilyElderLink is not None and _table_exists(db, "family_elder_links"):
            db.query(FamilyElderLink).filter(FamilyElderLink.elder_id == elder.id).delete(
                synchronize_session=False
            )

        prospect_ids = [
            p.id
            for p in db.query(ElderProspect.id)
            .filter(ElderProspect.converted_elder_id == elder.id)
            .all()
        ]
        db.query(ElderProspect).filter(
            ElderProspect.converted_elder_id == elder.id
        ).update({ElderProspect.converted_elder_id: None}, synchronize_session=False)

        if _table_exists(db, "home_safety_assessments"):
            db.query(HomeSafetyAssessmentRecord).filter(
                HomeSafetyAssessmentRecord.elder_id == elder.id
            ).update({HomeSafetyAssessmentRecord.elder_id: None}, synchronize_session=False)
        if _table_exists(db, "home_safety_ai_jobs"):
            db.query(HomeSafetyAIJob).filter(HomeSafetyAIJob.elder_id == elder.id).update(
                {HomeSafetyAIJob.elder_id: None}, synchronize_session=False
            )

        _release_document_refs(db, entity_type="elder", entity_id=elder.id)
        docs = _delete_documents(db, entity_type="elder", entity_id=elder.id)
        _purge_visit_graph(db, elder.id)
        fk_cleared = _clear_all_elder_foreign_keys(db, elder.id)

        name = f"{elder.first_name} {elder.last_name}".strip()
        eid = elder.id
        try:
            db.delete(elder)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            detail = exc.orig if getattr(exc, "orig", None) else exc
            raise_bad_request(
                "Could not permanently delete this client because related records "
                f"still reference it. Details: {detail}"
            )

        if db.query(Elder).filter(Elder.id == eid).first() is not None:
            raise_bad_request(f"Client #{eid} still exists after delete — contact support")

        return {
            "deleted": "elder",
            "id": eid,
            "name": name,
            "documents_removed": docs,
            "unlinked_prospect_ids": prospect_ids,
            "fk_cleared": fk_cleared,
        }
