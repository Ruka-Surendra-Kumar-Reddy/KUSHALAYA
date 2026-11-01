from pydantic import BaseModel, Field


class SafeHomeSolution(BaseModel):
    id: str
    section: str = ""
    finding: str
    riskDescription: str = ""
    priority: str = "medium"
    recommendedSolutions: list[str] = Field(default_factory=list)
    contractorType: str = ""
    productCategories: list[str] = Field(default_factory=list)
    estimatedCost: str = ""
    installationTime: str = ""
    scoreImprovement: int = 0
    maintenanceRequirement: str = ""
    futureUpgrades: str = ""
    rubricItemIds: list[str] = Field(default_factory=list)
    sort_order: int = 0


class SolutionLibrary(BaseModel):
    solutions: list[SafeHomeSolution]
