"""Phase 5B (#101 #102 #103): owner dashboard, GST invoices / credit notes, monthly CSV exports."""

import csv
import io
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.livewell import gst_invoices as gi
from app.livewell.family_elder_access import ensure_family_elder_link
from app.livewell.wallet_service import WalletService
from app.models.care_job import CareJob
from app.models.commerce import Order
from app.models.elder import Elder
from app.models.tax_invoice import InvoiceCounter, TaxInvoice
from app.models.user import User

F = "/api/v1/home-safety/family"
B = "/api/v1/business"
GSTIN = "36ABCDE1234F1Z5"


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _family(db, elder, tag):
    user = User(
        email=f"fam.{tag}.5b@test.example", password_hash=hash_password("testpass123"), first_name="Priya",
        last_name="Rao", role="ELDER_PORTAL", tenant_id=elder.tenant_id, elder_id=elder.id,
    )
    db.add(user)
    db.flush()
    ensure_family_elder_link(db, user, elder)
    db.commit()
    return user


def _top_up(db, elder, amount, key="t"):
    wallet = WalletService.get_or_create(db, elder)
    WalletService.record(db, wallet, kind="recharge", amount_minor=amount, idempotency_key=f"recharge:{key}{amount}")


def _paid_order(client, db, seed_tenant, fam_headers, qty=2):
    admin = _login(client, "admin@test.example")
    p = next(x for x in client.get("/api/v1/products", headers=admin).json() if x["name"] == "Fixed grab bar")
    client.put(f"/api/v1/products/{p['id']}", json={"cost_paise": 100000, "margin_bp": 3000}, headers=admin)
    order = client.post(
        "/api/v1/orders", json={"elder_id": seed_tenant["elder"].id, "lines": [{"product_id": p["id"], "qty": qty}]},
        headers=admin,
    ).json()
    client.post(f"/api/v1/orders/{order['id']}/status", json={"status": "quoted"}, headers=admin)
    res = client.post(f"{F}/quotes/{order['id']}/accept", headers=fam_headers).json()
    assert res["paid"] is True, res
    return admin, order


def _set_gstin(client, admin, gstin=GSTIN):
    res = client.put(f"{B}/details", json={"gstin": gstin, "legal_name": "Kushalaya Care Pvt Ltd"}, headers=admin)
    assert res.status_code == 200, res.text
    return res.json()


# --- Maths -----------------------------------------------------------------------


def test_split_and_inclusive_maths_in_paise():
    assert gi.split_tax(46800, True) == (23400, 23400, 0)
    assert gi.split_tax(101, True) == (51, 50, 0)  # odd paisa goes to CGST
    assert gi.split_tax(101, False) == (0, 0, 101)
    assert gi.taxable_from_inclusive(11800) == 10000
    assert gi.taxable_from_inclusive(100) == 85  # 84.75 rounds half up
    assert gi.taxable_from_inclusive(45000) == 38136
    for amount in (1, 99, 45000, 306801):
        t = gi.taxable_from_inclusive(amount)
        c, s, i = gi.split_tax(amount - t, True)
        assert t + c + s + i == amount


def test_financial_year_and_number_format():
    ist_apr1 = datetime(2027, 3, 31, 19, 0, tzinfo=timezone.utc)  # 00:30 on 1 Apr 2027 IST
    assert gi.financial_year(ist_apr1) == 2027
    assert gi.financial_year(datetime(2027, 3, 31, 18, 0, tzinfo=timezone.utc)) == 2026
    assert gi.financial_year(datetime(2026, 10, 7, tzinfo=timezone.utc)) == 2026
    assert gi.format_number("KUS", 2026, "invoice", 1) == "KUS2627/00001"
    assert gi.format_number("ABCDE", 2026, "credit_note", 12) == "ABCDE2627C/00012"
    assert len(gi.format_number("ABCDE", 2026, "credit_note", 99999)) <= 16


# --- Numbering -------------------------------------------------------------------


def test_numbering_gapless_and_rollback_does_not_burn(db, seed_tenant):
    tid = seed_tenant["tenant"].id
    assert gi.allocate_number(db, tid, 2026, "INV") == 1
    nested = db.begin_nested()
    assert gi.allocate_number(db, tid, 2026, "INV") == 2
    nested.rollback()  # a failed payment: its number goes back
    assert gi.allocate_number(db, tid, 2026, "INV") == 2
    assert gi.allocate_number(db, tid, 2026, "CN") == 1  # separate series
    assert gi.allocate_number(db, tid, 2027, "INV") == 1  # new financial year restarts


