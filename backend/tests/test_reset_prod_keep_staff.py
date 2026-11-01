"""The production reset keeps configuration and the named staff, removes the rest."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import reset_prod_keep_staff as reset  # noqa: E402


def test_dry_run_plan_and_apply(db, seed_tenant):
    from app.models.elder import Elder
    from app.models.user import User

    tenant_id = seed_tenant["tenant"].id
    keeper = User(tenant_id=tenant_id, email="keep.me@kushalaya.com", password_hash="x",
                  first_name="Keep", last_name="Me", role="TENANT_ADMIN", status="ACTIVE")
    gone = User(tenant_id=tenant_id, email="gone@kushalaya.com", password_hash="x",
                first_name="Gone", last_name="User", role="CARE_MANAGER", status="ACTIVE")
    db.add_all([keeper, gone, Elder(tenant_id=tenant_id, first_name="Old", last_name="Client", status="ACTIVE")])
    db.commit()

    keep_ids, counts, doomed = reset.plan(db, ["keep.me@kushalaya.com"])
    assert keep_ids == [keeper.id]
    assert any(name == "elders" and n >= 1 for name, n in counts)
    assert any(r.email == "gone@kushalaya.com" for r in doomed)

    os.environ["CONFIRM"] = "RESET-PROD"
    reset.apply(db, keep_ids)
    assert db.query(Elder).count() == 0
    emails = {u.email for u in db.query(User).all()}
    assert emails == {"keep.me@kushalaya.com"}
    # configuration survives
    from app.models.tenant import Tenant
    assert db.query(Tenant).filter(Tenant.id == tenant_id).count() == 1


def test_unknown_keep_email_aborts(db, seed_tenant):
    import pytest
    with pytest.raises(SystemExit):
        reset.plan(db, ["nobody@kushalaya.com"])
