"use client";

import { useMemo, useState } from "react";
import {
  TIER_LABELS,
  fetchStaffPhotoBlob,
  type AIVisualizationJob,
  type RoomAnalyzeResult,
} from "@/lib/livewell/aiVisualizations";
import { useEffect } from "react";
import { VisualizationProductsList } from "@/components/livewell/VisualizationProductsList";
import { publicSafetyScoreName } from "@/lib/public-brand";

export type PhaseId =
  | "assessment"
  | "recommendations"
  | "analysis"
  | "plan"
  | "render"
  | "review"
  | "complete"
  | "failed"
  | "rejected";

const PHASE_ORDER: PhaseId[] = [
  "assessment",
  "recommendations",
  "analysis",
  "plan",
  "render",
  "review",
];

const PHASE_META: Record<
  string,
  { title: string; contract: string; blurb: string }
> = {
  assessment: {
    title: "1. Assessment",
    contract: "Contract A",
    blurb: `Room photo, ${publicSafetyScoreName()}, and findings that drive visualization.`,
  },
  recommendations: {
    title: "2. Recommendations",
    contract: "Contract B",
    blurb: "Rule-engine solutions and products eligible for the concept image.",
  },
  analysis: {
    title: "3. Room analysis",
    contract: "Contract C",
    blurb: "Gemini vision hazards mapped to finding codes. Optional — skip if unavailable.",
  },
  plan: {
    title: "4. Visualization plan",
    contract: "Contract D",
    blurb: "Assessor-approved render items that may be sent to the image worker.",
  },
  render: {
    title: "5. Render",
    contract: "Contract E",
    blurb: "Hosted FLUX Kontext edit when configured; local stub otherwise.",
  },
  review: {
    title: "6. Human review",
    contract: "Review",
    blurb: "Approve, reject, or regenerate before the concept can appear in a family report.",
  },
};

function expandPhaseForJob(phase: string | null | undefined, status?: string): PhaseId {
  if (status === "needs_review" || phase === "review") return "review";
  if (phase === "complete" || phase === "rejected") return "review";
  if (phase === "failed") return "render";
  if (phase && phase in PHASE_META && PHASE_ORDER.includes(phase as PhaseId)) {
    return phase as PhaseId;
  }
  return "review";
}

function phaseState(
  phaseId: PhaseId,
  current: string,
): "done" | "active" | "pending" | "blocked" {
  if (current === "failed" && phaseId === "render") return "blocked";
  if (current === "rejected" && phaseId === "review") return "blocked";
  // Approved jobs: keep Review highlighted so the after photo stays easy to find.
  if (current === "complete") {
    if (phaseId === "review") return "active";
    return "done";
  }
  const curIdx = PHASE_ORDER.indexOf(current as PhaseId);
  const idx = PHASE_ORDER.indexOf(phaseId);
  if (curIdx < 0) {
    if (current === "failed" || current === "rejected") {
      return idx < PHASE_ORDER.indexOf("review") ? "done" : "blocked";
    }
    return "pending";
  }
  if (idx < curIdx) return "done";
  if (idx === curIdx) return "active";
  return "pending";
}

/** Prep board progress before any Contract E job exists. */
function prepCurrentPhase(opts: {
  assessmentConfirmed: boolean;
  analysisReady: boolean;
  hasSolutions: boolean;
}): PhaseId {
  if (!opts.assessmentConfirmed) return "assessment";
  if (!opts.analysisReady) return "analysis";
  if (!opts.hasSolutions) return "recommendations";
  return "plan";
}

function prepPhaseState(
  phaseId: PhaseId,
  opts: {
    assessmentConfirmed: boolean;
    analysisReady: boolean;
    hasSolutions: boolean;
  },
): "done" | "active" | "pending" | "blocked" {
  const current = prepCurrentPhase(opts);
  if (phaseId === "assessment") {
    return opts.assessmentConfirmed ? "done" : "active";
  }
  if (phaseId === "recommendations") {
    if (opts.hasSolutions) return "done";
    if (opts.assessmentConfirmed && opts.analysisReady) return "active";
    if (opts.assessmentConfirmed) return "pending";
    return "pending";
  }
  if (phaseId === "analysis") {
    if (opts.analysisReady) return "done";
    if (opts.assessmentConfirmed) return "active";
    return "pending";
  }
  if (phaseId === "plan") {
    if (opts.assessmentConfirmed && opts.analysisReady && opts.hasSolutions) {
      return "active";
    }
    return "pending";
  }
  // Render / review stay pending until jobs exist.
  if (phaseId === current) return "active";
  return "pending";
}

