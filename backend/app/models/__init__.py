"""SQLAlchemy models — tables registered per DEPLOY_VERTICAL (see app.models.packs)."""

from app.models.packs import ensure_models_registered

ensure_models_registered()