def test_numbering_concurrent_safe(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'counter.db'}", connect_args={"timeout": 30})
    InvoiceCounter.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    got, errors = [], []

    def worker():
        for _ in range(5):
            s = Session()
            try:
                got.append(gi.allocate_number(s, 1, 2026, "INV"))
                s.commit()
            except Exception as exc:  # pragma: no cover - surfaced below
                errors.append(exc)
                s.rollback()
            finally:
                s.close()

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert sorted(got) == list(range(1, 31))
    engine.dispose()


# --- Invoices --------------------------------------------------------------------


def test_admin_only_and_gstin_validation(client, seed_tenant, auth_headers):
    for path in (f"{B}/details", f"{B}/owner-dashboard", f"{B}/exports/dues.csv"):
        assert client.get(path, headers=auth_headers).status_code == 403
    admin = _login(client, "admin@test.example")
    d = client.get(f"{B}/details", headers=admin).json()
    assert d["gst_registered"] is False and d["default_sac"] == "9993" and d["state_code"] == "36"
    assert client.put(f"{B}/details", json={"gstin": "12345"}, headers=admin).status_code == 400
    assert client.put(f"{B}/details", json={"invoice_prefix": "TOOLONG"}, headers=admin).status_code == 400
    saved = _set_gstin(client, admin, "29ABCDE1234F1Z5")
    assert saved["gst_registered"] is True and saved["state_code"] == "29"


def test_no_gstin_issues_bill_of_supply(client, db, seed_tenant):
    elder = seed_tenant["elder"]
    fam = _family(db, elder, "bos")
    _top_up(db, elder, 500_000)
    admin, order = _paid_order(client, db, seed_tenant, _login(client, fam.email))
    inv = db.query(TaxInvoice).filter(TaxInvoice.source_type == "order", TaxInvoice.source_id == str(order["id"])).one()
    assert inv.doc_type == "bill_of_supply" and inv.kind == "invoice"
    assert inv.cgst_paise == inv.sgst_paise == inv.igst_paise == 0
    assert inv.total_paise == order["total_paise"]
    listed = client.get(f"{B}/invoices", headers=admin).json()
    assert listed["gst_registered"] is False
    assert listed["invoices"][0]["title"] == "Bill of supply / receipt"


def test_order_invoice_cgst_sgst_and_credit_note(client, db, seed_tenant):
    elder = seed_tenant["elder"]
    fam = _family(db, elder, "gst")
    _top_up(db, elder, 500_000)
    admin = _login(client, "admin@test.example")
    _set_gstin(client, admin)
    _, order = _paid_order(client, db, seed_tenant, _login(client, fam.email))
    inv = db.query(TaxInvoice).filter(TaxInvoice.kind == "invoice", TaxInvoice.source_id == str(order["id"])).one()
    assert inv.doc_type == "tax_invoice" and inv.intra_state is True
    assert inv.taxable_paise == 260000
    assert (inv.cgst_paise, inv.sgst_paise, inv.igst_paise) == (23400, 23400, 0)
    assert inv.taxable_paise + inv.cgst_paise + inv.sgst_paise == inv.total_paise == order["total_paise"]
    assert inv.number.endswith("/00001") and inv.supplier["gstin"] == GSTIN
    assert inv.lines[0]["hsn_sac"] == "9993" and inv.lines[0]["qty"] == 2

    # Cancel after payment: refund to the wallet + credit note against the invoice.
    res = client.post(f"/api/v1/orders/{order['id']}/status", json={"status": "cancelled"}, headers=admin)
    assert res.status_code == 200, res.text
    cn = db.query(TaxInvoice).filter(TaxInvoice.kind == "credit_note", TaxInvoice.source_id == str(order["id"])).one()
    assert cn.original_invoice_id == inv.id and cn.total_paise == inv.total_paise
    assert "C/00001" in cn.number
    rows = client.get(f"{B}/invoices", headers=admin).json()["invoices"]
    assert rows[0]["kind"] == "credit_note" and rows[0]["original_number"] == inv.number

    pdf = client.get(f"{B}/invoices/{inv.id}/pdf", headers=admin)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_other_state_is_igst_and_service_request_inclusive(client, db, seed_tenant):
    admin = _login(client, "admin@test.example")
    _set_gstin(client, admin)
    elder = Elder(tenant_id=seed_tenant["tenant"].id, first_name="Out", last_name="State", status="ACTIVE",
                  custom_attributes={"state_code": "29"})
    db.add(elder)
    db.commit()
    inv = gi.issue_invoice(db, tenant_id=elder.tenant_id, elder_id=elder.id, source_type="service_request",
                           source_id="fsr_x1", amount_paise=45_000, note="Nurse / physiotherapy")
    db.commit()
    assert inv.intra_state is False and inv.place_of_supply == "29"
    assert (inv.taxable_paise, inv.cgst_paise, inv.sgst_paise, inv.igst_paise) == (38136, 0, 0, 6864)
    # Idempotent per source: a retried payment gets the same invoice, no new number.
    again = gi.issue_invoice(db, tenant_id=elder.tenant_id, elder_id=elder.id, source_type="service_request",
                             source_id="fsr_x1", amount_paise=45_000)
    assert again.id == inv.id


