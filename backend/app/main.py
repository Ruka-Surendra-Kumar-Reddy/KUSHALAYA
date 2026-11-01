from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from workforceos_core.exceptions import WorkforceHTTPError

from app.core import database  # noqa: F401 — register deploy models before API routes
from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import get_db
from app.core.health import readiness_report
from app.core.rbac import ADMIN_ROLES
from app.core.security import decode_token
from app.models.user import User
from app.release import RELEASE_ID
from app.core.logging_config import configure_logging
from app.core.telemetry import instrument_fastapi, setup_telemetry
from app.middleware.request_context import RequestContextMiddleware

configure_logging()
setup_telemetry()

def api_docs_urls(environment: str) -> dict:
    """Swagger/ReDoc/OpenAPI only outside production (the schema maps every endpoint)."""
    if (environment or "").strip().lower() == "production":
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}


app = FastAPI(
    title="SafeHomeOps API",
    version="1.0.0",
    description="SafeHomeOps API — SafeHome 360™ assessments, catalog, and family app",
    **api_docs_urls(settings.ENVIRONMENT),
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
instrument_fastapi(app)


@app.on_event("startup")
def _resume_ai_preview_jobs() -> None:
    """AI room preview renders run in-process; pick up any a restart interrupted."""
    from app.livewell.ai_render_queue import recover_pending

    recover_pending()


@app.exception_handler(WorkforceHTTPError)
async def workforce_http_error_handler(_request: Request, exc: WorkforceHTTPError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.get("/")
def root():
    return {
        "application": "WorkforceOS",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    """Alias for readiness (load balancers / App Service health check)."""
    report = readiness_report()
    status_code = 200 if report["status"] == "healthy" else 503
    return JSONResponse(content=report, status_code=status_code)


@app.get("/health/live")
def health_live():
    return {"status": "alive", "environment": settings.ENVIRONMENT, "release": RELEASE_ID}


@app.get("/health/ready")
def health_ready():
    report = readiness_report()
    status_code = 200 if report["status"] == "healthy" else 503
    return JSONResponse(content=report, status_code=status_code)


# /db-test used to be open on the public API and echoed the database backend.
# It stays available for local debugging, but on any public deployment
# (ENVIRONMENT=production or staging) it needs a bearer token for an admin
# account (SYSTEM_ADMIN / TENANT_ADMIN). `auto_error=False` so a missing header
# is a 401 we control rather than a 403 from HTTPBearer.
_db_test_bearer = HTTPBearer(auto_error=False)


def _is_production() -> bool:
    return (settings.ENVIRONMENT or "").strip().lower() in ("production", "prod", "staging")


def _require_admin_in_production(
    credentials: HTTPAuthorizationCredentials | None = Depends(_db_test_bearer),
    db: Session = Depends(get_db),
) -> None:
    if not _is_production():
        return
    if credentials is None:
        raise HTTPException(status_code=401, detail="Admin token required")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.email == payload.get("sub")).first()
    if not user or user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


@app.get("/db-test", dependencies=[Depends(_require_admin_in_production)])
def db_test():
    report = readiness_report()
    db = report["checks"]["database"]
    return {
        "database": db["detail"] if db["ok"] else "error",
        "status": "connected" if db["ok"] else "failed",
    }
