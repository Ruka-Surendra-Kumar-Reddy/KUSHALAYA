from pydantic import BaseModel, Field

from app.schemas.home_safety_pricing import SafeHomePricingConfig


class MasterDataCatalogPhotoPreview(BaseModel):
    products_with_photos_before: int = 0
    products_with_photos_after: int = 0
    would_lose_photos: bool = False


class MasterDataFieldChange(BaseModel):
    entity: str
    id: str
    field: str
    before: object | None = None
    after: object | None = None
    change_type: str = "changed"


class MasterDataFieldDiff(BaseModel):
    dirty: bool = False
    change_count: int = 0
    truncated: bool = False
    by_entity: dict[str, int] = Field(default_factory=dict)
    changes: list[MasterDataFieldChange] = Field(default_factory=list)


class MasterDataImportResult(BaseModel):
    version_id: str
    status: str
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    diff: dict = Field(default_factory=dict)
    field_diff: MasterDataFieldDiff | dict = Field(default_factory=dict)
    sheets_found: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    workbook_meta: dict = Field(default_factory=dict)
    catalog_photo_preview: MasterDataCatalogPhotoPreview | None = None
    staged_pricing: SafeHomePricingConfig | None = None
    live_pricing: SafeHomePricingConfig | None = None
    pricing_from_workbook: bool = False
    pricing_edited_in_staging: bool = False


class MasterDataStagedPricingUpdate(BaseModel):
    pricing: SafeHomePricingConfig


class MasterDataApproveRequest(BaseModel):
    version_id: str
    confirm_catalog_photo_loss: bool = False


class MasterDataApproveResult(BaseModel):
    version_id: str
    status: str
    applied: list[str] = Field(default_factory=list)
    upload_id: str | None = None


class MasterDataVersionSummary(BaseModel):
    version_id: str | None = None
    approved_at: str | None = None
    approved_by: int | None = None
    comments: str = ""
    applied: list[str] = Field(default_factory=list)
    snapshot_summary: dict | None = None
    matches_current: bool = False
    is_latest_import: bool = False
    is_current_baseline: bool = False


class MasterDataCurrentSummary(BaseModel):
    summary: dict = Field(default_factory=dict)


class MasterDataSyncStatus(BaseModel):
    has_baseline: bool = False
    upload_id: str | None = None
    approved_at: str | None = None
    exported_at: str | None = None
    is_empty: bool = True
    requires_upload: bool = True
    dirty: bool = False
    drift: MasterDataFieldDiff | dict = Field(default_factory=dict)
    summary: dict = Field(default_factory=dict)
    message: str = ""


class RubricPayload(BaseModel):
    categories: list[dict] = Field(default_factory=list)
