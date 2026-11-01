DEFAULT_MONITORING_CONFIG = {
    "allowed_zones": [
        "living_room",
        "hallway",
        "entry",
        "medication_area",
    ],
    "restricted_zones": ["bathroom", "bedroom_private", "changing_area"],
    "notify_care_manager": True,
    "notify_family": True,
    "auto_incident_on_fall": True,
    "auto_incident_on_critical": True,
    "no_movement_hours": 4,
    "channels": ["email", "sms", "whatsapp"],
}


def merge_monitoring_config(raw: dict | None) -> dict:
    base = {**DEFAULT_MONITORING_CONFIG}
    if raw:
        base.update(raw)
    return base
