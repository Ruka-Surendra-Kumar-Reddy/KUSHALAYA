/**
 * Report-safe projection of AI room visualizations and merge status.
 *
 * Only human-approved, non-stub concepts are incorporated into the published
 * report. Stub / failed / pending work never blocks report creation — the
 * report always states whether AI visuals were included or not.
 */

import {
  listVisualizationJobs,
  staffPhotoImageUrl,
  type AIVisualizationJob,
} from "./aiVisualizations";
import { withPublicBrand } from "@/lib/public-brand";

export const REPORT_VISUALIZATION_DISCLOSURE =
  "AI room visualizations are conceptual design aids only. They do not certify structural safety, product fit, wall substrate, or final installation. Final recommendations require assessor and qualified professional confirmation.";

export const REPORT_AI_NOT_INCORPORATED = withPublicBrand(
  "AI room visualizations were NOT incorporated into this report. Findings, scores, and recommendations below come from the LiveWell360 assessment rules and catalog only.",
);

export type ApprovedRoomVisualization = {
  aiJobId: string;
  assessmentId: string;
  roomType: string;
  packageLevel: string;
  sourceDocumentId: number;
  proposedDocumentId: number;
  sourceImageUrl: string;
  proposedImageUrl: string;
  recommendationLabels: string[];
  /** Catalog products selected for the after photo. */
  productLabels: string[];
  productCodes: string[];
  reviewedAt: string | null;
  reviewNotes: string | null;
  disclosure: string;
  provider: string | null;
  isStub: boolean;
};

export type ReportAiMergeReason =
  | "incorporated"
  | "no_jobs"
  | "pending_review"
  | "stub_only"
  | "rejected_or_failed"
  | "unavailable";

export type ReportAiVisualMerge = {
  /** Non-stub, human-approved concepts included in the published report. */
  incorporated: ApprovedRoomVisualization[];
  /** All completed+approved jobs (including stubs) — for assessor UI only. */
  approvedIncludingStubs: ApprovedRoomVisualization[];
  incorporatedCount: number;
  totalJobs: number;
  pendingReviewCount: number;
  stubApprovedCount: number;
  failedOrRejectedCount: number;
  reason: ReportAiMergeReason;
  /** Short UI / report line explaining merge outcome. */
  summary: string;
  aiIncorporated: boolean;
};

function labelsFromJob(job: AIVisualizationJob): string[] {
  const snap = job.phase_snapshot as
    | {
        recommendations?: { items?: { label?: string; solution_code?: string }[] };
        plan?: { render_items?: { label?: string; product_code?: string }[] };
      }
    | null
    | undefined;
  const fromRecs = (snap?.recommendations?.items || [])
    .map((i) => i.label || i.solution_code || "")
    .filter(Boolean);
  if (fromRecs.length) return fromRecs;
  const fromPlan = (snap?.plan?.render_items || [])
    .map((i) => i.label || i.product_code || "")
    .filter(Boolean);
  if (fromPlan.length) return fromPlan;
  return (job.approved_solution_ids || []).map(String);
}

function productLabelsFromJob(job: AIVisualizationJob): string[] {
  if (job.product_labels?.length) return [...job.product_labels];
  if (job.product_codes?.length) return [...job.product_codes];
  const snap = job.phase_snapshot as
    | {
        plan?: { render_items?: { label?: string; product_code?: string }[] };
      }
    | null
    | undefined;
  const fromPlan = (snap?.plan?.render_items || [])
    .filter((i) => i.product_code)
    .map((i) =>
      i.label && i.product_code
        ? `${i.label} (${i.product_code})`
        : i.product_code || i.label || "",
    )
    .filter(Boolean);
  return fromPlan;
}

function productCodesFromJob(job: AIVisualizationJob): string[] {
  if (job.product_codes?.length) return [...job.product_codes];
  const snap = job.phase_snapshot as
    | {
        plan?: { render_items?: { product_code?: string }[] };
      }
    | null
    | undefined;
  return [
    ...new Set(
      (snap?.plan?.render_items || [])
        .map((i) => (i.product_code || "").trim())
        .filter(Boolean),
    ),
  ];
}

export function isStubVisualizationJob(job: AIVisualizationJob): boolean {
  if (job.provider === "manual_upload") return false;
  const provenance = job.render_callback as { is_stub?: boolean } | null | undefined;
  return Boolean(provenance?.is_stub || job.provider === "local_stub");
}

