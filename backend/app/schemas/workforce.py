from pydantic import BaseModel, Field


class BenchCaregiverRow(BaseModel):
    caregiver_id: int
    name: str
    category: str
    readiness_score: float
    readiness_band: str
    bench_days: int
    city: str | None = None
    languages: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    top_gaps: list[str] = Field(default_factory=list)


class BenchMetrics(BaseModel):
    total_bench: int
    by_category: dict[str, int]
    by_city: list[dict]
    by_language: list[dict]
    average_bench_days: float | None
    deployment_ready_count: int


class BenchResponse(BaseModel):
    tenant_id: int
    as_of_utc: str
    metrics: BenchMetrics
    caregivers: list[BenchCaregiverRow]


class WorkforceAlert(BaseModel):
    code: str
    severity: str
    title: str
    message: str
    metric_value: float | int | None = None


class RecruitmentFunnelStage(BaseModel):
    stage: str
    count: int


class WorkforceDashboardResponse(BaseModel):
    tenant_id: int
    as_of_utc: str
    workforce: dict
    elders: dict
    assignments: dict
    pipeline: dict
    operations: dict
    placement_velocity: dict
    recruitment_funnel: list[RecruitmentFunnelStage]
    alerts: list[WorkforceAlert]
    bench_summary: BenchMetrics
