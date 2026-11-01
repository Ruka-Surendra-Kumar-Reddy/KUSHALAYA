import os
import sys
import types

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _stub_missing_module(name: str, **attrs) -> None:
    """LiveWell deploy omits some elder-care models; stub them so helper tests can import."""
    try:
        __import__(name)
    except ModuleNotFoundError:
        mod = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(mod, key, value)
        sys.modules[name] = mod


_stub_missing_module("app.models.incident", Incident=type("Incident", (), {}))
_stub_missing_module(
    "app.models.invoice",
    Invoice=type("Invoice", (), {}),
    InvoiceLine=type("InvoiceLine", (), {}),
    ElderBillingRate=type("ElderBillingRate", (), {}),
)
_stub_missing_module(
    "app.models.elder_requirement",
    ElderRequirement=type("ElderRequirement", (), {}),
)
_stub_missing_module(
    "app.services.monitoring_service",
    MonitoringService=type("MonitoringService", (), {"summary": staticmethod(lambda *a, **k: {})}),
)

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("UPLOAD_DIR", "test_uploads")
os.environ.setdefault("ENABLE_TELEMETRY", "false")
os.environ.setdefault("ENVIRONMENT", "test")

from app.core.database import Base, get_db
import app.models  # noqa: F401 — register deploy pack tables
import importlib
from pathlib import Path

# Tests import extra workforce models (assignments, attendance, …) that are
# outside the LiveWell pack. Register every model module so create_all can
# resolve foreign keys.
_models_dir = Path(__file__).resolve().parents[1] / "app" / "models"
for _path in sorted(_models_dir.glob("*.py")):
    if _path.stem.startswith("_") or _path.stem in {"packs", "mixins"}:
        continue
    try:
        importlib.import_module(f"app.models.{_path.stem}")
    except Exception:
        pass

from app.core.security import hash_password
from app.main import app
from app.models.caregiver import Caregiver as CaregiverModel
from app.models.elder import Elder as ElderModel
from app.models.skill import Skill as SkillModel
from app.models.tenant import Tenant as TenantModel
from app.models.user import User as UserModel

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def seed_tenant(db):
    tenant = TenantModel(
        name="Test Care Agency",
        email="agency@test.example",
        phone="+1-555-0100",
        address="1 Test St",
        city="Testville",
        state="TS",
        theme="classic",
        portal_title="Test Care",
    )
    db.add(tenant)
    db.flush()

    admin = UserModel(
        email="admin@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Test",
        last_name="Admin",
        role="TENANT_ADMIN",
        tenant_id=tenant.id,
    )
    manager = UserModel(
        email="manager@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Test",
        last_name="Manager",
        role="CARE_MANAGER",
        tenant_id=tenant.id,
    )
    viewer = UserModel(
        email="viewer@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Test",
        last_name="Viewer",
        role="VIEWER",
        tenant_id=tenant.id,
    )
    db.add_all([admin, manager, viewer])
    db.flush()

    skill = SkillModel(code="NURSING", name="Nursing", category="Clinical")
    db.add(skill)
    db.flush()

    elder = ElderModel(
        tenant_id=tenant.id,
        first_name="Elder",
        last_name="One",
        care_level="High",
        custom_attributes={
            "language_preference": "English",
            "required_experience_years": 2,
            "latitude": 17.4,
            "longitude": 78.4,
            "care_type": "visit_based",
            "schedule_requirements": {"days": ["mon", "wed"]},
        },
    )
    caregiver = CaregiverModel(
        tenant_id=tenant.id,
        first_name="Care",
        last_name="Giver",
        years_experience=5,
        police_verification_status="VERIFIED",
        background_check_status="VERIFIED",
        custom_attributes={
            "languages": ["English"],
            "latitude": 17.41,
            "longitude": 78.41,
            "availability": {"days": ["mon", "wed", "fri"], "care_type": "visit_based"},
        },
    )
    # The seed client is in the test manager's team (managers see only their team).
    elder.manager_user_id = manager.id
    caregiver.manager_user_id = manager.id
    db.add_all([elder, caregiver])
    db.commit()

    return {
        "tenant": tenant,
        "admin": admin,
        "manager": manager,
        "viewer": viewer,
        "elder": elder,
        "caregiver": caregiver,
        "skill": skill,
    }


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_headers(client, seed_tenant):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.example", "password": "testpass123"},
    )
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def auth_headers(client, seed_tenant):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "manager@test.example", "password": "testpass123"},
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
