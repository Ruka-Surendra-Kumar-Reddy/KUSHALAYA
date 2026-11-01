"use client";

import { useEffect, useState } from "react";
import { VisualizationProductsList } from "@/components/livewell/VisualizationProductsList";
import { fetchStaffPhotoBlob, TIER_LABELS } from "@/lib/livewell/aiVisualizations";
import type {
  ApprovedRoomVisualization,
  ReportAiVisualMerge,
} from "@/lib/livewell/report-visualizations";

export function ReportAssemblyPanel({
  merge,
  assessmentReady,
}: {
  merge: ReportAiVisualMerge;
  assessmentReady: boolean;
}) {
  const aiStatusLabel = merge.aiIncorporated
    ? "Ready to merge"
    : merge.reason === "pending_review"
      ? "Waiting on review"
      : merge.reason === "stub_only"
        ? "Stub only — not merged"
        : merge.reason === "unavailable"
          ? "Unavailable"
          : merge.reason === "rejected_or_failed"
            ? "Not available"
            : "Not included";

  const aiStatusTone = merge.aiIncorporated
    ? "ok"
    : merge.reason === "pending_review"
      ? "warn"
      : "muted";

  return (
    <section className="card home-safety-section home-safety-report-assembly">
      <h2>Build family report</h2>
      <p className="muted home-safety-section-hint">
        Assessment findings always publish. AI room concepts merge only after human approval —
        stubs and unfinished jobs never block the report.
      </p>

      <ol className="home-safety-report-merge-steps">
        <li className={`home-safety-report-merge-step is-${assessmentReady ? "ok" : "warn"}`}>
          <span className="home-safety-report-merge-step-index" aria-hidden>
            1
          </span>
          <div>
            <strong>Assessment &amp; recommendations</strong>
            <p className="muted">
              {assessmentReady
                ? "Scores, findings, and rule-based solutions are ready."
                : "Finish rating applicable sections before saving the report."}
            </p>
          </div>
          <span
            className="home-safety-report-merge-badge"
            aria-label={
              assessmentReady
                ? "Assessment status: included"
                : "Assessment status: incomplete"
            }
          >
            {assessmentReady ? "Included" : "Incomplete"}
          </span>
        </li>

        <li className={`home-safety-report-merge-step is-${aiStatusTone}`}>
          <span className="home-safety-report-merge-step-index" aria-hidden>
            2
          </span>
          <div>
            <strong>AI room visualizations</strong>
            <p className="muted">{merge.summary}</p>
            {merge.approvedIncludingStubs.length > 0 ? (
              <ul className="home-safety-approved-viz-list">
                {merge.approvedIncludingStubs.map((v) => (
                  <li key={v.aiJobId}>
                    <ApprovedVizPreview viz={v} />
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
          <span
            className="home-safety-report-merge-badge"
            aria-label={`AI visualizations status: ${aiStatusLabel}`}
          >
            {aiStatusLabel}
          </span>
        </li>

        <li className="home-safety-report-merge-step is-ok">
          <span className="home-safety-report-merge-step-index" aria-hidden>
            3
          </span>
          <div>
            <strong>Published report</strong>
            <p className="muted">
              {merge.aiIncorporated
                ? `Report merges assessment data with ${merge.incorporatedCount} approved visualization(s).`
                : "Report is created from assessment data only. AI visuals are explicitly marked as not incorporated."}
            </p>
          </div>
          <span
            className="home-safety-report-merge-badge"
            aria-label={
              merge.aiIncorporated
                ? "Published report status: AI merged"
                : "Published report status: AI excluded"
            }
          >
            {merge.aiIncorporated ? "AI merged" : "AI excluded"}
          </span>
        </li>
      </ol>
    </section>
  );
}

function ApprovedVizPreview({ viz }: { viz: ApprovedRoomVisualization }) {
  const tier = TIER_LABELS[viz.packageLevel] || viz.packageLevel;
  return (
    <div className="home-safety-approved-viz-item">
      <strong>
        {viz.roomType} · {tier}
      </strong>
      <p className="muted" style={{ margin: "0.2rem 0 0.5rem" }}>
        {viz.isStub
          ? "Concept stub (assessor preview only, not in family report)"
          : "Will merge into report"}
      </p>
      <div className="ai-phase-pair" role="group" aria-label={`${viz.roomType} before and after`}>
        <figure>
          <figcaption>Before</figcaption>
          <StaffThumb documentId={viz.sourceDocumentId} alt={`Before ${viz.roomType}`} />
        </figure>
        <figure>
          <figcaption>After (approved)</figcaption>
          <StaffThumb documentId={viz.proposedDocumentId} alt={`After ${viz.roomType}, ${tier}`} />
        </figure>
      </div>
      <VisualizationProductsList
        labels={viz.productLabels}
        codes={viz.productCodes}
        headingId={`report-viz-${viz.aiJobId}-products`}
        emptyLabel={
          viz.recommendationLabels.length
            ? `Recommendations: ${viz.recommendationLabels.join("; ")}`
            : "No catalog products recorded for this concept."
        }
      />
    </div>
  );
}

function StaffThumb({ documentId, alt }: { documentId: number; alt: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let url: string | null = null;
    let cancelled = false;
    setSrc(null);
    setFailed(false);
    fetchStaffPhotoBlob(documentId)
      .then((blobUrl) => {
        if (!cancelled) {
          url = blobUrl;
          setSrc(blobUrl);
        }
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [documentId]);

  if (failed) {
    return (
      <div className="ai-phase-thumb-placeholder" role="img" aria-label={`${alt} — unavailable`}>
        Image unavailable
      </div>
    );
  }
  if (!src) {
    return (
      <div className="ai-phase-thumb-placeholder" role="status" aria-busy="true">
        Loading…
      </div>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img className="ai-phase-thumb" src={src} alt={alt} decoding="async" />;
}
