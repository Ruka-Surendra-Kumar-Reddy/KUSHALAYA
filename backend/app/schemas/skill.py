from pydantic import BaseModel


class SkillCreate(BaseModel):
    code: str
    name: str
    category: str | None = None
    description: str | None = None


class SkillResponse(BaseModel):
    id: int
    code: str
    name: str
    category: str | None
    description: str | None

    model_config = {"from_attributes": True}


class ElderRequirementCreate(BaseModel):
    skill_id: int
    required: bool = True
    weight: int | None = None
    notes: str | None = None


class CaregiverSkillCreate(BaseModel):
    skill_id: int
    experience_years: int | None = None
    certified: bool = False
    certification_reference: str | None = None
