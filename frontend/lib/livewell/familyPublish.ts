/** Stamp Independence Score + compact plan onto an assessment before server sync / family publish. */

import { withPublicBrand } from "@/lib/public-brand";
import type { AssessmentCategory, DomainScore, HomeSafetyAssessment } from "./assessment";
import { assessmentBand, computeDomainScores } from "./assessment";
import { EMPTY_RESIDENT_PROFILE } from "./resident-profile";
import { buildImprovementPlan } from "./improvement-plan";
import { carePathwayFor, type MembershipId } from "./livewell-rules";
import type { SolutionLibrary } from "./solution-types";
import { categoriesForAssessment } from "./conditional";

export type FamilyPublishedPlanItem = {
  id: string;
  title: string;
  priority: string;
  why?: string;
  actions: string[];
  score_gain: number;
  status: string;
  domain?: string;
  estimated_cost?: string;
};

export type FamilyPublishedPlan = {
  current_score: number;
  projected_score: number;
  finding_count: number;
  items: FamilyPublishedPlanItem[];
  estimated_cost_note?: string;
};

export type FamilyDomainScore = DomainScore;

export type FamilyCarePathway = {
  membership_id: MembershipId;
  membership_label: string;
  ecm_recommended: boolean;
  ecm_note: string;
};

export function stampFamilyPublishFields(
  assessment: HomeSafetyAssessment,
  categories: AssessmentCategory[],
  library: SolutionLibrary,
): HomeSafetyAssessment {
  categories = categoriesForAssessment(categories, assessment);
  const profile = assessment.residentProfile ?? EMPTY_RESIDENT_PROFILE;
  const grade = assessmentBand(categories, assessment.ratings, profile);
  const score = grade.score;
  const plan = buildImprovementPlan(assessment, categories, library);
  const { membershipId, ecm } = carePathwayFor(score, profile);

  const items: FamilyPublishedPlanItem[] = plan.entries.slice(0, 12).map((entry) => ({
    id: entry.solution.id,
    title: entry.solution.name || entry.solution.finding,
    priority: entry.solution.priority,
    why: entry.solution.riskDescription || undefined,
    actions: (entry.solution.recommendedSolutions || []).slice(0, 4),
    score_gain: entry.solution.scoreImprovement,
    status: "open",
    domain: entry.solution.section || undefined,
    estimated_cost: entry.solution.estimatedCost?.trim() || undefined,
  }));

  const costBits = items
    .map((i) => i.estimated_cost)
    .filter((c): c is string => Boolean(c))
    .slice(0, 4);
  const estimatedCostNote =
    costBits.length > 0
      ? withPublicBrand(
          `Indicative ranges from the plan: ${costBits.join(" · ")}. Final quote confirmed by LiveWell360.`,
        )
      : undefined;

  const domains = computeDomainScores(categories, assessment.ratings, profile);
  const topDomains = [...domains].sort((a, b) => a.score - b.score).slice(0, 3);
  const top = items.slice(0, 3).map((i) => i.title);
  const membershipLabel = carePathwayFor(score, profile).membershipLabel;
  const ecmNote = ecm
    ? "An Elder Care Manager (ECM) is recommended for ongoing coordination."
    : "ECM not required based on this assessment — your team remains available.";

  const summaryParts = [
    withPublicBrand(`LiveWell360 Safety Score ${score}/100 (${grade.label}).`),
  ];
  if (grade.capped) {
    summaryParts.push(
      `Band capped at ${grade.grade}: critical safety item(s) unsafe (${grade.criticalFindings
        .map((f) => f.label)
        .join("; ")}).`,
    );
  }
  // Family-facing: no internal pathway / membership names.
  if (top.length) summaryParts.push(`Top priorities: ${top.join("; ")}.`);
  if (topDomains.length) {
    summaryParts.push(
      `Areas to focus on: ${topDomains.map((d) => `${d.title.replace(/^\s*\d+[.)]\s*/, "")} ${d.score}`).join(", ")}.`,
    );
  }

  const shareBrief = [
    withPublicBrand(
      `LiveWell360 update for ${[assessment.clientFirstName, assessment.clientLastName].filter(Boolean).join(" ") || "our parent"}`,
    ),
    withPublicBrand(`LiveWell360 Safety Score: ${score}/100 (${grade.grade})`),
    top.length ? `Priorities: ${top.join("; ")}` : "No open improvement items",
    estimatedCostNote || "",
    withPublicBrand("— Shared from LiveWell360 Family"),
  ]
    .filter(Boolean)
    .join("\n");

  return {
    ...assessment,
    independenceScore: score,
    familyImprovementPlan: {
      current_score: plan.currentScore,
      projected_score: plan.projectedScore,
      finding_count: plan.findingCount,
      items,
      estimated_cost_note: estimatedCostNote,
    },
    familyDomainScores: domains,
    domainScores: Object.fromEntries(domains.map((d) => [d.id, d.score])),
    criticalFindings: grade.criticalFindings,
    familyCarePathway: {
      membership_id: membershipId,
      membership_label: membershipLabel,
      ecm_recommended: ecm,
      ecm_note: ecmNote,
    },
    familyScoreSummary: summaryParts.join(" "),
    familyShareBrief: shareBrief,
  };
}
