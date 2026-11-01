"""Resolve matching plugin for tenant vertical."""

from app.core.responses import raise_bad_request
from app.core.verticals import ELDER_CARE, normalize_vertical
from app.services.matching.plugins.elder_care import ElderCareMatchingPlugin

_PLUGINS = {
    ELDER_CARE: ElderCareMatchingPlugin,
}


def get_matching_plugin(vertical: str | None) -> ElderCareMatchingPlugin:
    key = normalize_vertical(vertical)
    plugin_cls = _PLUGINS.get(key)
    if plugin_cls is None:
        raise_bad_request(
            f"Matching is not configured for vertical {key}. "
            f"Supported: {', '.join(sorted(_PLUGINS))}"
        )
    return plugin_cls()
