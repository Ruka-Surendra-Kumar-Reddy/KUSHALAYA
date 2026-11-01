/**
 * Family / ops assessment report.
 *
 * Recommendations come only from the rule-bound improvement plan + catalog.
 * AI is useful for (1) approved before/after room visuals and (2) optional
 * paraphrase of this structured brief — never for inventing solutions/products.
 */

import { withPublicBrand } from "@/lib/public-brand";
import type {
  AssessmentCategory,
  HomeSafetyAssessment,
} from "./assessment";
import {
  assessmentBand,
  categoryScore,
  clientDisplayName,
  normalizeRating,
  projectedSafetyAge,
  ratingLabel,
  safetyAge,
} from "./assessment";
import { getApplicableCategories, categoriesForAssessment } from "./conditional";
import type { SafetyCatalog } from "./catalog-types";
import { buildImprovementPlan, formatImprovementPlanText } from "./improvement-plan";
import {
  buildProductRecommendations,
  formatProductQuoteDraftText,
} from "./product-recommendations";
import { buildSafeHomeQuote, formatSafeHomeQuoteText } from "./pricing-engine";
import type { SafeHomePricingConfig } from "./pricing-types";
import { EMPTY_RESIDENT_PROFILE, parseResidentAge } from "./resident-profile";
import type { SolutionLibrary } from "./solution-types";
import { EVIDENCE_LEVEL_META } from "./solution-types";
import { LWA_TITLE, LWA_VERSION } from "./lwa-rubric";
import {
  MEMBERSHIP_LABELS,
  carePathwayFor,
  cognitiveRiskFromProfile,
  familyAbroadFromProfile,
  livesAloneFromProfile,
  riskBandForScore,
  type MembershipId,
} from "./livewell-rules";
import {
  formatAiVisualizationMergeSection,
  buildReportAiVisualMerge,
  type ApprovedRoomVisualization,
  type ReportAiVisualMerge,
} from "./report-visualizations";

const DIVIDER = "─".repeat(48);

export type ReportOptions = {
  /** Cap how many recommendation lines appear in the family summary (full list still in appendix). */
  familyPriorityLimit?: number;
  /**
   * AI merge status for publication. Prefer `aiVisualMerge`.
   * If only `approvedVisualizations` is passed, a merge object is derived.
   */
  aiVisualMerge?: ReportAiVisualMerge;
  /** @deprecated Prefer aiVisualMerge — treated as publishable non-stub visuals. */
  approvedVisualizations?: ApprovedRoomVisualization[];
};

/**
 * Structured facts for optional AI narrative polish.
 * Models must only rephrase these fields — not add products or diagnoses.
 */
export function buildReportNarrativeBrief(
  assessment: HomeSafetyAssessment,
  categories: AssessmentCategory[],
  solutions: SolutionLibrary,
  catalog?: SafetyCatalog,
): Record<string, unknown> {
  categories = categoriesForAssessment(categories, assessment);
  const profile = assessment.residentProfile ?? EMPTY_RESIDENT_PROFILE;
  const grade = assessmentBand(categories, assessment.ratings, profile);
  const score = grade.score;
  const band = riskBandForScore(score, { criticalUnsafe: grade.capped });
  const { membershipId: membership, ecm } = carePathwayFor(score, profile);
  const plan = buildImprovementPlan(assessment, categories, solutions, profile);
  const top = plan.entries.slice(0, 8).map((e) => ({
    id: e.solution.id,
    name: e.solution.name || e.solution.finding,
    priority: e.solution.priority,
    evidenceLevel: e.solution.evidenceLevel || "B",
    findings: e.findings.map((f) => f.itemLabel),
  }));

  return {
    resident: clientDisplayName(assessment) || "Resident",
    address: assessment.clientAddress || "",
    independenceScore: score,
    independenceBand: grade.grade,
    bandCappedByCriticalItem: grade.capped,
    criticalFindings: grade.criticalFindings.map((f) => f.label),
    riskBand: band.band,
    riskLabel: band.label,
    membershipId: membership,
    membershipLabel: MEMBERSHIP_LABELS[membership],
    ecmRecommended: ecm,
    findingCount: plan.findingCount,
    projectedScore: plan.projectedScore,
    topRecommendations: top,
    productCount: catalog
      ? buildProductRecommendations(plan, catalog).items.length
      : 0,
    assessorNotes: assessment.notes?.trim() || "",
    painPoints: assessment.painPoints?.trim() || "",
    constraint:
      "Do not invent medical diagnoses, products, prices, or solutions not listed in topRecommendations.",
  };
}