function toApproved(j: AIVisualizationJob): ApprovedRoomVisualization {
  const proposedId = j.generated_document_id as number;
  return {
    aiJobId: j.ai_job_id,
    assessmentId: j.assessment_id,
    roomType: j.room_type,
    packageLevel: j.package_level,
    sourceDocumentId: j.source_document_id,
    proposedDocumentId: proposedId,
    sourceImageUrl: staffPhotoImageUrl(j.source_document_id),
    proposedImageUrl: staffPhotoImageUrl(proposedId),
    recommendationLabels: labelsFromJob(j),
    productLabels: productLabelsFromJob(j),
    productCodes: productCodesFromJob(j),
    reviewedAt: j.reviewed_at ?? null,
    reviewNotes: j.review_notes ?? null,
    disclosure: REPORT_VISUALIZATION_DISCLOSURE,
    provider: j.provider,
    isStub: isStubVisualizationJob(j),
  };
}

/** Project raw AI jobs into report-safe approved visualizations (includes stubs). */
export function projectApprovedVisualizations(
  jobs: AIVisualizationJob[],
): ApprovedRoomVisualization[] {
  return jobs
    .filter(
      (j) =>
        j.status === "completed" &&
        j.review_status === "approved" &&
        j.generated_document_id != null &&
        j.source_document_id != null,
    )
    .map(toApproved)
    .sort(
      (a, b) =>
        a.roomType.localeCompare(b.roomType) || a.packageLevel.localeCompare(b.packageLevel),
    );
}

function reasonSummary(
  reason: ReportAiMergeReason,
  counts: { incorporated: number; stubApproved: number; pending: number },
): string {
  switch (reason) {
    case "incorporated":
      return `${counts.incorporated} human-approved room visualization(s) will be merged into the report.`;
    case "no_jobs":
      return "No AI visualization jobs were run. The report will be created without AI room concepts.";
    case "pending_review":
      return `${counts.pending} visualization(s) still need review. Unapproved AI will not be merged into the report.`;
    case "stub_only":
      return `${counts.stubApproved} approved concept stub(s) only — stub/provider preview images are not merged into the family report.`;
    case "rejected_or_failed":
      return "AI visualization jobs failed or were rejected. The report will be created without AI room concepts.";
    case "unavailable":
      return "AI visualization service was unavailable. The report will be created without AI room concepts.";
    default:
      return "AI room visualizations are not incorporated into this report.";
  }
}

/** Summarize how AI jobs merge into the published report. */
export function buildReportAiVisualMerge(
  jobs: AIVisualizationJob[],
  opts?: { unavailable?: boolean },
): ReportAiVisualMerge {
  if (opts?.unavailable) {
    return {
      incorporated: [],
      approvedIncludingStubs: [],
      incorporatedCount: 0,
      totalJobs: 0,
      pendingReviewCount: 0,
      stubApprovedCount: 0,
      failedOrRejectedCount: 0,
      reason: "unavailable",
      summary: reasonSummary("unavailable", { incorporated: 0, stubApproved: 0, pending: 0 }),
      aiIncorporated: false,
    };
  }

  const active = jobs.filter((j) => j.status !== "cancelled");
  const approvedIncludingStubs = projectApprovedVisualizations(active);
  const incorporated = approvedIncludingStubs.filter((v) => !v.isStub);
  const stubApprovedCount = approvedIncludingStubs.filter((v) => v.isStub).length;
  const pendingReviewCount = active.filter(
    (j) =>
      j.review_status === "pending" &&
      (j.status === "needs_review" || j.status === "awaiting_provider" || j.status === "completed"),
  ).length;
  const failedOrRejectedCount = active.filter(
    (j) => j.review_status === "rejected" || j.status === "failed" || j.status === "error",
  ).length;

  let reason: ReportAiMergeReason;
  if (incorporated.length) reason = "incorporated";
  else if (!active.length) reason = "no_jobs";
  else if (stubApprovedCount > 0 && !incorporated.length) reason = "stub_only";
  else if (pendingReviewCount > 0) reason = "pending_review";
  else if (failedOrRejectedCount > 0) reason = "rejected_or_failed";
  else reason = "no_jobs";

  return {
    incorporated,
    approvedIncludingStubs,
    incorporatedCount: incorporated.length,
    totalJobs: active.length,
    pendingReviewCount,
    stubApprovedCount,
    failedOrRejectedCount,
    reason,
    summary: reasonSummary(reason, {
      incorporated: incorporated.length,
      stubApproved: stubApprovedCount,
      pending: pendingReviewCount,
    }),
    aiIncorporated: incorporated.length > 0,
  };
}

