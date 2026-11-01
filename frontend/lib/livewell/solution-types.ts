/** LiveWell360 Solution Library v1 — Finding → Solution → Product. */

export type SolutionPriority = "critical" | "high" | "medium" | "low";
export type EvidenceLevel = "A" | "B" | "C";

export interface SafeHomeSolution {
  id: string;
  section: string;
  subcategory?: string;
  /** Outcome-oriented solution name (Library v1). */
  name?: string;
  finding: string;
  riskDescription: string;
  priority: SolutionPriority;
  recommendedSolutions: string[];
  contractorType: string;
  productCategories: string[];
  estimatedCost: string;
  installationTime: string;
  scoreImprovement: number;
  maintenanceRequirement?: string;
  futureUpgrades?: string;
  /** Rubric item ids — triggered when rated unsafe or acceptable */
  rubricItemIds: string[];
  sort_order: number;
  legacyIds?: string[];
  evidenceLevel?: EvidenceLevel;
  membershipImpact?: string;
  aiVisualization?: boolean;
  followUpDays?: number;
}

export interface SolutionLibrary {
  solutions: SafeHomeSolution[];
  schemaVersion?: number;
  libraryVersion?: string;
}

export const SOLUTION_PRIORITY_META: Record<
  SolutionPriority,
  { label: string; window: string }
> = {
  critical: { label: "Critical", window: "Within 7 days" },
  high: { label: "High", window: "Within 30 days" },
  medium: { label: "Medium", window: "Within 90 days" },
  low: { label: "Low", window: "Optional" },
};

export const EVIDENCE_LEVEL_META: Record<
  EvidenceLevel,
  { label: string; description: string }
> = {
  A: {
    label: "Level A",
    description: "Strong evidence or widely accepted clinical/home-safety practice",
  },
  B: {
    label: "Level B",
    description: "Moderate evidence or strong expert consensus",
  },
  C: {
    label: "Level C",
    description: "Emerging practice, optional enhancement, or comfort-focused",
  },
};

export const SOLUTION_PRIORITY_ORDER: SolutionPriority[] = [
  "critical",
  "high",
  "medium",
  "low",
];
