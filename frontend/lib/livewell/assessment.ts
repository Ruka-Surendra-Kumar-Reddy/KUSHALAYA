/** LiveWell360 Assessment — types, scoring, and report helpers. */

import { getApplicableCategories, getApplicableItems } from "./conditional";
import type { SafeHomePricingConfig } from "./pricing-types";
import type { SafetyCatalog } from "./catalog-types";
import type { SolutionLibrary } from "./solution-types";
import { EMPTY_RESIDENT_PROFILE, parseResidentAge, type ResidentProfile } from "./resident-profile";
import { LWA_RAW_MAX, LWA_TITLE, LWA_VERSION, SAFEHOME360_RAW_MAX, SAFEHOME360_TITLE, SAFEHOME360_VERSION } from "./lwa-rubric";
import { formatAssessmentReport as formatAssessmentReportImpl } from "./assessment-report";
import { withPublicBrand } from "@/lib/public-brand";

export type { ResidentProfile } from "./resident-profile";
export { LWA_VERSION, LWA_TITLE, LWA_RAW_MAX, SAFEHOME360_VERSION, SAFEHOME360_TITLE, SAFEHOME360_RAW_MAX };

/** Canonical SafeHome 360 ratings (+ legacy pass/partial/fail). */
export type SafeHomeRating = "excellent" | "acceptable" | "unsafe" | "na" | null;
export type LegacyRating = "pass" | "partial" | "fail";
export type ItemRating = SafeHomeRating | LegacyRating | null;

export type ScoringScale = "standard" | "critical";
export type AssessmentStatus = "draft" | "completed";

export type { RubricItemSource } from "./rubric-sources";

export type SkipRule = {
  field?: keyof ResidentProfile | string;
  equals?: boolean | string | number;
  notEquals?: boolean | string | number;
  /** Named profile rule — see conditional-rules.ts */
  when?: import("./conditional-rules").ConditionalRuleId;
};

export type AssessmentInputType = "rating" | "yesno" | "text";

export interface AssessmentItem {
  id: string;
  label: string;
  maxPoints: number;
  group?: string;
  scoringScale?: ScoringScale;
  skipWhen?: SkipRule;
  /** AARP HomeFit, CDC STEADI, or SafeHome 360™ proprietary */
  source?: import("./rubric-sources").RubricItemSource;
  /** Short assessor guidance shown behind a “?” next to the label */
  help?: string;
  /** How the assessor answers this item. Default rating. */
  inputType?: AssessmentInputType;
  /** Hidden from new assessments (kept for old reports). Nothing is deleted. */
  hidden?: boolean;
  /** Asked again on every care visit, not just the full assessment. */
  visitQuestion?: boolean;
  /** YYYY-MM-DD the question joined the rubric (old completed assessments skip it). */
  addedOn?: string;
  /** The question as asked in the home (falls back to the caregiver wording, then label). */
  ask?: string;
  /** Answer options the caregiver sees (1–8). Each saves a rating, so scoring is unchanged.
   *  Missing = standard options (see question-options.ts). */
  options?: QuestionOption[];
}

export type OptionRating = "excellent" | "acceptable" | "unsafe" | "na";
export type QuestionOption = { label: string; rating: OptionRating };

export interface AssessmentCategory {
  id: string;
  title: string;
  sectionNumber?: number;
  maxPoints: number;
  items: AssessmentItem[];
  skipWhen?: SkipRule;
}

