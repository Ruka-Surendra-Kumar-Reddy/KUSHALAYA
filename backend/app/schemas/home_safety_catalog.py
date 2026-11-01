from pydantic import BaseModel, Field


class CatalogProductImage(BaseModel):
    document_id: int
    url: str = ""
    supplier_id: str | None = None
    photo_kind: str = "generic"  # generic | vendor


class CatalogProduct(BaseModel):
    id: str
    product_code: str | None = None
    name: str
    short_description: str = ""
    details: str = ""
    category: str = "General"
    category_prefix: str | None = None
    price_inr: int | None = None
    price_label: str = "Quote"
    sort_order: int = 0
    image_ids: list[int] = Field(default_factory=list)
    image_urls: list[str] = Field(default_factory=list)
    images: list[CatalogProductImage] = Field(default_factory=list)
    image_id: int | None = None
    image_url: str | None = None
    purpose: str = ""
    options: list[str] = Field(default_factory=list)
    material: str = ""
    installation_type: str = ""
    contractor_type: str = ""
    install_time: str = ""
    product_cost: str = ""
    installed_price: str = ""
    life_years: int | None = None
    maintenance_schedule: str = ""
    assessment_findings: list[str] = Field(default_factory=list)
    safety_improvement: int = 0
    solution_ids: list[str] = Field(default_factory=list)


class ServicePackage(BaseModel):
    id: str
    name: str
    tagline: str = ""
    description: str = ""
    price_inr: int | None = None
    price_label: str = "From"
    highlight: bool = False
    product_ids: list[str] = Field(default_factory=list)
    sort_order: int = 0


class CatalogCategoryType(BaseModel):
    prefix: str
    label: str
    kind: str = "product"  # service | product
    sort: int = 0
    active: bool = True


class SafetyCatalog(BaseModel):
    products: list[CatalogProduct]
    packages: list[ServicePackage]
    category_types: list[CatalogCategoryType] = Field(default_factory=list)