def test_service_request_payment_and_refund_via_wallet(client, db, seed_tenant):
    elder = Elder(tenant_id=seed_tenant["tenant"].id, first_name="Sr", last_name="Pay", status="ACTIVE",
                  manager_user_id=seed_tenant["manager"].id)
    db.add(elder)
    db.commit()
    fam = _family(db, elder, "sr")
    _top_up(db, elder, 100_000, "sr")
    fh = _login(client, fam.email)
    req_id = client.post(f"{F}/service-requests", headers=fh, json={"service_type": "home_repair"}).json()["id"]
    staff = _login(client, "manager@test.example")
    client.patch(f"/api/v1/home-safety/care/elders/{elder.id}/service-requests/{req_id}", headers=staff,
                 json={"status": "requested", "quoted_amount_minor": 20_000})
    assert client.post(f"{F}/service-requests/{req_id}/pay", headers=fh).status_code == 200
    assert client.post(f"{F}/service-requests/{req_id}/cancel", headers=fh).status_code == 200
    kinds = sorted(i.kind for i in db.query(TaxInvoice).filter(TaxInvoice.source_id == req_id))
    assert kinds == ["credit_note", "invoice"]


def test_family_sees_only_own_invoices(client, db, seed_tenant):
    elder = seed_tenant["elder"]
    fam = _family(db, elder, "own")
    _top_up(db, elder, 500_000)
    fh = _login(client, fam.email)
    _paid_order(client, db, seed_tenant, fh)
    other_elder = Elder(tenant_id=elder.tenant_id, first_name="Other", last_name="Family", status="ACTIVE")
    db.add(other_elder)
    db.commit()
    other = _login(client, _family(db, other_elder, "other").email)

    mine = client.get(f"{F}/invoices", headers=fh).json()
    assert len(mine) == 1 and mine[0]["elder_id"] == elder.id
    assert client.get(f"{F}/invoices/{mine[0]['id']}/pdf", headers=fh).content.startswith(b"%PDF")
    assert client.get(f"{F}/invoices", headers=other).json() == []
    assert client.get(f"{F}/invoices/{mine[0]['id']}/pdf", headers=other).status_code == 404
    # Staff routes are not open to families.
    assert client.get(f"{B}/invoices", headers=fh).status_code == 403


# --- Dashboard and CSVs ------------------------------------------------------------


def _csv(res):
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/csv")
    return list(csv.reader(io.StringIO(res.content.decode("utf-8-sig"))))


def test_dues_aging_buckets_and_dashboard(client, db, seed_tenant):
    admin = _login(client, "admin@test.example")
    elder = seed_tenant["elder"]
    now = datetime.now(timezone.utc)
    for days, total in ((5, 10_000), (45, 20_000), (75, 30_000), (120, 40_000)):
        db.add(Order(tenant_id=elder.tenant_id, elder_id=elder.id, status="quoted", lines=[], subtotal_paise=total,
                     total_paise=total, quoted_at=now - timedelta(days=days)))
    db.add(Order(tenant_id=elder.tenant_id, elder_id=elder.id, status="cancelled", total_paise=99_999,
                 quoted_at=now - timedelta(days=10)))
    _top_up(db, elder, 123_450, "dash")
    db.commit()

    d = client.get(f"{B}/owner-dashboard", headers=admin)
    assert d.status_code == 200, d.text
    d = d.json()
    assert {a["bucket"]: a["amount_paise"] for a in d["dues"]["aging"]} == {
        "0-30": 10_000, "31-60": 20_000, "61-90": 30_000, "90+": 40_000,
    }
    assert d["dues"]["total_paise"] == 100_000
    assert d["cash"]["this_month_paise"] == 123_450
    assert d["satisfaction"]["available"] in (True, False)
    for key in ("pipeline", "margin", "visits", "sos", "reassessment", "utilisation", "clients"):
        assert key in d
    assert client.get(f"{B}/owner-dashboard?month=2026-13", headers=admin).status_code == 400

    rows = _csv(client.get(f"{B}/exports/dues.csv", headers=admin))
    assert rows[0][-1] == "Amount due (₹)"
    assert sorted(r[-1] for r in rows[1:]) == ["100.00", "200.00", "300.00", "400.00"]
    assert {r[6] for r in rows[1:]} == {"0-30", "31-60", "61-90", "90+"}