export interface HomeSafetyAssessment {
  id: string;
  createdAt: string;
  updatedAt: string;
  completedAt: string | null;
  status: AssessmentStatus;
  /** Option the caregiver tapped per question (field app); report wording only. */
  answerLabels?: Record<string, string>;
  frameworkVersion?: string;
  clientFirstName: string;
  clientLastName: string;
  clientAddress: string;
  clientPhone: string;
  clientEmail: string;
  familyContactName: string;
  familyContactPhone: string;
  painPoints: string;
  assessorName: string;
  notes: string;
  residentProfile: ResidentProfile;
  ratings: Record<string, ItemRating>;
  itemNotes: Record<string, string>;
  prospectId: number | null;
  prospectSyncedAt: string | null;
  elderId: number | null;
  photos: AssessmentPhoto[];
  purchaseOrder?: import("./procurement-types").SafeHomePurchaseOrder | null;
  /** Assessor-customized customer quote (tiers, lines, quote inputs). */
  quoteCustomization?: AssessmentQuoteCustomization | null;
  /** Stamped on complete so backend can publish to family portal. */
  independenceScore?: number | null;
  familyImprovementPlan?: import("./familyPublish").FamilyPublishedPlan | null;
  familyScoreSummary?: string | null;
  familyDomainScores?: import("./familyPublish").FamilyDomainScore[] | null;
  familyCarePathway?: import("./familyPublish").FamilyCarePathway | null;
  familyShareBrief?: string | null;
  /** Domain id -> 0-100 score (dict form; familyDomainScores is the list form). */
  domainScores?: Record<string, number> | null;
  /** Critical-scale items rated unsafe — caps the Independence band at High Risk. */
  criticalFindings?: CriticalFinding[] | null;
  /** Server-side scoring stamps (backend/app/livewell/scoring.py). */
  clientReportedScore?: number | null;
  scoringSource?: string | null;
  serverScoredAt?: string | null;
  /** Rule-engine stamps from the server (assessment_service). */
  recommended_membership_id?: string | null;
  ecm_recommended?: boolean | null;
  risk_band?: string | null;
  risk_band_label?: string | null;
  ruleEngineSource?: string | null;
  /**
   * Transient: completed assessments are locked server-side. Set to true on the
   * save that follows "Reopen to edit"; never persisted.
   */
  reopen?: boolean;
}

export type CriticalFinding = { id: string; label: string; category: string };

export interface AssessmentPhoto {
  id: string;
  caption: string;
  roomType: string | null;
  localPreview: string | null;
  /** True when full image bytes live in IndexedDB (not localStorage). */
  hasLocalPreview?: boolean;
  documentId: number | null;
  uploadedAt: string | null;
}

/** Persisted assessor edits to the customer quote on review. */
export type AssessmentQuoteLineCustomization = {
  productId: string;
  included: boolean;
  source: "recommended" | "added";
};

export type AssessmentQuoteCustomization = {
  packageTiers: string[];
  /** null = follow recommended products for the selected tiers. */
  lines: AssessmentQuoteLineCustomization[] | null;
  /**
   * Product-id key from when `lines` was last customized.
   * When the recommended set changes (new ratings), lines are ignored and rebuilt.
   */
  recommendedProductKey?: string | null;
  quoteInputs?: {
    travel_km?: number;
    apply_weekend_surcharge?: boolean;
    apply_emergency_surcharge?: boolean;
    margin_percent_override?: number;
  };
};

export type LegacyHomeSafetyAssessment = HomeSafetyAssessment & { clientName?: string };

/** Merge partial/missing profile from sync or old drafts into a safe shape. */
export function normalizeResidentProfile(
  raw: ResidentProfile | null | undefined,
): ResidentProfile {
  const p = raw && typeof raw === "object" ? raw : {};
  return {
    ...EMPTY_RESIDENT_PROFILE,
    ...p,
    medicalConditions: Array.isArray(p.medicalConditions) ? p.medicalConditions : [],
  };
}

/**
 * Normalize assessments from localStorage, server sync, or partial JSON.
 * Prevents Review-step crashes on iPad when fields are missing after sync.
 */
export function normalizeAssessment(
  raw: LegacyHomeSafetyAssessment | HomeSafetyAssessment | null | undefined,
): HomeSafetyAssessment {
  if (!raw || typeof raw !== "object") {
    return createEmptyAssessment();
  }
  const legacyName = "clientName" in raw ? (raw.clientName?.trim() ?? "") : "";
  const split =
    raw.clientFirstName != null || raw.clientLastName != null
      ? { first: raw.clientFirstName ?? "", last: raw.clientLastName ?? "" }
      : splitClientName(legacyName);

  // `reopen` is a one-shot request flag — never let it persist locally.
  const { reopen: _reopen, ...rest } = raw;
  return {
    ...rest,
    id: typeof raw.id === "string" && raw.id ? raw.id : `hs-norm-${Date.now()}`,
    createdAt: raw.createdAt || new Date().toISOString(),
    updatedAt: raw.updatedAt || new Date().toISOString(),
    clientFirstName: split.first,
    clientLastName: split.last,
    clientAddress: typeof raw.clientAddress === "string" ? raw.clientAddress : "",
    clientPhone: typeof raw.clientPhone === "string" ? raw.clientPhone : "",
    clientEmail: raw.clientEmail ?? "",
    familyContactName: raw.familyContactName ?? "",
    familyContactPhone: raw.familyContactPhone ?? "",
    painPoints: raw.painPoints ?? "",
    assessorName: typeof raw.assessorName === "string" ? raw.assessorName : "",
    notes: typeof raw.notes === "string" ? raw.notes : "",
    ratings: raw.ratings && typeof raw.ratings === "object" ? raw.ratings : {},
    itemNotes: raw.itemNotes && typeof raw.itemNotes === "object" ? raw.itemNotes : {},
    residentProfile: normalizeResidentProfile(raw.residentProfile),
    prospectId: raw.prospectId ?? null,
    prospectSyncedAt: raw.prospectSyncedAt ?? null,
    elderId: raw.elderId ?? null,
    photos: Array.isArray(raw.photos) ? raw.photos : [],
    purchaseOrder: raw.purchaseOrder ?? null,
    status: raw.status ?? (raw.completedAt ? "completed" : "draft"),
    completedAt: raw.completedAt ?? null,
  };
}

