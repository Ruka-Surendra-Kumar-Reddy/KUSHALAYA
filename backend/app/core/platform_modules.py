"""Re-export platform module registry from workforceos-core."""

from workforceos_core.platform_modules import PLATFORM_MODULES, list_platform_modules

__all__ = ["PLATFORM_MODULES", "list_platform_modules"]
