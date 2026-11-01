"""Phase 5B: business details, GST invoices, owner dashboard, monthly exports.

See app/livewell/gst_invoices.py (numbering, GST maths) and
app/livewell/owner_reports.py (dashboard definitions, CSVs).
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import READ_ROLES, SYSTEM_ADMIN, TENANT_ADMIN, require_elder_portal, require_roles
from app.core.responses import raise_not_found
from app.core.team_scope import team_elder_ids
from app.livewell import gst_invoices, owner_reports
from app.livewell.commerce import _tenant
from app.models.tenant import Tenant
from app.models.user import User

router = APIRouter(prefix="/business", tags=["Business"])
family_router = APIRouter(prefix="/home-safety/family", tags=["Family invoices"])

ADMIN_ROLES = (SYSTEM_ADMIN, TENANT_ADMIN)


def _tenant_row(db: Session, user: User) -> Tenant:
    tenant = db.get(Tenant, _tenant(user))
    if not tenant:
        raise_not_found("Agency not found")
    return tenant


def _pdf(db: Session, inv) -> Response:
    return Response(
        content=gst_invoices.render_pdf(db, inv),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{inv.number.replace("/", "-")}.pdf"'},
    )


# --- Business details (admins) ----------------------------------------------------


@router.get("/details")
def get_details(db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    return gst_invoices.business_payload(_tenant_row(db, user))


@router.put("/details")
def put_details(body: dict, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    return gst_invoices.save_business(db, _tenant_row(db, user), body)


# --- Invoices (staff, team-scoped) ------------------------------------------------


@router.get("/invoices")
def list_invoices(
    elder_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*READ_ROLES)),
):
    tid = _tenant(user)
    scope = team_elder_ids(db, user)
    if elder_id is not None:
        scope = {elder_id} if scope is None or elder_id in scope else set()
    tenant = db.get(Tenant, tid)
    return {
        "gst_registered": bool(gst_invoices.get_business(tenant)["gstin"]),
        "invoices": gst_invoices.list_for_elders(db, tid, scope),
    }


@router.get("/invoices/shared/{token}")
def shared_invoice_pdf(token: str, db: Session = Depends(get_db)):
    """No-login PDF behind a signed, expiring token (sent by email / WhatsApp)."""
    from app.livewell.invoice_delivery import invoice_from_share_token

    inv = invoice_from_share_token(db, token)
    if inv is None:
        raise_not_found("This invoice link is invalid or has expired")
    return _pdf(db, inv)


@router.get("/invoices/{invoice_id}/pdf")
def invoice_pdf(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    inv = gst_invoices.get_visible(db, invoice_id, _tenant(user), team_elder_ids(db, user))
    return _pdf(db, inv)


# --- Owner dashboard and exports (admins) -----------------------------------------


@router.get("/owner-dashboard")
def owner_dashboard(
    month: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    tenant = _tenant_row(db, user)
    data = owner_reports.dashboard(db, tenant, owner_reports.parse_month(month))
    data["gst_registered"] = bool(gst_invoices.get_business(tenant)["gstin"])
    data["exports"] = [{"key": k, "label": v} for k, v in owner_reports.EXPORTS.items()]
    return data


@router.get("/exports/{kind}.csv")
def export_csv(
    kind: str,
    month: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    if kind not in owner_reports.EXPORTS:
        raise_not_found("Unknown export")
    tenant = _tenant_row(db, user)
    m = owner_reports.parse_month(month)
    # Build the whole file while the request's session is still open: FastAPI closes
    # `get_db` before a StreamingResponse body runs, so a lazy generator would read
    # from a closed session. One month of rows is small.
    body = "".join(owner_reports.export_csv(db, tenant, kind, m))
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="kushalaya-{kind}-{m:%Y-%m}.csv"'},
    )


# --- Family: only their own invoices ----------------------------------------------


def _family_scope(db: Session, user: User) -> tuple[int, set[int]]:
    from app.livewell.family_elder_access import list_linked_elders

    elders = list_linked_elders(db, user)
    return user.tenant_id, {e.id for e in elders}


@family_router.get("/invoices")
def family_invoices(db: Session = Depends(get_db), user: User = Depends(require_elder_portal)):
    tid, ids = _family_scope(db, user)
    return gst_invoices.list_for_elders(db, tid, ids, limit=100)


@family_router.get("/invoices/{invoice_id}/pdf")
def family_invoice_pdf(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(require_elder_portal)):
    tid, ids = _family_scope(db, user)
    return _pdf(db, gst_invoices.get_visible(db, invoice_id, tid, ids))