/** Safe city fragment for vendor/quote helpers (never throws). */
export function assessmentJobCity(assessment: Pick<HomeSafetyAssessment, "clientAddress">): string {
  const address = typeof assessment.clientAddress === "string" ? assessment.clientAddress : "";
  return address.split(",").pop()?.trim() || "";
}

export function clientDisplayName(
  a: Pick<HomeSafetyAssessment, "clientFirstName" | "clientLastName">,
): string {
  return [a.clientFirstName, a.clientLastName].filter(Boolean).join(" ").trim();
}

export function splitClientName(full: string): { first: string; last: string } {
  const trimmed = full.trim();
  if (!trimmed) return { first: "", last: "" };
  const space = trimmed.indexOf(" ");
  if (space < 0) return { first: trimmed, last: "" };
  return { first: trimmed.slice(0, space), last: trimmed.slice(space + 1).trim() };
}

export interface SafetyGrade {
  grade: string;
  label: string;
  status: string;
}

/**
 * Independence Score™ bands (0–100).
 *
 * This is the ONE risk vocabulary: `grade` is the band name and `label` its
 * plain-language meaning. Reports, the score card and the family portal all
 * print these two strings; there is no separate "risk level" scale.
 * Mirrored by backend rule_engine_defaults.DEFAULT_RISK_RULES / BAND_DISPLAY.
 */
export const LWA_INDEPENDENCE_BANDS: {
  min: number;
  grade: string;
  label: string;
  status: string;
}[] = [
  { min: 90, grade: "Excellent", label: "Fully independent", status: "excellent" },
  { min: 75, grade: "Good", label: "Minor improvements recommended", status: "good" },
  { min: 60, grade: "Moderate Risk", label: "Several improvements recommended", status: "moderate" },
  { min: 40, grade: "High Risk", label: "Comprehensive intervention recommended", status: "high" },
  { min: 0, grade: "Critical", label: "Immediate safety and care coordination required", status: "critical" },
];

/** @deprecated Use LWA_INDEPENDENCE_BANDS */
export const SAFEHOME360_GRADE_TABLE = LWA_INDEPENDENCE_BANDS;

/** @deprecated Legacy A–F bands for old assessments */
export const GRADE_TABLE = LWA_INDEPENDENCE_BANDS;

export function normalizeRating(rating: ItemRating | undefined): SafeHomeRating {
  if (rating == null) return null;
  if (rating === "pass") return "excellent";
  if (rating === "partial") return "acceptable";
  if (rating === "fail") return "unsafe";
  return rating as SafeHomeRating;
}

export function ratingLabel(rating: ItemRating | undefined): string {
  const r = normalizeRating(rating);
  // Same words everywhere (caregiver app, reports, family portal).
  if (r === "excellent") return "Safe";
  if (r === "acceptable") return "Needs attention";
  if (r === "unsafe") return "Risk";
  if (r === "na") return "Doesn't apply";
  return "—";
}

export function itemPoints(
  rating: ItemRating,
  maxPoints: number,
  scale: ScoringScale = "standard",
): number {
  const r = normalizeRating(rating);
  if (r == null || r === "na") return 0;
  if (scale === "critical") {
    if (r === "excellent") return maxPoints;
    if (r === "acceptable") return Math.round(maxPoints * 0.5 * 10) / 10;
    return 0;
  }
  if (r === "excellent") return maxPoints;
  if (r === "acceptable") return Math.round(maxPoints * 0.5 * 10) / 10;
  return 0;
}

export function categoryScore(
  category: AssessmentCategory,
  ratings: Record<string, ItemRating>,
  profile: ResidentProfile = EMPTY_RESIDENT_PROFILE,
): number {
  const applicable = getApplicableCategories([category], profile, ratings)[0];
  if (!applicable) return 0;
  return applicable.items.reduce(
    (sum, item) =>
      sum + itemPoints(ratings[item.id] ?? null, item.maxPoints, item.scoringScale ?? "standard"),
    0,
  );
}

