from pydantic import BaseModel, Field


class CustomFieldDefinition(BaseModel):
    key: str
    label: str
    type: str = "text"
    required: bool = False
    section: str | None = "Custom"
    options: list[str] | None = None


class TenantFieldSchemasUpdate(BaseModel):
    elder_fields: list[CustomFieldDefinition] | None = None
    caregiver_fields: list[CustomFieldDefinition] | None = None
    demand_fields: list[CustomFieldDefinition] | None = Field(
        default=None,
        description="Platform alias for client/demand custom fields (maps to elder_fields)",
    )
    supply_fields: list[CustomFieldDefinition] | None = Field(
        default=None,
        description="Platform alias for worker/supply custom fields (maps to caregiver_fields)",
    )


class TenantFieldSchemasResponse(BaseModel):
    elder_fields: list[dict]
    caregiver_fields: list[dict]
    demand_fields: list[dict] = Field(
        default_factory=list,
        description="Platform alias — same as elder_fields for Elder Care vertical",
    )
    supply_fields: list[dict] = Field(
        default_factory=list,
        description="Platform alias — same as caregiver_fields",
    )