export function VisualizationPhaseBoard({
  job,
  selectedSolutionIds,
  availableSolutions,
  selectedProductIds,
  availableProducts,
  onToggleSolution,
  onToggleProduct,
  onConfirmAssessment,
  onSkipAnalysis,
  onRunAnalysis,
  analysisResult,
  assessmentConfirmed = false,
  analysisReady = false,
  onGenerate,
  onUploadConcept,
  onReview,
  busy = false,
  mode = "job",
  showConceptGallery = true,
}: {
  job?: AIVisualizationJob | null;
  selectedSolutionIds?: string[];
  availableSolutions?: { id: string; label: string }[];
  selectedProductIds?: string[];
  availableProducts?: { id: string; code: string; label: string; solutionIds: string[] }[];
  onToggleSolution?: (id: string) => void;
  onToggleProduct?: (id: string) => void;
  onConfirmAssessment?: () => void;
  onSkipAnalysis?: () => void;
  onRunAnalysis?: () => void;
  analysisResult?: RoomAnalyzeResult | null;
  assessmentConfirmed?: boolean;
  analysisReady?: boolean;
  onGenerate?: () => void;
  onUploadConcept?: (file: File) => void;
  onReview?: (action: "approve" | "reject" | "regenerate", notes?: string) => void;
  busy?: boolean;
  mode?: "prep" | "job";
  /** When false, caller renders VisualizationConceptGallery above this board. */
  showConceptGallery?: boolean;
}) {
  const [notes, setNotes] = useState("");
  const [expanded, setExpanded] = useState<PhaseId | null>("review");
  const hasSolutions = (selectedSolutionIds?.length ?? 0) > 0;
  const prepOpts = {
    assessmentConfirmed,
    analysisReady,
    hasSolutions,
  };
  const current =
    mode === "prep"
      ? prepCurrentPhase(prepOpts)
      : job?.current_phase || "assessment";
  const snap = job?.phase_snapshot;

  const phases = useMemo(() => PHASE_ORDER, []);

  useEffect(() => {
    if (mode === "prep") setExpanded(current as PhaseId);
    else setExpanded(expandPhaseForJob(job?.current_phase, job?.status));
  }, [job?.ai_job_id, job?.current_phase, job?.status, mode, current]);

  const expandedMeta = expanded ? PHASE_META[expanded] : null;

  return (
    <div className="ai-phase-board">
      {job && showConceptGallery ? <VisualizationConceptGallery job={job} /> : null}

      <div className="ai-phase-rail" role="list" aria-label="Visualization phases">
        {phases.map((id) => {
          const state =
            mode === "prep" ? prepPhaseState(id, prepOpts) : phaseState(id, current);
          const meta = PHASE_META[id];
          return (
            <button
              key={id}
              type="button"
              role="listitem"
              className={`ai-phase-chip is-${state}${expanded === id ? " is-open" : ""}`}
              onClick={() => setExpanded(id)}
            >
              <span className="ai-phase-chip-mark" aria-hidden>
                {state === "done" ? "✓" : state === "active" ? "●" : state === "blocked" ? "!" : "○"}
              </span>
              <span>
                <strong>{meta.title}</strong>
                <em>{meta.contract}</em>
              </span>
            </button>
          );
        })}
      </div>

      {expanded && expandedMeta ? (
        <div className="ai-phase-panel">
          <header className="ai-phase-panel-head">
            <div>
              <p className="ai-phase-kicker">{expandedMeta.contract}</p>
              <h3>{expandedMeta.title}</h3>
              <p className="muted">{expandedMeta.blurb}</p>
            </div>
            {job ? (
              <p className="ai-phase-job-meta">
                {TIER_LABELS[job.package_level] || job.package_level} · {job.status}
                {job.review_status !== "pending" ? ` · ${job.review_status}` : ""}
              </p>
            ) : null}
          </header>

          {expanded === "assessment" ? (
            <AssessmentPhaseBody
              job={job}
              snap={snap}
              onConfirm={onConfirmAssessment}
              busy={busy}
              mode={mode}
            />
          ) : null}

          {expanded === "recommendations" ? (
            <RecommendationsPhaseBody
              job={job}
              snap={snap}
              availableSolutions={availableSolutions}
              selectedSolutionIds={selectedSolutionIds}
              availableProducts={availableProducts}
              selectedProductIds={selectedProductIds}
              onToggleSolution={onToggleSolution}
              onToggleProduct={onToggleProduct}
              onGenerate={onGenerate}
              busy={busy}
              mode={mode}
            />
          ) : null}

          {expanded === "analysis" ? (
            <div className="ai-phase-body">
              {(() => {
                const snapAnalysis = snap?.analysis as
                  | {
                      status?: string;
                      note?: string;
                    }
                  | undefined;
                const liveOk = analysisResult?.status === "SUCCEEDED";
                const status = liveOk
                  ? "succeeded"
                  : analysisResult?.status === "FAILED"
                    ? "failed"
                    : snapAnalysis?.status || "pending";
                const note = liveOk
                  ? "Vision analysis available for this photo (re-run anytime)."
                  : analysisResult?.error_message ||
                    snapAnalysis?.note ||
                    "Run Gemini room analysis, or continue without it.";
                const suggestions =
                  analysisResult?.mapped_suggestions ||
                  (snapAnalysis as { mapped_suggestions?: RoomAnalyzeResult["mapped_suggestions"] } | undefined)
                    ?.mapped_suggestions ||
                  [];
                const canRerun =
                  status === "succeeded" ||
                  status === "failed" ||
                  status === "skipped" ||
                  !!analysisResult;
                return (
                  <>
                    <p>{note}</p>
                    <p className="muted">
                      Status: <strong>{status}</strong>
                      {analysisResult?.cache_hit ? " · cache" : ""}
                    </p>
                    {suggestions.length ? (
                      <ul className="ai-phase-checklist">
                        {suggestions.map((s) => (
                          <li key={`${s.finding_code}-${s.solution_id}`}>
                            {s.finding_code} → {s.solution_id} ({s.confidence_percent}%)
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    <div className="ai-phase-actions">
                      {onRunAnalysis ? (
                        <button
                          type="button"
                          className="primary"
                          disabled={busy}
                          onClick={onRunAnalysis}
                        >
                          {busy
                            ? "Analyzing…"
                            : canRerun
                              ? "Re-run analysis"
                              : "Run analysis"}
                        </button>
                      ) : (
                        <p className="muted">
                          Use “Run room analysis” above the job tabs to analyze this photo.
                        </p>
                      )}
                      {onSkipAnalysis ? (
                        <button
                          type="button"
                          className="secondary"
                          disabled={busy}
                          onClick={onSkipAnalysis}
                        >
                          Continue without analysis
                        </button>
                      ) : null}
                    </div>
                  </>
                );
              })()}
            </div>
          ) : null}

          {expanded === "plan" ? (
            <PlanPhaseBody
              job={job}
              snap={snap}
              mode={mode}
              availableSolutions={availableSolutions}
              selectedSolutionIds={selectedSolutionIds}
              availableProducts={availableProducts}
              selectedProductIds={selectedProductIds}
              onGenerate={onGenerate}
              busy={busy}
            />
          ) : null}

          {expanded === "render" ? (
            <RenderPhaseBody
              job={job}
              snap={snap}
              onUploadConcept={onUploadConcept}
              onReview={onReview}
              notes={notes}
              busy={busy}
            />
          ) : null}

          {expanded === "review" ? (
            <ReviewPhaseBody
              job={job}
              notes={notes}
              setNotes={setNotes}
              onReview={onReview}
              onUploadConcept={onUploadConcept}
              busy={busy}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function AssessmentPhaseBody({
  job,
  snap,
  onConfirm,
  busy,
  mode,
}: {
  job?: AIVisualizationJob | null;
  snap?: AIVisualizationJob["phase_snapshot"];
  onConfirm?: () => void;
  busy: boolean;
  mode: "prep" | "job";
}) {
  const a = snap?.assessment as
    | {
        assessment_id?: string;
        independence_score?: number;
        room_type?: string;
        photo_ids?: string[];
        findings?: { finding_code: string; severity: string }[];
      }
    | undefined;
  return (
    <div className="ai-phase-body">
      <ul className="ai-phase-facts">
        <li>
          Assessment: <strong>{a?.assessment_id || job?.assessment_id || "—"}</strong>
        </li>
        <li>
          Room: <strong>{a?.room_type || job?.room_type || "—"}</strong>
        </li>
        <li>
          Score: <strong>{a?.independence_score ?? "—"}</strong>
        </li>
        <li>
          Photos: <strong>{(a?.photo_ids || []).join(", ") || job?.source_document_id || "—"}</strong>
        </li>
      </ul>
      {a?.findings?.length ? (
        <ul className="ai-phase-list">
          {a.findings.map((f) => (
            <li key={f.finding_code}>
              {f.finding_code} <span className="muted">({f.severity})</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">Findings appear after a visualization job is created.</p>
      )}
      {mode === "prep" && onConfirm ? (
        <button type="button" className="primary" disabled={busy} onClick={onConfirm}>
          Confirm assessment inputs
        </button>
      ) : null}
    </div>
  );
}

function RecommendationsPhaseBody({
  job,
  snap,
  availableSolutions,
  selectedSolutionIds,
  availableProducts,
  selectedProductIds,
  onToggleSolution,
  onToggleProduct,
  onGenerate,
  busy,
  mode,
}: {
  job?: AIVisualizationJob | null;
  snap?: AIVisualizationJob["phase_snapshot"];
  availableSolutions?: { id: string; label: string }[];
  selectedSolutionIds?: string[];
  availableProducts?: { id: string; code: string; label: string; solutionIds: string[] }[];
  selectedProductIds?: string[];
  onToggleSolution?: (id: string) => void;
  onToggleProduct?: (id: string) => void;
  onGenerate?: () => void;
  busy: boolean;
  mode: "prep" | "job";
}) {
  const items =
    (
      snap?.recommendations as
        | { items?: { recommendation_id: string; label?: string; solution_code: string; priority: string }[] }
        | undefined
    )?.items || [];

  const selectedProductCount = selectedProductIds?.length ?? 0;
  const canGenerate =
    !!(selectedSolutionIds && selectedSolutionIds.length) &&
    (!(availableProducts && availableProducts.length) || selectedProductCount > 0);

  return (
    <div className="ai-phase-body">
      {mode === "prep" && availableSolutions?.length ? (
        <>
          <p>1. Select assessment solutions for the concept:</p>
          <ul className="ai-phase-checklist">
            {availableSolutions.map((s) => {
              const checked = selectedSolutionIds?.includes(s.id) ?? false;
              return (
                <li key={s.id}>
                  <label className="ai-phase-check">
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={busy || !onToggleSolution}
                      onChange={() => onToggleSolution?.(s.id)}
                    />
                    <span className="ai-phase-check-text">
                      {s.label}
                      <span className="ai-phase-check-id">{s.id}</span>
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>

          <p style={{ marginTop: "1rem" }}>
            2. Select catalog products to show in the after photo:
          </p>
          {availableProducts?.length ? (
            <ul className="ai-phase-checklist">
              {availableProducts.map((p) => {
                const checked = selectedProductIds?.includes(p.id) ?? false;
                return (
                  <li key={p.id}>
                    <label className="ai-phase-check">
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={busy || !onToggleProduct}
                        onChange={() => onToggleProduct?.(p.id)}
                      />
                      <span className="ai-phase-check-text">
                        {p.label}
                        <span className="ai-phase-check-id">{p.code}</span>
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="muted">
              No catalog products are linked to the selected solutions. Link products in Master Data /
              catalog, or generate using solution labels only.
            </p>
          )}

          <p className="muted">
            {selectedSolutionIds?.length
              ? `${selectedSolutionIds.length} solution${selectedSolutionIds.length === 1 ? "" : "s"}`
              : "No solutions"}
            {availableProducts?.length
              ? ` · ${selectedProductCount} product${selectedProductCount === 1 ? "" : "s"} for the after photo`
              : ""}
            .
          </p>
          {onGenerate ? (
            <button
              type="button"
              className="primary"
              disabled={busy || !canGenerate}
              onClick={onGenerate}
            >
              {busy ? "Generating…" : "Build plan & generate concept"}
            </button>
          ) : null}
        </>
      ) : items.length ? (
        <ul className="ai-phase-list">
          {items.map((item) => (
            <li key={item.recommendation_id}>
              <strong>{item.label || item.solution_code}</strong>
              <span className="muted"> · {item.priority}</span>
            </li>
          ))}
        </ul>
      ) : (
        <ul className="ai-phase-list">
          {(job?.approved_solution_ids || []).map((id) => (
            <li key={id}>{id}</li>
          ))}
        </ul>
      )}
      {!availableSolutions?.length && !items.length && !(job?.approved_solution_ids || []).length ? (
        <p className="muted">
          No recommendations yet. Complete assessment ratings so the improvement plan has solutions,
          then return here to pick products for the after photo.
        </p>
      ) : null}
    </div>
  );
}

function PlanPhaseBody({
  job,
  snap,
  mode = "job",
  availableSolutions,
  selectedSolutionIds,
  availableProducts,
  selectedProductIds,
  onGenerate,
  busy = false,
}: {
  job?: AIVisualizationJob | null;
  snap?: AIVisualizationJob["phase_snapshot"];
  mode?: "prep" | "job";
  availableSolutions?: { id: string; label: string }[];
  selectedSolutionIds?: string[];
  availableProducts?: { id: string; code: string; label: string; solutionIds: string[] }[];
  selectedProductIds?: string[];
  onGenerate?: () => void;
  busy?: boolean;
}) {
  const plan = snap?.plan as
    | {
        visualization_plan_id?: string;
        render_items?: {
          render_item_id: string;
          label?: string;
          approval_status: string;
          operation: string;
        }[];
        preservation_constraints?: string[];
      }
    | undefined;

  const selected =
    availableSolutions?.filter((s) => selectedSolutionIds?.includes(s.id)) || [];
  const selectedProducts =
    availableProducts?.filter((p) => selectedProductIds?.includes(p.id)) || [];
  const showPrepDraft = mode === "prep" && !plan?.render_items?.length;

  return (
    <div className="ai-phase-body">
      {showPrepDraft ? (
        <>
          <p>
            Draft visualization plan from your selected solutions and products. Building creates
            Contract D and sends Contract E (after photo).
          </p>
          {selected.length ? (
            <ul className="ai-phase-list">
              {selected.map((s, i) => (
                <li key={s.id}>
                  <strong>{s.label}</strong>
                  <span className="muted">
                    {" "}
                    · RITEM-{String(i + 1).padStart(2, "0")} · INSERT_OBJECT · pending approve
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">
              Select recommendations in step 2 first — those become the plan render items.
            </p>
          )}
          {selectedProducts.length ? (
            <>
              <p className="muted" style={{ marginTop: "0.75rem" }}>
                Products for after photo:
              </p>
              <ul className="ai-phase-list">
                {selectedProducts.map((p) => (
                  <li key={p.id}>
                    <strong>{p.label}</strong>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {onGenerate ? (
            <div className="ai-phase-actions">
              <button
                type="button"
                className="primary"
                disabled={
                  busy ||
                  !selected.length ||
                  (!!availableProducts?.length && !selectedProducts.length)
                }
                onClick={onGenerate}
              >
                {busy ? "Generating…" : "Build plan & generate concept"}
              </button>
            </div>
          ) : null}
        </>
      ) : (
        <>
          <p>
            Plan ID:{" "}
            <strong>{plan?.visualization_plan_id || job?.visualization_plan_id || "—"}</strong>
          </p>
          <ul className="ai-phase-list">
            {(plan?.render_items || []).map((item) => (
              <li key={item.render_item_id}>
                <strong>{item.label || item.render_item_id}</strong>
                <span className="muted">
                  {" "}
                  · {item.operation} · {item.approval_status}
                </span>
              </li>
            ))}
          </ul>
          {plan?.preservation_constraints?.length ? (
            <p className="muted">Preserve: {plan.preservation_constraints.join(", ")}</p>
          ) : null}
          {!plan?.render_items?.length ? (
            <p className="muted">Render items appear after the plan is built.</p>
          ) : null}
        </>
      )}
    </div>
  );
}

function RenderPhaseBody({
  job,
  snap,
  onUploadConcept,
  onReview,
  notes,
  busy,
}: {
  job?: AIVisualizationJob | null;
  snap?: AIVisualizationJob["phase_snapshot"];
  onUploadConcept?: (file: File) => void;
  onReview?: (action: "approve" | "reject" | "regenerate", notes?: string) => void;
  notes?: string;
  busy?: boolean;
}) {
  const render = snap?.render as { job_id?: string; profile?: string; item_count?: number } | undefined;
  const renderFailed =
    !!job &&
    (job.status === "failed" ||
      job.status === "awaiting_provider" ||
      (job.current_phase === "failed" && !job.generated_document_id));
  const canRerunRender = !!job && !!onReview;
  return (
    <div className="ai-phase-body">
      <ul className="ai-phase-facts">
        <li>
          Render job: <strong>{render?.job_id || job?.render_job_id || "—"}</strong>
        </li>
        <li>
          Provider: <strong>{job?.provider || "—"}</strong>
        </li>
        <li>
          Profile: <strong>{render?.profile || "—"}</strong>
        </li>
        <li>
          Status: <strong>{job?.status || "—"}</strong>
        </li>
        <li>
          Callback:{" "}
          <strong>
            {(job?.render_callback as { status?: string } | undefined)?.status ||
              (job?.status === "needs_review" ? "SUCCEEDED" : "—")}
          </strong>
        </li>
      </ul>
      {job?.error_message ? (
        <p className={renderFailed ? "error-text" : "muted"}>{job.error_message}</p>
      ) : null}
      {job?.generated_document_id ? (
        <ConceptThumb documentId={job.generated_document_id} />
      ) : (
        <ConceptUploadPrompt onUploadConcept={onUploadConcept} busy={!!busy} />
      )}
      {canRerunRender ? (
        <div className="ai-phase-actions">
          <button
            type="button"
            className="primary"
            disabled={!!busy}
            onClick={() => onReview?.("regenerate", notes)}
          >
            {busy
              ? "Re-running render…"
              : renderFailed
                ? "Re-run render (Contract E)"
                : "Re-run render"}
          </button>
          {onUploadConcept && !job?.generated_document_id ? (
            <p className="muted" style={{ margin: 0, width: "100%" }}>
              Or upload an after photo below / in the upload accordion if AI is unavailable.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function ReviewPhaseBody({
  job,
  notes,
  setNotes,
  onReview,
  onUploadConcept,
  busy,
}: {
  job?: AIVisualizationJob | null;
  notes: string;
  setNotes: (v: string) => void;
  onReview?: (action: "approve" | "reject" | "regenerate", notes?: string) => void;
  onUploadConcept?: (file: File) => void;
  busy: boolean;
}) {
  const canReview =
    !!job &&
    !!job.generated_document_id &&
    (job.status === "needs_review" || job.status === "awaiting_provider") &&
    job.review_status === "pending";
  const renderFailed = !!job && (job.status === "failed" || job.current_phase === "failed");
  const isApproved = job?.review_status === "approved";
  return (
    <div className="ai-phase-body">
      {job?.generated_document_id ? (
        isApproved ? (
          <p className="home-safety-saved-badge" role="status">
            Approved for the family report — see the before/after pair at the top of this job.
          </p>
        ) : (
          <p className="muted">
            Concept image is shown in the gallery above. Approve it to include in the family report.
          </p>
        )
      ) : (
        <ConceptUploadPrompt onUploadConcept={onUploadConcept} busy={busy} />
      )}
      {renderFailed && job?.error_message ? (
        <p className="error-text">{job.error_message}</p>
      ) : null}
      <label className="ai-phase-notes">
        Review notes
        <textarea
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Optional notes for the audit trail"
          disabled={busy || !onReview || isApproved}
        />
      </label>
      <div className="ai-phase-actions">
        <button
          type="button"
          className="primary"
          disabled={busy || !canReview || !onReview}
          onClick={() => onReview?.("approve", notes)}
        >
          Approve for report
        </button>
        <button
          type="button"
          className="secondary danger"
          disabled={busy || !canReview || !onReview}
          onClick={() => onReview?.("reject", notes)}
        >
          Reject
        </button>
        <button
          type="button"
          className={renderFailed ? "primary" : "secondary"}
          disabled={busy || !job || !onReview}
          onClick={() => onReview?.("regenerate", notes)}
        >
          {busy
            ? "Re-running…"
            : renderFailed
              ? "Re-run render (Contract E)"
              : "Regenerate"}
        </button>
      </div>
      {job?.review_status && job.review_status !== "pending" ? (
        <p className="muted">
          Current decision: <strong>{job.review_status}</strong>
          {job.review_notes ? ` — ${job.review_notes}` : ""}
        </p>
      ) : null}
      {!job ? <p className="muted">Generate a concept first to enable review actions.</p> : null}
      {renderFailed ? (
        <p className="muted">
          Previous render failed. Re-run Contract E after fixing the provider (e.g. fal balance), or
          upload an after photo.
        </p>
      ) : null}
    </div>
  );
}

function ConceptUploadPrompt({
  onUploadConcept,
  busy,
}: {
  onUploadConcept?: (file: File) => void;
  busy: boolean;
}) {
  if (!onUploadConcept) {
    return <p className="muted">No after photo yet. Generate with AI or upload one from the panel above.</p>;
  }
  return (
    <label className="ai-phase-upload">
      <span>No after photo — upload one</span>
      <input
        type="file"
        accept="image/*"
        disabled={busy}
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) onUploadConcept(file);
        }}
      />
    </label>
  );
}

function ConceptPair({ job }: { job: AIVisualizationJob }) {
  const snapProducts = (() => {
    const snap = job.phase_snapshot as
      | { plan?: { render_items?: { label?: string; product_code?: string }[] } }
      | null
      | undefined;
    const items = snap?.plan?.render_items || [];
    const labels = items
      .filter((i) => i.product_code)
      .map((i) =>
        i.label && i.product_code
          ? `${i.label} (${i.product_code})`
          : i.product_code || i.label || "",
      )
      .filter(Boolean);
    const codes = items.map((i) => (i.product_code || "").trim()).filter(Boolean);
    return { labels, codes };
  })();
  const productLabels = job.product_labels?.length
    ? job.product_labels
    : snapProducts.labels;
  const productCodes = job.product_codes?.length ? job.product_codes : snapProducts.codes;
  const products =
    (productLabels?.length ? productLabels : null) ??
    (productCodes?.length ? productCodes : null) ??
    [];
  const productsNote = products.length ? ` Products: ${products.join(", ")}.` : "";
  const tier = TIER_LABELS[job.package_level] || job.package_level;

  return (
    <div className="ai-phase-pair-wrap">
      <div
        className="ai-phase-pair"
        role="group"
        aria-label={`${job.room_type} ${tier} before and after concept.${productsNote}`}
      >
        <figure>
          <figcaption>Before</figcaption>
          <ConceptThumb
            documentId={job.source_document_id}
            alt={`Source ${job.room_type} photo before improvements`}
          />
        </figure>
        {job.generated_document_id ? (
          <figure>
            <figcaption>{job.review_status === "approved" ? "After (approved)" : "After"}</figcaption>
            <ConceptThumb
              documentId={job.generated_document_id}
              alt={`After concept for ${job.room_type}, ${tier}.${productsNote}`}
            />
          </figure>
        ) : null}
      </div>
      <VisualizationProductsList
        labels={productLabels}
        codes={productCodes}
        headingId={`job-${job.ai_job_id}-products`}
        emptyLabel="No products recorded on this concept. Select products above, then rebuild or re-upload the after photo."
      />
    </div>
  );
}

/** Before/after pair for a concept job — keep visible outside collapsed job panels. */
export function VisualizationConceptGallery({ job }: { job: AIVisualizationJob }) {
  if (!job.generated_document_id) return null;
  const isApproved = job.review_status === "approved";
  return (
    <section
      className={`ai-phase-approved-gallery${isApproved ? " is-approved" : ""}`}
      aria-label={
        isApproved
          ? "Approved before and after concept"
          : "Before and after concept preview"
      }
    >
      <header className="ai-phase-approved-gallery-head">
        <h3>{isApproved ? "Approved after photo" : "Concept preview"}</h3>
        <p className="muted">
          {TIER_LABELS[job.package_level] || job.package_level}
          {" · "}
          {job.room_type}
          {isApproved ? " · ready for family report" : ` · ${job.review_status || job.status}`}
        </p>
      </header>
      <ConceptPair job={job} />
    </section>
  );
}

function ConceptThumb({
  documentId,
  alt = `Document ${documentId}`,
}: {
  documentId: number;
  alt?: string;
}) {
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
      <div
        className="ai-phase-thumb-placeholder"
        role="img"
        aria-label={`${alt} — could not load`}
      >
        Image unavailable
      </div>
    );
  }
  if (!src) {
    return (
      <div
        className="ai-phase-thumb-placeholder"
        role="status"
        aria-busy="true"
        aria-label={`Loading ${alt}`}
      >
        Loading…
      </div>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img className="ai-phase-thumb" src={src} alt={alt} decoding="async" />;
}
