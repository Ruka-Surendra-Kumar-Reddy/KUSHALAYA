"use client";

import { aiPreviewHref } from "@/lib/aiPreview";
import type { ReportAiVisualMerge } from "@/lib/livewell/report-visualizations";

export function AiVisualizationsLaunchCard({
  assessmentId,
  merge,
}: {
  assessmentId: string;
  merge: ReportAiVisualMerge;
}) {
  const href = `/kushalaya/assess/${assessmentId}/visualizations`;
  const status = merge.aiIncorporated
    ? `${merge.incorporatedCount} approved concept${merge.incorporatedCount === 1 ? "" : "s"} ready for the report`
    : merge.reason === "pending_review"
      ? "Concepts waiting on human review"
      : merge.reason === "no_jobs"
        ? "No visualization jobs yet"
        : merge.summary;
  const statusId = "ai-viz-launch-status";

  return (
    <section
      className="card home-safety-section home-safety-viz-launch"
      aria-labelledby="ai-viz-launch-heading"
    >
      <h2 id="ai-viz-launch-heading">AI room visualizations</h2>
      <p className="muted home-safety-section-hint" id="ai-viz-launch-hint">
        Room analysis, product selection, and after-photo generation live on a dedicated page so
        this review step stays focused on scores, quotes, and the family report.
      </p>
      <p className="home-safety-viz-launch-status" id={statusId} role="status">
        {status}
      </p>
      <div className="home-safety-viz-launch-actions">
        {/* Full page load — soft router.push can fail with stale client bundles / PWA cache. */}
        <a
          href={href}
          className="primary home-safety-viz-launch-primary"
          aria-describedby={`${statusId} ai-viz-launch-hint`}
        >
          Open AI visualizations
        </a>
        <a href={aiPreviewHref({ assessment: assessmentId })} className="secondary">
          See it in their home (AI preview)
        </a>
      </div>
    </section>
  );
}
