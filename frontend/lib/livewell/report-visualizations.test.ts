import { describe, expect, it } from "vitest";

import type { AIVisualizationJob } from "./aiVisualizations";
import {
  buildReportAiVisualMerge,
  formatAiVisualizationMergeSection,
  formatApprovedVisualizationsSection,
  projectApprovedVisualizations,
  REPORT_AI_NOT_INCORPORATED,
  REPORT_VISUALIZATION_DISCLOSURE,
} from "./report-visualizations";
import { formatAssessmentReport } from "./assessment-report";
import { createEmptyAssessment } from "./assessment";
import { DEFAULT_SAFETY_CATEGORIES } from "./rubric-defaults";
import { DEFAULT_SOLUTION_LIBRARY } from "./solution-defaults";

function job(overrides: Partial<AIVisualizationJob> = {}): AIVisualizationJob {
  return {
    ai_job_id: "aij_1",
    id: 1,
    assessment_id: "assess_1",
    prospect_id: null,
    elder_id: null,
    room_type: "bathroom",
    package_level: "essential",
    source_document_id: 10,
    status: "completed",
    provider: "local_stub",
    original_image_url: null,
    generated_image_url: null,
    generated_document_id: 20,
    prompt_text: null,
    negative_prompt_text: null,
    workflow_name: null,
    review_status: "approved",
    reviewed_at: "2026-07-16T12:00:00.000Z",
    review_notes: "Looks good",
    error_code: null,
    error_message: null,
    approved_solution_ids: ["LW-HS-BTH-001"],
    created_at: "2026-07-16T11:00:00.000Z",
    updated_at: "2026-07-16T12:00:00.000Z",
    phase_snapshot: {
      recommendations: {
        items: [{ label: "Toilet grab bar", solution_code: "LW-HS-BTH-001" }],
      },
    },
    ...overrides,
  };
}

describe("report visualizations", () => {
  it("includes only completed + approved jobs with generated images", () => {
    const approved = projectApprovedVisualizations([
      job(),
      job({
        ai_job_id: "aij_pending",
        status: "needs_review",
        review_status: "pending",
        generated_document_id: 21,
      }),
      job({
        ai_job_id: "aij_rejected",
        review_status: "rejected",
        generated_document_id: 22,
      }),
      job({
        ai_job_id: "aij_no_image",
        generated_document_id: null,
      }),
    ]);

    expect(approved).toHaveLength(1);
    expect(approved[0].aiJobId).toBe("aij_1");
    expect(approved[0].recommendationLabels).toEqual(["Toilet grab bar"]);
    expect(approved[0].productLabels).toEqual([]);
    expect(approved[0].isStub).toBe(true);
    expect(approved[0].disclosure).toBe(REPORT_VISUALIZATION_DISCLOSURE);
  });

  it("surfaces product labels selected for the after photo", () => {
    const approved = projectApprovedVisualizations([
      job({
        provider: "jarvislabs",
        product_codes: ["BTH-001"],
        product_labels: ["Shower chair / folding seat (BTH-001)"],
        render_callback: { is_stub: false },
      }),
    ]);
    expect(approved[0].productLabels).toEqual(["Shower chair / folding seat (BTH-001)"]);
    expect(approved[0].productCodes).toEqual(["BTH-001"]);
    const text = formatApprovedVisualizationsSection(approved);
    expect(text).toContain("Products in after photo: Shower chair / folding seat (BTH-001)");
  });

  it("does not incorporate stub-only approved jobs into the family report", () => {
    const merge = buildReportAiVisualMerge([job()]);
    expect(merge.aiIncorporated).toBe(false);
    expect(merge.reason).toBe("stub_only");
    expect(merge.incorporated).toHaveLength(0);
    expect(merge.stubApprovedCount).toBe(1);
    const section = formatAiVisualizationMergeSection(merge);
    expect(section).toContain("NOT INCORPORATED");
    expect(section).toContain(REPORT_AI_NOT_INCORPORATED);
  });

  it("incorporates non-stub approved jobs", () => {
    const merge = buildReportAiVisualMerge([
      job({ provider: "jarvislabs", render_callback: { is_stub: false } }),
    ]);
    expect(merge.aiIncorporated).toBe(true);
    expect(merge.incorporated).toHaveLength(1);
    expect(formatAiVisualizationMergeSection(merge)).toContain("INCORPORATED");
  });

  it("formats a report section with disclosure", () => {
    const section = formatApprovedVisualizationsSection(
      projectApprovedVisualizations([
        job({ provider: "jarvislabs", render_callback: { is_stub: false } }),
      ]),
    );
    expect(section).toContain("APPROVED ROOM VISUALIZATIONS");
    expect(section).toContain("BATHROOM");
    expect(section).toContain("Toilet grab bar");
    expect(section).toContain(REPORT_VISUALIZATION_DISCLOSURE);
  });

  it("always embeds an AI merge section — even when AI is absent", () => {
    const a = createEmptyAssessment();
    a.clientFirstName = "Lakshmi";
    const text = formatAssessmentReport(
      a,
      DEFAULT_SAFETY_CATEGORIES,
      DEFAULT_SOLUTION_LIBRARY,
      undefined,
      undefined,
      { aiVisualMerge: buildReportAiVisualMerge([]) },
    );
    expect(text).toContain("AI ROOM VISUALIZATIONS (REPORT MERGE)");
    expect(text).toContain("NOT INCORPORATED");
    expect(text).toContain(REPORT_AI_NOT_INCORPORATED);
    expect(text).toContain("not incorporated into this report");
  });

  it("embeds incorporated visuals when non-stub approvals exist", () => {
    const a = createEmptyAssessment();
    const merge = buildReportAiVisualMerge([
      job({ provider: "jarvislabs", render_callback: { is_stub: false } }),
    ]);
    const text = formatAssessmentReport(
      a,
      DEFAULT_SAFETY_CATEGORIES,
      DEFAULT_SOLUTION_LIBRARY,
      undefined,
      undefined,
      { aiVisualMerge: merge },
    );
    expect(text).toContain("INCORPORATED");
    expect(text).toContain("human-approved before inclusion");
  });
});