export function formatAssessmentReport(
  assessment: HomeSafetyAssessment,
  categories: AssessmentCategory[],
  solutions?: SolutionLibrary,
  catalog?: SafetyCatalog,
  pricing?: SafeHomePricingConfig,
  options: ReportOptions = {},
): string {
  categories = categoriesForAssessment(categories, assessment);
  const profile = assessment.residentProfile ?? EMPTY_RESIDENT_PROFILE;
  const grade = assessmentBand(categories, assessment.ratings, profile);
  const score = grade.score;
  const band = riskBandForScore(score, { criticalUnsafe: grade.capped });
  const age = parseResidentAge(profile);
  const name = clientDisplayName(assessment);
  const cognitiveRisk = cognitiveRiskFromProfile(profile);
  const familyAbroad = familyAbroadFromProfile(profile);
  const livesAlone = livesAloneFromProfile(profile);
  const { membershipId, ecm }: { membershipId: MembershipId; ecm: boolean } = carePathwayFor(
    score,
    profile,
  );

  const lines: string[] = [
    LWA_TITLE,
    "Professional aging-in-place assessment report",
    `Framework v${assessment.frameworkVersion ?? LWA_VERSION}`,
    DIVIDER,
    "",
    "1. RESIDENT & VISIT",
    `   Name: ${name || "—"}`,
    `   Address: ${assessment.clientAddress || "—"}`,
    `   Phone: ${assessment.clientPhone || "—"}`,
    `   Family contact: ${
      [assessment.familyContactName, assessment.familyContactPhone].filter(Boolean).join(" · ") ||
      "—"
    }`,
    `   Assessor: ${assessment.assessorName || "—"}`,
    `   Date: ${new Date(assessment.completedAt || assessment.updatedAt).toLocaleString()}`,
  ];

  if (livesAlone) lines.push("   Lives alone: Yes");
  if (familyAbroad) lines.push("   Family abroad (NRI pathway): Yes");
  if (cognitiveRisk && cognitiveRisk !== "none") {
    lines.push(`   Cognitive / neurological flag (from profile): ${cognitiveRisk}`);
  }
  if (profile.historyOfFalls) lines.push("   History of falls: Yes");
  if (assessment.painPoints?.trim()) {
    lines.push(`   Family priorities: ${assessment.painPoints.trim()}`);
  }

  lines.push(
    "",
    withPublicBrand("2. LiveWell360 SAFETY SCORE & RISK"),
    withPublicBrand(`   LiveWell360 Safety Score: ${score} / 100`),
    `   Independence band: ${grade.grade} — ${grade.label}`,
    `   Escalation: ${band.escalation}`,
  );
  if (grade.capped) {
    lines.push(
      `   Band capped at ${grade.grade}: critical item(s) rated unsafe — ${grade.criticalFindings
        .map((f) => f.label)
        .join("; ")}`,
    );
  }
  if (age != null) {
    lines.push(
      `   Safety Age™: ${safetyAge(age, score)} (chronological age ${age})`,
    );
  }

  lines.push(
    "",
    "3. CARE PATHWAY",
    `   Recommended membership: ${MEMBERSHIP_LABELS[membershipId]} (${membershipId})`,
    `   Elder Care Manager (ECM): ${ecm ? "Recommended" : "Not indicated from current flags"}`,
  );
  if (ecm) {
    lines.push(
      "   ECM note: Assignment and visit cadence follow tenant ECM rules after enrollment.",
    );
  }

  lines.push("", "4. ROOM BY ROOM");
  for (const cat of getApplicableCategories(categories, profile, assessment.ratings)) {
    const pts = Math.round(categoryScore(cat, assessment.ratings, profile));
    lines.push(`   ${cat.title}: ${pts} / ${cat.maxPoints}`);
  }

  const issueLines: string[] = [];
  for (const cat of getApplicableCategories(categories, profile, assessment.ratings)) {
    for (const item of cat.items) {
      const rating = assessment.ratings[item.id];
      const r = normalizeRating(rating);
      const note = assessment.itemNotes[item.id]?.trim();
      if (r === "unsafe" || r === "acceptable" || note) {
        issueLines.push(
          `   • [${cat.title}] ${item.label} — ${ratingLabel(rating)}${
            note ? ` (${note})` : ""
          }`,
        );
      }
    }
  }
  if (issueLines.length) {
    lines.push("", "5. FINDINGS (observed)", ...issueLines);
  } else {
    lines.push("", "5. FINDINGS (observed)", "   No unsafe/acceptable items recorded.");
  }

  if (solutions?.solutions?.length) {
    const plan = buildImprovementPlan(assessment, categories, solutions, profile);
    if (plan.entries.length) {
      const limit = options.familyPriorityLimit ?? 12;
      const familyEntries = plan.entries.slice(0, limit);
      lines.push(
        "",
        "6. RECOMMENDED SOLUTIONS (rule-linked)",
        `   Current score ${plan.currentScore} → projected ${plan.projectedScore} if priority items addressed (+${plan.totalScoreGain} est.)`,
      );
      if (age != null) {
        lines.push(
          `   Projected Safety Age™ after improvements: ${projectedSafetyAge(age, plan.currentScore, plan.totalScoreGain)}`,
        );
      }
      lines.push("");
      for (const entry of familyEntries) {
        const s = entry.solution;
        const title = s.name || s.finding;
        const evidence = s.evidenceLevel || "B";
        const evidenceNote = EVIDENCE_LEVEL_META[evidence]?.description || "";
        lines.push(`   ${title}`);
        lines.push(`      Priority: ${s.priority.toUpperCase()} · Evidence ${evidence}${evidenceNote ? ` (${evidenceNote})` : ""}`);
        if (s.riskDescription) lines.push(`      Why: ${s.riskDescription}`);
        if (s.recommendedSolutions?.length) {
          lines.push(`      Actions: ${s.recommendedSolutions.join("; ")}`);
        }
        if (s.productCategories?.length) {
          lines.push(`      Product categories: ${s.productCategories.join(", ")}`);
        }
        if (s.contractorType) lines.push(`      Professional: ${s.contractorType}`);
        if (s.estimatedCost) lines.push(`      Est. cost: ${s.estimatedCost}`);
        if (s.installationTime) lines.push(`      Est. time: ${s.installationTime}`);
        if (s.followUpDays) lines.push(`      Follow-up: ${s.followUpDays} days`);
        if (s.membershipImpact) lines.push(`      Membership fit: ${s.membershipImpact}`);
        if (s.aiVisualization) {
          lines.push("      AI visualization: Eligible (approved solution only)");
        }
        for (const f of entry.findings) {
          lines.push(`      From finding: ${f.itemLabel} (${ratingLabel(f.rating)})`);
        }
        lines.push("");
      }
      if (plan.entries.length > familyEntries.length) {
        lines.push(
          `   …and ${plan.entries.length - familyEntries.length} additional solution(s) in the full improvement plan below.`,
        );
      }

      lines.push("", "7. FULL IMPROVEMENT PLAN", formatImprovementPlanText(plan));

      if (catalog?.products?.length) {
        const quoteDraft = buildProductRecommendations(plan, catalog);
        lines.push("", "8. PRODUCT & SERVICE LINE ITEMS");
        if (quoteDraft.items.length) {
          lines.push(formatProductQuoteDraftText(quoteDraft));
          if (pricing) {
            const quote = buildSafeHomeQuote(quoteDraft, plan, pricing);
            if (quote) {
              lines.push("", "9. INVESTMENT ESTIMATE", formatSafeHomeQuoteText(quote, quoteDraft));
            }
          }
        } else {
          lines.push(
            "   Solutions matched, but no catalog products are linked yet.",
            "   Link products to solutions in Master Data / catalog.",
          );
          if (quoteDraft.unmappedSolutions.length) {
            lines.push(
              "   Unmapped solutions:",
              ...quoteDraft.unmappedSolutions.map((s) => `   • ${s.name || s.finding}`),
            );
          }
        }
      }
    } else {
      lines.push(
        "",
        "6. RECOMMENDED SOLUTIONS",
        "   No automated solutions — rated items are Excellent or N/A, or not yet linked in the solution library.",
      );
    }
  }

  const pkg = catalog?.packages?.find((p) => p.id === membershipId);
  if (pkg) {
    lines.push(
      "",
      "10. MEMBERSHIP PACKAGE SNAPSHOT",
      `   ${pkg.name}${pkg.tagline ? ` — ${pkg.tagline}` : ""}`,
    );
    if (pkg.description) lines.push(`   ${pkg.description}`);
    if (pkg.price_inr != null) {
      lines.push(
        `   From ₹${Number(pkg.price_inr).toLocaleString("en-IN")} ${pkg.price_label || ""}`.trim(),
      );
    }
  }

  lines.push(
    "",
    "11. NEXT STEPS",
    "   1. Review findings and priority solutions with the family.",
    "   2. Confirm membership pathway and ECM assignment if indicated.",
    "   3. Approve product/service scope and schedule installations.",
    "   4. Complete follow-ups per solution timelines (typically 7–30 days).",
  );

  if (assessment.notes.trim()) {
    lines.push("", "12. ASSESSOR NOTES", assessment.notes.trim());
  }

  const aiVisualMerge = resolveAiVisualMerge(options);
  lines.push(formatAiVisualizationMergeSection(aiVisualMerge));

  lines.push(
    "",
    DIVIDER,
    "Notes",
    withPublicBrand("• Solutions and products are selected by configured LiveWell360 rules and catalog links — not free-form AI."),
    "• Evidence Levels A/B/C describe practice strength; they are not a medical diagnosis.",
    "• Quote estimates are indicative; final pricing may vary after site confirmation.",
    aiVisualMerge.aiIncorporated
      ? "• Room visualizations above were human-approved before inclusion; they remain conceptual design aids only."
      : "• AI room visualizations were not incorporated into this report (none approved, stub-only, pending, failed, or unavailable).",
  );

  return lines.join("\n");
}

function resolveAiVisualMerge(options: ReportOptions): ReportAiVisualMerge {
  if (options.aiVisualMerge) return options.aiVisualMerge;
  const approved = options.approvedVisualizations ?? [];
  if (!approved.length) return buildReportAiVisualMerge([]);
  const incorporated = approved.filter((v) => !v.isStub);
  const stubApprovedCount = approved.filter((v) => v.isStub).length;
  const aiIncorporated = incorporated.length > 0;
  return {
    incorporated,
    approvedIncludingStubs: approved,
    incorporatedCount: incorporated.length,
    totalJobs: approved.length,
    pendingReviewCount: 0,
    stubApprovedCount,
    failedOrRejectedCount: 0,
    reason: aiIncorporated ? "incorporated" : stubApprovedCount ? "stub_only" : "no_jobs",
    summary: aiIncorporated
      ? `${incorporated.length} human-approved room visualization(s) will be merged into the report.`
      : stubApprovedCount
        ? `${stubApprovedCount} approved concept stub(s) only — stub/provider preview images are not merged into the family report.`
        : "No AI visualization jobs were run. The report will be created without AI room concepts.",
    aiIncorporated,
  };
}