export function totalScore(
  categories: AssessmentCategory[],
  ratings: Record<string, ItemRating>,
  profile: ResidentProfile = EMPTY_RESIDENT_PROFILE,
): number {
  return getApplicableCategories(categories, profile, ratings).reduce(
    (sum, cat) => sum + categoryScore(cat, ratings, profile),
    0,
  );
}

/** Raw earned points (excludes N/A from denominator). */
export function scoredItemTotals(
  categories: AssessmentCategory[],
  ratings: Record<string, ItemRating>,
  profile: ResidentProfile = EMPTY_RESIDENT_PROFILE,
): { earned: number; max: number } {
  let earned = 0;
  let max = 0;
  for (const item of getApplicableItems(categories, profile, ratings)) {
    const r = normalizeRating(ratings[item.id]);
    if (r === "na") continue;
    max += item.maxPoints;
    earned += itemPoints(ratings[item.id] ?? null, item.maxPoints, item.scoringScale ?? "standard");
  }
  return { earned, max };
}

/** Independence Score™ normalized to 0–100. */
export function normalizedScore(
  categories: AssessmentCategory[],
  ratings: Record<string, ItemRating>,
  profile: ResidentProfile = EMPTY_RESIDENT_PROFILE,
): number {
  const { earned, max } = scoredItemTotals(categories, ratings, profile);
  if (max <= 0) return 0;
  return Math.round((earned / max) * 100);
}

const BAND_ORDER: Record<string, number> = {
  excellent: 0,
  good: 1,
  moderate: 2,
  high: 3,
  critical: 4,
};

/**
 * Band for a 0–100 score.
 *
 * `criticalUnsafe` — any item on the `critical` scoring scale rated unsafe caps
 * the band at High Risk (the numeric score is unchanged). See lwa-rubric.ts and
 * backend rule_engine_defaults.risk_band_for_score.
 */
export function safetyGradeFromScore(
  score0to100: number,
  opts: { criticalUnsafe?: boolean } = {},
): SafetyGrade & { capped: boolean } {
  let found: SafetyGrade | null = null;
  for (const row of LWA_INDEPENDENCE_BANDS) {
    if (score0to100 >= row.min) {
      found = { grade: row.grade, label: row.label, status: row.status };
      break;
    }
  }
  if (!found) {
    found = {
      grade: "Critical",
      label: "Immediate safety and care coordination required",
      status: "critical",
    };
  }
  // The band always matches the number on the printed scale (owner, 28 Oct: a 69
  // labelled "High Risk" next to a 60–74 = Moderate key confused everyone). A critical
  // item at risk is still flagged (capped) and listed first as Urgent; it no longer
  // lifts the band.
  return { ...found, capped: Boolean(opts.criticalUnsafe) };
}

export function safetyGrade(total: number, maxTotal: number): SafetyGrade {
  const pct = maxTotal > 0 ? (total / maxTotal) * 100 : 0;
  return safetyGradeFromScore(Math.round(pct));
}

/** Critical-scale items rated unsafe (applicable items only). */
export function criticalUnsafeItems(
  categories: AssessmentCategory[],
  ratings: Record<string, ItemRating>,
  profile: ResidentProfile = EMPTY_RESIDENT_PROFILE,
): CriticalFinding[] {
  const out: CriticalFinding[] = [];
  for (const cat of getApplicableCategories(categories, profile, ratings)) {
    for (const item of cat.items) {
      if ((item.scoringScale ?? "standard") !== "critical") continue;
      if (normalizeRating(ratings[item.id]) !== "unsafe") continue;
      out.push({ id: item.id, label: item.label, category: cat.title });
    }
  }
  return out;
}

export type AssessmentBand = SafetyGrade & {
  score: number;
  capped: boolean;
  criticalFindings: CriticalFinding[];
};

/** Score + band for an assessment, applying the critical-item cap. */
export function assessmentBand(
  categories: AssessmentCategory[],
  ratings: Record<string, ItemRating>,
  profile: ResidentProfile = EMPTY_RESIDENT_PROFILE,
): AssessmentBand {
  const score = normalizedScore(categories, ratings, profile);
  const criticalFindings = criticalUnsafeItems(categories, ratings, profile);
  const grade = safetyGradeFromScore(score, { criticalUnsafe: criticalFindings.length > 0 });
  return { ...grade, score, criticalFindings };
}

