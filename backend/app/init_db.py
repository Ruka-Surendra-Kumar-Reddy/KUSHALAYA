from app.core.database import Base, engine
from app.core.deploy import deploy_vertical
from app.models.packs import ensure_models_registered

ensure_models_registered(deploy_vertical())

print(f"Creating database tables for deploy vertical {deploy_vertical()}...")

Base.metadata.create_all(bind=engine)

from app.db_migrate import run_migrations

run_migrations()

print("Done.")