def test_gst_register_payments_visits_payroll_csv(client, db, seed_tenant):
    elder = seed_tenant["elder"]
    fam = _family(db, elder, "csv")
    _top_up(db, elder, 500_000, "csv")
    admin = _login(client, "admin@test.example")
    _set_gstin(client, admin)
    _, order = _paid_order(client, db, seed_tenant, _login(client, fam.email))

    now = datetime.now(timezone.utc)
    cg = seed_tenant["caregiver"]
    start = now.replace(hour=4, minute=0, second=0, microsecond=0)
    if start.astimezone(gi.IST).month != now.astimezone(gi.IST).month:  # keep it inside this IST month
        start = now
    db.add(CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, caregiver_id=cg.id, kind="visit", title="Visit",
                   status="completed", scheduled_at=start, checked_in_at=start,
                   completed_at=start + timedelta(minutes=90)))
    db.add(CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, caregiver_id=cg.id, kind="visit", title="Visit",
                   status="missed", scheduled_at=start))
    db.commit()
    month = now.astimezone(gi.IST).strftime("%Y-%m")

    reg = _csv(client.get(f"{B}/exports/gst-register.csv?month={month}", headers=admin))
    assert reg[0][:3] == ["Date (IST)", "Number", "Type"]
    row = reg[1]
    assert row[2] == "Tax invoice" and row[1].endswith("/00001")
    assert row[8:13] == ["2600.00", "234.00", "234.00", "0.00", "3068.00"]
    assert row[6] == "36-Telangana"

    pay = _csv(client.get(f"{B}/exports/payments.csv?month={month}", headers=admin))
    kinds = {r[4]: r[6] for r in pay[1:]}
    assert kinds["recharge"] == "5000.00" and kinds["debit"] == "-3068.00"

    visits = _csv(client.get(f"{B}/exports/visits.csv?month={month}", headers=admin))
    assert sorted(r[6] for r in visits[1:]) == ["completed", "missed"]

    payroll = _csv(client.get(f"{B}/exports/payroll.csv?month={month}", headers=admin))
    assert payroll[1][2] == "Care Giver"
    assert payroll[1][4:] == ["1", "1", "90", "1.50"]

    assert client.get(f"{B}/exports/nope.csv", headers=admin).status_code == 404


def test_hard_delete_refused_when_client_has_tax_invoices(client, db, seed_tenant):
    import pytest

    from app.services import customer_delete_service as cds

    elder = seed_tenant["elder"]
    fam = _family(db, elder, "hd")
    _top_up(db, elder, 500_000, "hd")
    _paid_order(client, db, seed_tenant, _login(client, fam.email))
    assert db.query(TaxInvoice).filter(TaxInvoice.elder_id == elder.id).count() == 1
    admin = db.query(User).filter(User.email == "admin@test.example").one()
    with pytest.raises(Exception) as exc:
        cds.CustomerDeleteService.permanently_delete_elder(db, elder.id, admin)
    assert getattr(exc.value, "status_code", None) == 400
    assert "DPDP" in str(exc.value.detail)
    assert db.query(TaxInvoice).filter(TaxInvoice.elder_id == elder.id).count() == 1
    assert db.query(Elder).filter(Elder.id == elder.id).count() == 1
    # The generic FK purge never lists the statutory tables.
    assert {"tax_invoices", "invoice_counters"} <= cds.PROTECTED_TABLES
    touched = cds._clear_all_elder_foreign_keys(db, elder.id)
    db.rollback()
    assert not any(t.startswith(("tax_invoices.", "invoice_counters.")) for t in touched)


def test_owner_csv_escapes_formula_cells(client, db, seed_tenant):
    admin = _login(client, "admin@test.example")
    elder = seed_tenant["elder"]
    elder.first_name, elder.last_name = "=HYPERLINK(1)", "@x"
    db.add(Order(tenant_id=elder.tenant_id, elder_id=elder.id, status="quoted", lines=[], subtotal_paise=500,
                 total_paise=500, quoted_at=datetime.now(timezone.utc) - timedelta(days=3)))
    db.commit()
    rows = _csv(client.get(f"{B}/exports/dues.csv", headers=admin))
    client_cell = rows[1][1]
    assert client_cell.startswith("'=") and rows[1][-1] == "5.00"
