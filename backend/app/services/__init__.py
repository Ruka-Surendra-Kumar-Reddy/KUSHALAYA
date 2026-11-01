"""Service layer — import modules directly (avoid eager elder-care imports).

SafeHomeOps registers a slim model pack. Do not re-export MatchingEngine /
MonitoringService / SchedulingService here — those pull elder_requirement and
other Elder Care–only models.
"""

__all__: list[str] = []
