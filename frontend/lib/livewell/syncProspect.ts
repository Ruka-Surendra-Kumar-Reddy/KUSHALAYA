import type { AssessmentCategory, HomeSafetyAssessment } from "./assessment";
import {
  assessmentBand,
  formatAssessmentReport,
  prospectSummaryNotes,
} from "./assessment";
import { getCachedSolutions } from "./solutionApi";
import { getCachedCatalog } from "./catalogApi";
import { getCachedPricing } from "./pricingApi";
import { EMPTY_RESIDENT_PROFILE } from "./resident-profile";
import { loadReportAiVisualMerge } from "./report-visualizations";
import { getStoredAuth } from "@/lib/api";
import { withPublicBrand } from "@/lib/public-brand";
import {
  addElderActivity,
  convertElderProspect,
  createElderProspect,
  getElderProspect,
  updateElderProspect,
} from "@/lib/prospects";
import { linkAssessmentProspect } from "./storage";
import { categoriesForAssessment } from "./conditional";

/** Matches backend ActivityCreate.max_length (leave headroom for encoding). */
const ACTIVITY_BODY_MAX = 95_000;

function careLevelFromGrade(grade: string): string {
  const map: Record<string, string> = {
    Excellent: "Low risk — fully independent",
    Good: "Minor improvements recommended",
    "Moderate Risk": "Several improvements recommended",
    "High Risk": "Comprehensive intervention recommended",
    Critical: "Immediate safety and care coordination required",
    Platinum: "Low risk — excellent home safety",
    Gold: "Low risk — safe home",
    Silver: "Moderate risk — improvements recommended",
    Bronze: "High risk — safety upgrades needed",
    Red: "Critical risk — immediate action required",
  };
  return map[grade] ?? withPublicBrand("LiveWell360 assessment completed");
}

function prospectIntakePayload(assessment: HomeSafetyAssessment) {
  return {
    first_name: assessment.clientFirstName.trim(),
    last_name: assessment.clientLastName.trim() || "—",
    phone: assessment.clientPhone.trim() || null,
    email: assessment.clientEmail.trim() || null,
    address: assessment.clientAddress.trim() || null,
    source: "home_safety_assessment",
  };
}

function clipActivityBody(text: string): string {
  if (text.length <= ACTIVITY_BODY_MAX) return text;
  const notice =
    "\n\n[Report truncated for pipeline storage — use Copy report / Share report in the assessment for the full text.]";
  return text.slice(0, ACTIVITY_BODY_MAX - notice.length) + notice;
}

export function isPipelineSyncAvailable(): boolean {
  return Boolean(getStoredAuth()?.access_token);
}

/** Create or update the pipeline prospect before photos / AI artifacts (in-progress assessment). */
export async function ensureAssessmentCustomerLink(
  assessment: HomeSafetyAssessment,
): Promise<HomeSafetyAssessment> {
  if (assessment.prospectId || assessment.elderId) {
    return assessment;
  }
  if (!isPipelineSyncAvailable()) {
    throw new Error(withPublicBrand("Sign in to LiveWell360 to save photos and AI prompts to the client record."));
  }
  if (!assessment.clientFirstName.trim()) {
    throw new Error("Enter resident first name before saving photos or AI prompts to the client.");
  }

  const payload = {
    ...prospectIntakePayload(assessment),
    stage: "ASSESSMENT_SCHEDULED",
    notes: withPublicBrand(`LiveWell360 assessment ${assessment.id} in progress.`),
  };

  const created = await createElderProspect(payload);
  const prospectId = created.id;
  const elderId = (await getElderProspect(prospectId)).converted_elder_id ?? null;
  const now = new Date().toISOString();
  const linked =
    linkAssessmentProspect(assessment.id, prospectId, elderId) ??
    ({
      ...assessment,
      prospectId,
      elderId,
      prospectSyncedAt: now,
    } satisfies HomeSafetyAssessment);

  return { ...linked, prospectSyncedAt: linked.prospectSyncedAt ?? now };
}

/** Push completed assessment to elder prospect pipeline (requires sign-in). */
export async function syncAssessmentToProspect(
  assessment: HomeSafetyAssessment,
  categories: AssessmentCategory[],
): Promise<{ prospectId: number | null; elderId: number | null }> {
  const auth = getStoredAuth();
  if (!auth?.access_token) {
    throw new Error(withPublicBrand("Sign in to LiveWell360 to add this client to the pipeline."));
  }

  categories = categoriesForAssessment(categories, assessment);
  const profile = assessment.residentProfile ?? EMPTY_RESIDENT_PROFILE;
  const grade = assessmentBand(categories, assessment.ratings, profile);
  const summaryNotes = prospectSummaryNotes(assessment, categories);
  const aiVisualMerge = await loadReportAiVisualMerge(assessment.id);
  const report = formatAssessmentReport(
    assessment,
    categories,
    getCachedSolutions(),
    getCachedCatalog(),
    getCachedPricing(),
    { aiVisualMerge },
  );

  const payload = {
    ...prospectIntakePayload(assessment),
    stage: "ASSESSMENT_DONE",
    notes: summaryNotes,
    care_level: careLevelFromGrade(grade.grade),
  };

  // Already a client — no prospect needed.
  if (assessment.elderId && !assessment.prospectId) {
    return { prospectId: null, elderId: assessment.elderId };
  }

  let prospectId = assessment.prospectId;
  if (prospectId) {
    try {
      await updateElderProspect(prospectId, payload);
    } catch {
      // Prospect may already have been absorbed into a client.
      prospectId = null;
    }
  }
  if (!prospectId && !assessment.elderId) {
    const created = await createElderProspect(payload);
    prospectId = created.id;
  }

  if (prospectId) {
    try {
      await addElderActivity(prospectId, {
        activity_type: "VISIT",
        body: clipActivityBody(report),
      });
    } catch {
      // Activity is optional once convert absorbs the lead.
    }
  }

  const preferredElderId = assessment.elderId;
  let elderId: number | null = preferredElderId ?? null;

  if (prospectId) {
    const openProspectId = prospectId;
    try {
      const converted = await convertElderProspect(
        openProspectId,
        preferredElderId != null ? { elder_id: preferredElderId } : undefined,
      );
      elderId = converted.elder_id;
      prospectId = null; // lead absorbed into client
    } catch {
      try {
        const existing = await getElderProspect(openProspectId);
        elderId =
          preferredElderId ?? existing.converted_elder_id ?? null;
      } catch {
        elderId = preferredElderId ?? null;
        prospectId = null;
      }
    }
  }

  return { prospectId: null, elderId: elderId ?? preferredElderId ?? null };
}
