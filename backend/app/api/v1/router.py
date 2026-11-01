from fastapi import APIRouter

from app.api.v1 import (
    activity,
    auth,
    caregiver_portal,
    emergency_partner_public,
    gateway_http_public,
    live_track_public,
    team,
    jobs,
    schedule,
    commerce,
    caregivers,
    documents,
    elders,
    geocode,
    home_safety_ai,
    home_safety_assessments,
    home_safety_catalog,
    public_enquiries,
    home_safety_dashboard,
    home_safety_family,
    home_safety_master_data,
    home_safety_pricing,
    home_safety_recommendation_chat,
    home_safety_rubric,
    home_safety_signed_docs,
    home_safety_solutions,
    home_safety_suppliers,
    home_safety_visits,
    client_profile,
    client_care,
    client_care,
    family_contacts,
    incidents,
    incident_reports,
    iot,
    platform,
    prospects,
    sales,
    subscriptions,
    tenants,
    users,
    webhooks,
    workflows,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(activity.router)
api_router.include_router(tenants.router)
api_router.include_router(users.router)
api_router.include_router(prospects.router)
api_router.include_router(sales.router)
api_router.include_router(elders.router)
api_router.include_router(caregivers.router)
api_router.include_router(caregiver_portal.router)
api_router.include_router(caregiver_portal.staff_router)
api_router.include_router(team.router)
api_router.include_router(jobs.router)
api_router.include_router(schedule.router)
api_router.include_router(schedule.caregiver_router)
api_router.include_router(commerce.router)
from app.api.v1 import business as business_api  # noqa: E402  (Phase 5B #101-#103)

api_router.include_router(business_api.router)
api_router.include_router(business_api.family_router)
api_router.include_router(documents.router)
api_router.include_router(geocode.router)
api_router.include_router(webhooks.router)
api_router.include_router(iot.router)
api_router.include_router(incidents.router)
from app.api.v1 import sos_siren as _sos_siren  # noqa: E402  (C1 SOS siren)

api_router.include_router(_sos_siren.router)
from app.api.v1 import push_devices as _push_devices  # noqa: E402  (Android app SOS alarm)

api_router.include_router(_push_devices.router)
from app.api.v1 import vendors as _vendors  # noqa: E402  (Sales -> Vendors)

api_router.include_router(_vendors.router)
api_router.include_router(incident_reports.router)
api_router.include_router(incident_reports.checklist_router)
api_router.include_router(incident_reports.caregiver_router)
api_router.include_router(incident_reports.family_router)
api_router.include_router(client_profile.router)
from app.api.v1 import kushlife_quality as _kl_quality  # noqa: E402  (K3 #100, ratings/NPS #106)

api_router.include_router(_kl_quality.router)
api_router.include_router(_kl_quality.jobs_router)
api_router.include_router(_kl_quality.caregiver_router)
api_router.include_router(_kl_quality.family_router)
api_router.include_router(client_care.router)
api_router.include_router(client_care.handover_router)
api_router.include_router(client_care.family_router)
api_router.include_router(client_care.caregiver_router)
api_router.include_router(family_contacts.family_router)
api_router.include_router(family_contacts.staff_router)
api_router.include_router(subscriptions.router)
api_router.include_router(workflows.router)
api_router.include_router(platform.router)

api_router.include_router(home_safety_catalog.router)
api_router.include_router(public_enquiries.router)
from app.api.v1 import plan_purchases  # noqa: E402  (website Buy now, 30 Oct 2026)

api_router.include_router(plan_purchases.router)
from app.api.v1 import site_chat  # noqa: E402  (website chat answers)

api_router.include_router(site_chat.router)
from app.api.v1 import site_settings as _site_settings  # noqa: E402  FIX 107/108

api_router.include_router(_site_settings.router)
api_router.include_router(_site_settings.funnel_router)
api_router.include_router(_site_settings.family_router)
from app.api.v1 import blog as _blog  # noqa: E402  www /blog

api_router.include_router(_blog.router)
api_router.include_router(_blog.public_router)
api_router.include_router(emergency_partner_public.router)
api_router.include_router(live_track_public.router)
from app.api.v1 import contracts as _contracts  # noqa: E402  (contracts signed in the app)

api_router.include_router(_contracts.router)
api_router.include_router(_contracts.public_router)
api_router.include_router(_contracts.family_router)
api_router.include_router(gateway_http_public.router)
api_router.include_router(home_safety_dashboard.router)
api_router.include_router(home_safety_dashboard.nav_router)
api_router.include_router(home_safety_solutions.router)
api_router.include_router(home_safety_pricing.router)
api_router.include_router(home_safety_suppliers.router)
api_router.include_router(home_safety_master_data.router)
api_router.include_router(home_safety_rubric.router)
from app.api.v1 import privacy as privacy_api  # noqa: E402  (DPDP #104, backup status #105)

api_router.include_router(privacy_api.family_router)
api_router.include_router(privacy_api.router)
api_router.include_router(home_safety_family.router)
api_router.include_router(home_safety_family.care_router)
api_router.include_router(home_safety_visits.router)
api_router.include_router(home_safety_family.photos_router)
api_router.include_router(home_safety_signed_docs.router)
from app.api.v1 import home_safety_ai_hazards  # noqa: E402  (AI room hazard check)

api_router.include_router(home_safety_ai_hazards.router)
api_router.include_router(home_safety_ai_hazards.usage_router)
api_router.include_router(home_safety_ai_hazards.family_router)
from app.core.config import settings as _settings  # noqa: E402

api_router.include_router(home_safety_ai.router)
# Contract E mock GPU (in-memory) — dev/test only, admins only; never routed in production.
if (_settings.ENVIRONMENT or "").strip().lower() != "production":
    api_router.include_router(home_safety_ai.gpu_router)
from app.api.v1 import home_safety_ai_preview  # noqa: E402  (AI room preview)

api_router.include_router(home_safety_ai_preview.router)
api_router.include_router(home_safety_ai_preview.family_router)
api_router.include_router(home_safety_recommendation_chat.router)
api_router.include_router(home_safety_assessments.router)
from app.api.v1 import app_release as _app_release  # noqa: E402  (Android app self-update)

api_router.include_router(_app_release.router)
