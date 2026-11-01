from datetime import date

from pydantic import BaseModel


class AssignmentFromMatchRequest(BaseModel):
    match_result_id: int
    start_date: date | None = None


class AssignmentCreate(BaseModel):
    elder_id: int
    caregiver_id: int
    match_score: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str = "ACTIVE"


class AssignmentEndRequest(BaseModel):
    end_date: date | None = None


class AssignmentResponse(BaseModel):
    id: int
    tenant_id: int
    elder_id: int
    caregiver_id: int
    match_score: float | None
    start_date: date | None
    end_date: date | None
    status: str

    model_config = {"from_attributes": True}
