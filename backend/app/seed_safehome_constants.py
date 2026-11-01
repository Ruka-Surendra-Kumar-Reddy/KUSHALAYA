"""Shared LiveWell360 demo identity constants (seed + purge)."""

DEMO_PASSWORD = "demo1234"

TENANT_NAME = "LiveWell Demo"
LEGACY_TENANT_NAMES = ("SafeHome Demo", "Sunrise Elder Care")
CONTACT_EMAIL = "contact@livewell.example"

TENANT_ADMIN_EMAIL = "admin@sunrise-care.example"
MANAGER_EMAIL = "manager@sunrise-care.example"
ASSESSOR_EMAIL = "anita.caregiver@sunrise-care.example"
SUPER_ADMIN_EMAIL = "superadmin@livewellops.com"
LEGACY_SUPER_ADMIN_EMAILS = (
    "superadmin@safehomeops.com",
    "superadmin@eldercareops.com",
    "system@eldercareops.com",
)
LEGACY_ADMIN_EMAIL = "care_admin@tekmatrix.ai"

FAMILY_EMAILS = (
    "lakshmi.family@sunrise-care.example",
    "arjun.family@sunrise-care.example",
    "clairview.family@sunrise-care.example",
)

SEED_USER_EMAILS = (
    TENANT_ADMIN_EMAIL,
    MANAGER_EMAIL,
    ASSESSOR_EMAIL,
    *FAMILY_EMAILS,
)

SEED_CLIENTS = (
    ("Lakshmi", "Reddy"),
    ("Padmaja", "Posa"),
)

DEPLOY_VERTICAL = "LIVEWELL360"
LEGACY_VERTICALS = ("SAFEHOME360",)