export type DomainScore = {
  id: string;
  title: string;
  score: number;
  max_points: number;
  earned_points: number;
};

/** Per-domain 0–100 scores (N/A excluded; unrated counts as 0). */
export function computeDomainScores(
  categories: AssessmentCategory[],
  ratings: Record<string, ItemRating>,
  profile: ResidentProfile = EMPTY_RESIDENT_PROFILE,
): DomainScore[] {
  const out: DomainScore[] = [];
  for (const cat of getApplicableCategories(categories, profile, ratings)) {
    let earned = 0;
    let max = 0;
    for (const item of cat.items) {
      const r = normalizeRating(ratings[item.id]);
      if (r === "na") continue;
      max += item.maxPoints;
      earned += itemPoints(ratings[item.id] ?? null, item.maxPoints, item.scoringScale ?? "standard");
    }
    if (max <= 0) continue;
    out.push({
      id: cat.id,
      title: cat.title,
      score: Math.round((earned / max) * 100),
      max_points: max,
      earned_points: Math.round(earned * 10) / 10,
    });
  }
  return out;
}

/** Safety Age™ — illustrative model from spec examples. */
export function safetyAge(residentAge: number, score0to100: number): number {
  const delta = Math.round((100 - score0to100) * 0.43);
  return Math.max(residentAge, residentAge + delta);
}

export function projectedSafetyAge(
  residentAge: number,
  score0to100: number,
  improvementPoints = 15,
): number {
  return safetyAge(residentAge, Math.min(100, score0to100 + improvementPoints));
}

export function completionPercent(
  categories: AssessmentCategory[],
  ratings: Record<string, ItemRating>,
  profile: ResidentProfile = EMPTY_RESIDENT_PROFILE,
): number {
  const items = getApplicableItems(categories, profile, ratings);
  const rated = items.filter((i) => normalizeRating(ratings[i.id]) != null).length;
  return items.length ? Math.round((rated / items.length) * 100) : 0;
}

export function categoryCompletion(
  category: AssessmentCategory,
  ratings: Record<string, ItemRating>,
): { answered: number; total: number; percent: number } {
  const total = category.items.length;
  const answered = category.items.filter(
    (item) => normalizeRating(ratings[item.id]) != null,
  ).length;
  return {
    answered,
    total,
    percent: total ? Math.round((answered / total) * 100) : 100,
  };
}

export function newAssessmentId(): string {
  return `hsa-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function createEmptyAssessment(): HomeSafetyAssessment {
  const now = new Date().toISOString();
  return {
    id: newAssessmentId(),
    createdAt: now,
    updatedAt: now,
    completedAt: null,
    status: "draft",
    frameworkVersion: LWA_VERSION,
    clientFirstName: "",
    clientLastName: "",
    clientAddress: "",
    clientPhone: "",
    clientEmail: "",
    familyContactName: "",
    familyContactPhone: "",
    painPoints: "",
    assessorName: "",
    notes: "",
    residentProfile: { ...EMPTY_RESIDENT_PROFILE },
    ratings: {},
    itemNotes: {},
    prospectId: null,
    prospectSyncedAt: null,
    elderId: null,
    photos: [],
  };
}

/** Family/ops report — see assessment-report.ts for structure and AI constraints. */
export function formatAssessmentReport(
  a: HomeSafetyAssessment,
  categories: AssessmentCategory[],
  solutions?: SolutionLibrary,
  catalog?: SafetyCatalog,
  pricing?: SafeHomePricingConfig,
  options?: import("./assessment-report").ReportOptions,
): string {
  return formatAssessmentReportImpl(a, categories, solutions, catalog, pricing, options);
}

export function prospectSummaryNotes(
  a: HomeSafetyAssessment,
  categories: AssessmentCategory[],
): string {
  const profile = a.residentProfile ?? EMPTY_RESIDENT_PROFILE;
  const band = assessmentBand(categories, a.ratings, profile);
  const parts = [
    withPublicBrand(
      `LiveWell360 Safety Score: ${band.score}/100 (${band.grade} — ${band.label})`,
    ),
  ];
  if (band.capped) {
    parts.push(
      `Band capped at High Risk: critical item(s) unsafe — ${band.criticalFindings
        .map((f) => f.label)
        .join("; ")}`,
    );
  }
  if (a.painPoints.trim()) parts.push(`Pain points: ${a.painPoints.trim()}`);
  if (a.notes.trim()) parts.push(`Recommendations: ${a.notes.trim()}`);
  return parts.join("\n");
}