/** Fetch AI jobs and build report merge status (never throws). */
export async function loadReportAiVisualMerge(
  assessmentId: string,
): Promise<ReportAiVisualMerge> {
  try {
    const jobs = await listVisualizationJobs(assessmentId);
    return buildReportAiVisualMerge(jobs);
  } catch {
    return buildReportAiVisualMerge([], { unavailable: true });
  }
}

/** Returns publishable (non-stub) visuals only. */
export async function loadApprovedVisualizationsForAssessment(
  assessmentId: string,
): Promise<ApprovedRoomVisualization[]> {
  const merge = await loadReportAiVisualMerge(assessmentId);
  return merge.incorporated;
}

export function formatApprovedVisualizationsSection(
  visuals: ApprovedRoomVisualization[],
): string {
  if (!visuals.length) return "";
  const lines: string[] = [
    "",
    "APPROVED ROOM VISUALIZATIONS",
    "   Human-reviewed concepts only. Unapproved or pending jobs are excluded.",
    "",
  ];
  for (const v of visuals) {
    const tier = v.packageLevel.charAt(0).toUpperCase() + v.packageLevel.slice(1);
    lines.push(`   ${v.roomType.toUpperCase()} · ${tier} · job ${v.aiJobId}`);
    lines.push(`      Source photo document: #${v.sourceDocumentId}`);
    lines.push(`      Proposed concept document: #${v.proposedDocumentId}`);
    if (v.productLabels.length) {
      lines.push(`      Products in after photo: ${v.productLabels.join("; ")}`);
    } else if (v.productCodes.length) {
      lines.push(`      Product codes in after photo: ${v.productCodes.join("; ")}`);
    }
    if (v.recommendationLabels.length) {
      lines.push(`      Illustrated recommendations: ${v.recommendationLabels.join("; ")}`);
    }
    if (v.reviewedAt) {
      lines.push(`      Reviewed: ${new Date(v.reviewedAt).toLocaleString()}`);
    }
    if (v.reviewNotes?.trim()) {
      lines.push(`      Review notes: ${v.reviewNotes.trim()}`);
    }
    if (v.provider) {
      lines.push(`      Provider: ${v.provider}${v.isStub ? " (concept stub)" : ""}`);
    }
    lines.push(`      Source URL: ${v.sourceImageUrl}`);
    lines.push(`      Proposed URL: ${v.proposedImageUrl}`);
    lines.push("");
  }
  lines.push(`   Disclosure: ${REPORT_VISUALIZATION_DISCLOSURE}`);
  return lines.join("\n");
}

/** Always emit an AI section: either incorporated visuals or an explicit exclusion. */
export function formatAiVisualizationMergeSection(merge: ReportAiVisualMerge): string {
  const lines: string[] = ["", "AI ROOM VISUALIZATIONS (REPORT MERGE)", ""];

  if (merge.aiIncorporated && merge.incorporated.length) {
    lines.push(`   Status: INCORPORATED (${merge.incorporatedCount} concept(s))`);
    lines.push(`   ${merge.summary}`);
    lines.push(formatApprovedVisualizationsSection(merge.incorporated));
    return lines.join("\n");
  }

  lines.push("   Status: NOT INCORPORATED");
  lines.push(`   ${REPORT_AI_NOT_INCORPORATED}`);
  lines.push(`   Reason: ${merge.summary}`);
  if (merge.stubApprovedCount > 0) {
    lines.push(
      `   Note: ${merge.stubApprovedCount} local/stub concept board(s) were reviewed for assessor preview only and are excluded from the family report.`,
    );
  }
  if (merge.pendingReviewCount > 0) {
    lines.push(
      `   Note: ${merge.pendingReviewCount} job(s) still pending human review were excluded.`,
    );
  }
  lines.push(`   Disclosure: ${REPORT_VISUALIZATION_DISCLOSURE}`);
  return lines.join("\n");
}
