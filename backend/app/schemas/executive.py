from pydantic import BaseModel, Field


class ExecutiveCriticalAlert(BaseModel):
    code: str
    level: str
    title: str
    message: str
    metric_label: str | None = None
    metric_value: float | int | None = None
    metric_value_display: str | None = None
    change_percent: float | None = None
    recommended_action: str


class ExecutiveDashboardResponse(BaseModel):
    tenant_id: int
    as_of_utc: str
    critical_alerts: list[ExecutiveCriticalAlert]
    executive_kpis: dict
    utilization: dict
    bench_intelligence: dict
    placement_intelligence: dict
    recruitment_funnel: list[dict]
    demand_forecast: dict
    readiness_tiers: dict
    attrition: dict
    financial: dict
    city_operations: list[dict]
    marketplace: dict
    ai_insights: list[dict]
    scorecard: dict
    executive_copilot_questions: list[str] = Field(default_factory=list)
    tenant_settings: dict = Field(default_factory=dict)
    workforce_base: dict
