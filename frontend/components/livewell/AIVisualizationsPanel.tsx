"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { HomeSafetyAssessment, AssessmentCategory } from "@/lib/livewell/assessment";
import { buildImprovementPlan } from "@/lib/livewell/improvement-plan";
import type { SolutionLibrary } from "@/lib/livewell/solution-types";
import { persistDraftWithSync } from "@/lib/livewell/assessmentSync";
import { ensureAssessmentCustomerLink } from "@/lib/livewell/syncProspect";
import {
  ACTIVE_TIERS,
  ROOM_TYPE_OPTIONS,
  TIER_LABELS,
  analyzeRoomPhotos,
  fetchStaffPhotoBlob,
  generateVisualizationsForPhoto,
  getRoomAnalysis,
  listVisualizationJobs,
  mergeVisualizationJobs,
  reviewVisualizationJob,
  uploadConceptPhoto,
  type AIVisualizationJob,
  type RoomAnalyzeResult,
} from "@/lib/livewell/aiVisualizations";
import {
  VisualizationConceptGallery,
  VisualizationPhaseBoard,
} from "@/components/livewell/VisualizationPhaseBoard";
import type { SafetyCatalog } from "@/lib/livewell/catalog-types";
import { productsForSolution } from "@/lib/livewell/catalog-product-seed";

export function AIVisualizationsPanel({
  assessment,
  categories,
  library,
  catalog,
  selectedPackageTiers,
  onPackageTiersChange,
  onAssessmentChange,
  onJobsChange,
}: {
  assessment: HomeSafetyAssessment;
  categories: AssessmentCategory[];
  library: SolutionLibrary;
  catalog?: SafetyCatalog;
  selectedPackageTiers: string[];
  onPackageTiersChange: (tiers: string[]) => void;
  onAssessmentChange?: (next: HomeSafetyAssessment) => void;
  onJobsChange?: (jobs: AIVisualizationJob[]) => void;
}) {
  const [jobs, setJobs] = useState<AIVisualizationJob[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [selectedPhotoId, setSelectedPhotoId] = useState<number | null>(null);
  const [assessmentConfirmed, setAssessmentConfirmed] = useState(false);
  const [analysisSkipped, setAnalysisSkipped] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<RoomAnalyzeResult | null>(null);
  const [selectedSolutionIds, setSelectedSolutionIds] = useState<string[]>([]);
  const [selectedProductIds, setSelectedProductIds] = useState<string[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [visionOpen, setVisionOpen] = useState(false);
  const [planOpen, setPlanOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [jobsOpen, setJobsOpen] = useState(false);

  const plan = buildImprovementPlan(assessment, categories, library);
  const availableSolutions = useMemo(
    () =>
      plan.entries.map((e) => ({
        id: e.solution.id,
        label: e.solution.recommendedSolutions?.[0] || e.solution.finding || e.solution.id,
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- rebuild when assessment ratings change
    [assessment.id, assessment.ratings, library],
  );

  const syncedPhotos = assessment.photos.filter((p) => p.documentId);
  const selectedRoomType =
    syncedPhotos.find((p) => p.documentId === selectedPhotoId)?.roomType || "";

  const availableProducts = useMemo(() => {
    const products = catalog?.products ?? [];
    if (!products.length) return [];

    const byId = new Map<
      string,
      {
        id: string;
        code: string;
        label: string;
        solutionIds: string[];
        source: "solution" | "room" | "quote";
      }
    >();

    const addProduct = (
      p: (typeof products)[number],
      solutionIds: string[],
      source: "solution" | "room" | "quote",
    ) => {
      const code = (p.product_code || p.id).trim();
      const existing = byId.get(p.id);
      if (existing) {
        for (const sid of solutionIds) {
          if (!existing.solutionIds.includes(sid)) existing.solutionIds.push(sid);
        }
        if (source === "solution") existing.source = "solution";
        else if (source === "quote" && existing.source === "room") existing.source = "quote";
        return;
      }
      const optionHint =
        Array.isArray(p.options) && p.options.length
          ? ` — ${p.options.slice(0, 3).join(", ")}`
          : "";
      byId.set(p.id, {
        id: p.id,
        code,
        label: `${p.name}${optionHint}${code ? ` (${code})` : ""}`,
        solutionIds: [...solutionIds],
        source,
      });
    };

    for (const sid of selectedSolutionIds) {
      for (const p of productsForSolution(products, sid)) {
        addProduct(p, [sid], "solution");
      }
    }

    // Quote draft products for this assessment (if any) — always include.
    for (const p of products) {
      const custom = assessment.quoteCustomization?.lines;
      if (!custom?.length) break;
      const inQuote = custom.some((line) => line.productId === p.id && line.included);
      if (inQuote) addProduct(p, [], "quote");
    }

    // Room-matched products — merge with solution products so the list is never sparse.
    if (selectedRoomType) {
      const room = selectedRoomType.toLowerCase();
      const prefixByRoom: Record<string, string[]> = {
        bathroom: ["BTH"],
        bedroom: ["BED"],
        kitchen: ["KIT"],
        hallway: ["HLW", "GEN"],
        entry: ["ENT", "GEN"],
        living: ["LIV", "GEN"],
        living_room: ["LIV", "GEN"],
        stairs: ["STA", "GEN"],
      };
      const prefixes = new Set(prefixByRoom[room] || []);
      for (const p of products) {
        const prefix = (p.category_prefix || p.product_code || "").toUpperCase().slice(0, 3);
        const cat = (p.category || "").toLowerCase();
        if (
          prefixes.has(prefix) ||
          cat.includes(room.replace("_", " ")) ||
          (room === "bathroom" && cat.includes("bath")) ||
          ((room === "living" || room === "living_room") && cat.includes("living"))
        ) {
          addProduct(p, [], "room");
        }
      }
    }

    // Last resort: if still empty, offer the full catalog (capped) so assessors can pick.
    if (byId.size === 0) {
      for (const p of products.slice(0, 40)) {
        addProduct(p, [], "room");
      }
    }

    return [...byId.values()].sort((a, b) => a.label.localeCompare(b.label));
  }, [
    catalog?.products,
    selectedSolutionIds,
    selectedRoomType,
    assessment.quoteCustomization?.lines,
  ]);

  useEffect(() => {
    setSelectedSolutionIds(availableSolutions.map((s) => s.id));
  }, [availableSolutions]);

  useEffect(() => {
    setSelectedProductIds(availableProducts.map((p) => p.id));
  }, [availableProducts]);

  // Keep Plan & generate open so product pickers are visible.
  useEffect(() => {
    if (availableSolutions.length || availableProducts.length) {
      setPlanOpen(true);
    }
  }, [availableSolutions.length, availableProducts.length]);

  useEffect(() => {
    if (!selectedPhotoId && syncedPhotos[0]?.documentId) {
      setSelectedPhotoId(syncedPhotos[0].documentId!);
    }
  }, [selectedPhotoId, syncedPhotos]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const rows = await listVisualizationJobs(assessment.id);
        if (!cancelled) setJobs(rows);
      } catch {
        if (!cancelled) setJobs([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [assessment.id]);

  useEffect(() => {
    onJobsChange?.(jobs);
  }, [jobs, onJobsChange]);

  useEffect(() => {
    let cancelled = false;
    setAnalysisResult(null);
    setAnalysisSkipped(false);
    if (!selectedPhotoId) return;
    (async () => {
      const cached = await getRoomAnalysis(selectedPhotoId);
      if (!cancelled && cached?.status === "SUCCEEDED") {
        setAnalysisResult(cached);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedPhotoId]);

  const selectedPhoto = syncedPhotos.find((p) => p.documentId === selectedPhotoId);
  const analysisReady =
    analysisSkipped || (analysisResult != null && analysisResult.status === "SUCCEEDED");
  const photoJobs = jobs
    .filter((j) => j.source_document_id === selectedPhotoId && j.status !== "cancelled")
    .sort((a, b) => a.package_level.localeCompare(b.package_level));
  const activeJob =
    photoJobs.find((j) => j.ai_job_id === selectedJobId) ||
    photoJobs.find((j) => j.status === "needs_review" && j.review_status === "pending") ||
    photoJobs[0] ||
    null;

  useEffect(() => {
    if (activeJob && selectedJobId !== activeJob.ai_job_id) {
      setSelectedJobId(activeJob.ai_job_id);
    }
    if (!photoJobs.length) setSelectedJobId(null);
  }, [activeJob, photoJobs.length, selectedJobId]);

  // Keep Jobs open when this photo has a concept so the after image is not buried.
  const hasConceptForPhoto = photoJobs.some((j) => !!j.generated_document_id);
  useEffect(() => {
    if (hasConceptForPhoto) setJobsOpen(true);
  }, [selectedPhotoId, hasConceptForPhoto]);

  async function withCustomerLink(): Promise<HomeSafetyAssessment> {
    const linked = await ensureAssessmentCustomerLink(assessment);
    if (
      linked.prospectId !== assessment.prospectId ||
      linked.elderId !== assessment.elderId
    ) {
      const saved = persistDraftWithSync(linked);
      onAssessmentChange?.(saved);
      return saved;
    }
    return linked;
  }

  async function runAnalysis(opts?: { force?: boolean }) {
    if (!selectedPhotoId) {
      setError("Select a room photo first.");
      return;
    }
    const roomType = selectedPhoto?.roomType || "";
    if (!roomType) {
      setError("Set a room type on the photo before analyzing.");
      return;
    }
    setBusyKey(`${selectedPhotoId}:analyze`);
    setError(null);
    setMessage(null);
    try {
      const result = await analyzeRoomPhotos({
        assessmentId: assessment.id,
        roomType,
        documentIds: [selectedPhotoId],
        force: opts?.force ?? false,
      });
      setAnalysisResult(result);
      setAnalysisSkipped(false);
      if (result.status === "SUCCEEDED") {
        setVisionOpen(true);
        setPlanOpen(true);
        setAssessmentConfirmed(true);
      }
      // Refresh frozen job snapshots so Contract C is not stuck on "skipped".
      setJobs((prev) =>
        prev.map((j) => {
          if (j.source_document_id !== selectedPhotoId) return j;
          const succeeded = result.status === "SUCCEEDED";
          return {
            ...j,
            phase_snapshot: {
              ...(j.phase_snapshot || {}),
              analysis: {
                status: succeeded ? "succeeded" : "failed",
                provider: result.provider,
                model_version: result.model_version,
                observation_count: result.response?.observations?.length ?? 0,
                mapped_suggestions: result.mapped_suggestions,
                limitations: result.response?.limitations ?? [],
                cache_hit: result.cache_hit,
                note: succeeded
                  ? "Contract C vision analysis available for this photo."
                  : result.error_message ||
                    "Room analysis failed. Re-run analysis or continue without it.",
              },
            },
          };
        }),
      );
      const n = result.mapped_suggestions?.length ?? 0;
      if (result.status !== "SUCCEEDED") {
        setError(
          result.error_message ||
            "Room analysis failed. Check GEMINI_API_KEY / model, then re-run.",
        );
      } else {
        setMessage(
          (result.cache_hit
            ? `Analysis loaded from cache (${n} suggestion${n === 1 ? "" : "s"}).`
            : `Analysis complete (${n} suggestion${n === 1 ? "" : "s"}).`) +
            " Next: select recommendations in Plan & generate, then build concepts.",
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Room analysis failed");
    } finally {
      setBusyKey(null);
    }
  }

  async function runGenerate() {
    if (!selectedPhotoId) {
      setError("Select a room photo first.");
      return;
    }
    const roomType = selectedPhoto?.roomType || "";
    if (!roomType) {
      setError("Set a room type on the photo before generating visualizations.");
      return;
    }
    if (!assessmentConfirmed) {
      setError("Confirm assessment inputs before generating.");
      return;
    }
    if (!analysisReady) {
      setError("Run room analysis or continue without analysis before generating.");
      return;
    }
    if (!selectedSolutionIds.length) {
      setError("Select at least one recommendation to visualize.");
      return;
    }
    const pickedProducts = availableProducts.filter((p) =>
      selectedProductIds.includes(p.id),
    );
    if (availableProducts.length && !pickedProducts.length) {
      setError("Select at least one catalog product for the after photo.");
      return;
    }
    if (!selectedPackageTiers.length) {
      setError("Select at least one package tier.");
      return;
    }

    const key = `${selectedPhotoId}:phases`;
    setBusyKey(key);
    setError(null);
    setMessage(null);
    try {
      const ctx = await withCustomerLink();
      const created = await generateVisualizationsForPhoto({
        assessmentId: ctx.id,
        sourceDocumentId: selectedPhotoId,
        roomType,
        approvedSolutionIds: selectedSolutionIds,
        approvedProductCodes: pickedProducts.map((p) => p.code),
        productLabels: pickedProducts.map((p) => p.label),
        tiers: selectedPackageTiers,
        onlyMissing: false,
        prospectId: ctx.prospectId,
        elderId: ctx.elderId,
      });
      setJobs((prev) => mergeVisualizationJobs(prev, created));
      if (created[0]) setSelectedJobId(created[0].ai_job_id);
      if (created.length) setJobsOpen(true);
      if (created.length === 0) {
        setMessage("No new jobs created.");
      } else if (created.every((j) => j.cache_hit)) {
        setMessage(
          `Using ${created.length} cached concept${created.length === 1 ? "" : "s"} (no new render).`,
        );
      } else {
        const fresh = created.filter((j) => !j.cache_hit).length;
        setMessage(
          `${fresh} concept job${fresh === 1 ? "" : "s"} ready for human review` +
            (fresh < created.length
              ? ` (${created.length - fresh} cached).`
              : "."),
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create visualization jobs");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleReview(
    aiJobId: string,
    action: "approve" | "reject" | "regenerate",
    notes?: string,
  ) {
    setBusyKey(`${aiJobId}:${action}`);
    setError(null);
    try {
      const updated = await reviewVisualizationJob(aiJobId, action, notes);
      setJobs((prev) => mergeVisualizationJobs(prev, [updated]));
      setSelectedJobId(updated.ai_job_id);
      setJobsOpen(true);
      setMessage(
        action === "regenerate"
          ? `${TIER_LABELS[updated.package_level] || updated.package_level} render re-run (${updated.status}).`
          : action === "approve"
            ? "Approved — after photo is shown above Jobs for this photo."
            : `Job ${action}d`,
      );
      if (action === "regenerate" && updated.status === "failed") {
        setError(updated.error_message || "Render re-run failed");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Review failed");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleUploadConcept(file: File, forJobId?: string | null) {
    if (!selectedPhotoId) {
      setError("Select a room photo first.");
      return;
    }
    const roomType = selectedPhoto?.roomType || "";
    if (!roomType) {
      setError("Set a room type on the photo before uploading an after photo.");
      return;
    }
    const tier =
      (forJobId
        ? jobs.find((j) => j.ai_job_id === forJobId)?.package_level
        : null) ||
      selectedPackageTiers[0] ||
      "essential";
    const pickedProducts = availableProducts.filter((p) =>
      selectedProductIds.includes(p.id),
    );

    setBusyKey(`${selectedPhotoId}:upload`);
    setError(null);
    setMessage(null);
    try {
      const ctx = await withCustomerLink();
      const updated = await uploadConceptPhoto({
        file,
        assessmentId: ctx.id,
        sourceDocumentId: selectedPhotoId,
        roomType,
        packageLevel: tier,
        approvedSolutionIds: selectedSolutionIds,
        approvedProductCodes: pickedProducts.map((p) => p.code),
        productLabels: pickedProducts.map((p) => p.label),
        prospectId: ctx.prospectId,
        elderId: ctx.elderId,
        aiJobId: forJobId || null,
      });
      setJobs((prev) => mergeVisualizationJobs(prev, [updated]));
      setSelectedJobId(updated.ai_job_id);
      setJobsOpen(true);
      setMessage(
        `After photo uploaded for ${TIER_LABELS[updated.package_level] || updated.package_level}. Review and approve to include in the report.`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not upload after photo");
    } finally {
      setBusyKey(null);
    }
  }

  if (!syncedPhotos.length) {
    return (
      <section className="card home-safety-section">
        <h2>AI visualizations</h2>
        <p className="muted">
          Save the assessment and sync photos first. Then walk through Assessment → Recommendations →
          Plan → Render → Review.
        </p>
      </section>
    );
  }

  const busy = !!busyKey;

  return (
    <section className="card home-safety-section home-safety-ai-assessor-panel">
      <h2>AI visualizations</h2>
      <p className="muted home-safety-section-hint">
        Walk Assessment → Recommendations → Plan → Render → Review. Only human-approved,
        non-stub concepts merge into the family report below — stubs and unfinished jobs never
        block report creation. If AI does not produce an after photo, upload one manually.
      </p>

      {message ? (
        <p className="home-safety-saved-badge" role="status" aria-live="polite">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="error-text" role="alert">
          {error}
        </p>
      ) : null}

      <div className="ai-phase-setup">
        <label>
          Room photo
          <select
            value={selectedPhotoId ?? ""}
            onChange={(e) => {
              setSelectedPhotoId(Number(e.target.value));
              setAssessmentConfirmed(false);
              setAnalysisSkipped(false);
              setAnalysisResult(null);
              setVisionOpen(false);
              setPlanOpen(false);
              setUploadOpen(false);
              setJobsOpen(false);
            }}
          >
            {syncedPhotos.map((photo) => (
              <option key={photo.documentId} value={photo.documentId!}>
                {photo.caption || `Photo #${photo.documentId}`} ·{" "}
                {ROOM_TYPE_OPTIONS.find((r) => r.value === photo.roomType)?.label || "No room"}
              </option>
            ))}
          </select>
        </label>
        <fieldset className="ai-phase-tiers">
          <legend>Package tiers</legend>
          {ACTIVE_TIERS.map((tier) => (
            <label key={tier} className="ai-phase-check">
              <input
                type="checkbox"
                checked={selectedPackageTiers.includes(tier)}
                onChange={() =>
                  onPackageTiersChange(
                    selectedPackageTiers.includes(tier)
                      ? selectedPackageTiers.filter((t) => t !== tier)
                      : [...selectedPackageTiers, tier],
                  )
                }
              />
              <span className="ai-phase-check-text">{TIER_LABELS[tier]}</span>
            </label>
          ))}
        </fieldset>
        {selectedPhotoId ? <PhotoThumb documentId={selectedPhotoId} caption={selectedPhoto?.caption || ""} /> : null}
      </div>

      <div
        className="ai-phase-product-picker card"
        style={{ margin: "1rem 0", padding: "1rem" }}
        role="group"
        aria-labelledby="ai-products-picker-heading"
        aria-describedby="ai-products-picker-hint"
      >
        <h3 id="ai-products-picker-heading" style={{ marginTop: 0 }}>
          Products for the after photo
        </h3>
        <p id="ai-products-picker-hint" className="muted" style={{ marginTop: 0 }}>
          Check the catalog products to insert into the room (e.g. shower chair / folding seat).
          Then open Plan &amp; generate → Build concept.
        </p>
        {availableProducts.length ? (
          <ul className="ai-phase-checklist" aria-label="Catalog products for after photo">
            {availableProducts.map((p) => {
              const checked = selectedProductIds.includes(p.id);
              return (
                <li key={p.id}>
                  <label className="ai-phase-check">
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={busy}
                      onChange={() =>
                        setSelectedProductIds((prev) =>
                          prev.includes(p.id)
                            ? prev.filter((x) => x !== p.id)
                            : [...prev, p.id],
                        )
                      }
                    />
                    <span className="ai-phase-check-text">
                      {p.label}
                      {p.code ? (
                        <span className="ai-phase-check-id">
                          <span className="visually-hidden">Product code </span>
                          {p.code}
                        </span>
                      ) : null}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="muted" role="status">
            {catalog?.products?.length
              ? "No products matched this room/solutions yet. Confirm the photo has a room type and solutions exist on the improvement plan."
              : "Catalog is empty — load Master Data / catalog products first."}
          </p>
        )}
        {selectedProductIds.length ? (
          <div
            className="home-safety-viz-products ai-phase-selected-products"
            role="region"
            aria-labelledby="ai-selected-products-heading"
          >
            <h4 id="ai-selected-products-heading" className="home-safety-viz-products-heading">
              Selected for after photo ({selectedProductIds.length})
            </h4>
            <ul className="home-safety-viz-products-list">
              {availableProducts
                .filter((p) => selectedProductIds.includes(p.id))
                .map((p) => (
                  <li key={p.id}>{p.label}</li>
                ))}
            </ul>
          </div>
        ) : (
          <p className="muted" style={{ marginBottom: 0 }} role="status">
            No products selected yet — check items above before building a concept.
          </p>
        )}
        <p className="muted" style={{ marginBottom: 0 }} aria-live="polite">
          {selectedProductIds.length} product{selectedProductIds.length === 1 ? "" : "s"} selected
          for the after photo.
        </p>
      </div>

      <div className="ai-phase-gates">
        <button
          type="button"
          className={assessmentConfirmed ? "secondary" : "primary"}
          disabled={busy}
          onClick={() => {
            setAssessmentConfirmed(true);
            setPlanOpen(true);
          }}
        >
          {assessmentConfirmed ? "Assessment confirmed ✓" : "1. Confirm assessment inputs"}
        </button>
        <button
          type="button"
          className="primary"
          disabled={busy || !selectedPhotoId}
          onClick={() => void runAnalysis({ force: !!analysisResult })}
        >
          {analysisResult?.status === "SUCCEEDED"
            ? analysisResult.cache_hit
              ? "3. Analysis cached — re-run"
              : "3. Re-run room analysis"
            : "3. Run room analysis"}
        </button>
        <button
          type="button"
          className="secondary"
          disabled={busy || !assessmentConfirmed}
          onClick={() => {
            setAnalysisSkipped(true);
            setPlanOpen(true);
            setMessage("Continuing without vision analysis. Select recommendations, then generate.");
          }}
        >
          {analysisSkipped ? "Analysis skipped ✓" : "Continue without analysis"}
        </button>
      </div>

      {analysisResult?.status === "SUCCEEDED" ? (
        <OpsAccordion
          title="Vision suggestions"
          hint={`${analysisResult.mapped_suggestions?.length ?? 0} mapped`}
          open={visionOpen}
          onOpenChange={setVisionOpen}
        >
          <div className="ai-phase-analysis-summary">
            <p className="muted">
              {analysisResult.provider}/{analysisResult.model_version}
              {analysisResult.cache_hit ? " · cache hit" : ""} — advisory only; solutions still come
              from rules.
            </p>
            {(analysisResult.mapped_suggestions || []).length ? (
              <ul className="ai-phase-checklist">
                {analysisResult.mapped_suggestions.map((s) => (
                  <li key={`${s.finding_code}-${s.solution_id}`}>
                    <strong>{s.finding_code}</strong> → {s.solution_id} ({s.confidence_percent}%
                    {s.requires_human_verification ? ", confirm" : ""})
                    {s.evidence ? <span className="muted"> — {s.evidence}</span> : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No mapped findings above confidence threshold.</p>
            )}
          </div>
        </OpsAccordion>
      ) : null}

      <OpsAccordion
        title="Plan & generate"
        hint="Recommendations → build concept"
        open={planOpen}
        onOpenChange={setPlanOpen}
      >
        <VisualizationPhaseBoard
          mode="prep"
          availableSolutions={availableSolutions}
          selectedSolutionIds={selectedSolutionIds}
          availableProducts={availableProducts}
          selectedProductIds={selectedProductIds}
          assessmentConfirmed={assessmentConfirmed}
          analysisReady={analysisReady}
          onToggleSolution={(id) =>
            setSelectedSolutionIds((prev) =>
              prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
            )
          }
          onToggleProduct={(id) =>
            setSelectedProductIds((prev) =>
              prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
            )
          }
          onConfirmAssessment={() => setAssessmentConfirmed(true)}
          onSkipAnalysis={() => setAnalysisSkipped(true)}
          onRunAnalysis={() => void runAnalysis()}
          analysisResult={analysisResult}
          onGenerate={async () => {
            setPlanOpen(true);
            await runGenerate();
          }}
          onUploadConcept={(file) => handleUploadConcept(file)}
          busy={busy}
        />
      </OpsAccordion>

      <OpsAccordion
        title="Upload after photo"
        hint="If AI did not generate one"
        open={uploadOpen}
        onOpenChange={setUploadOpen}
      >
        <div className="ai-phase-upload-row">
          <label className="ai-phase-upload">
            <span>Choose an after / concept image</span>
            <input
              type="file"
              accept="image/*"
              disabled={busy || !selectedPhotoId}
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (file) void handleUploadConcept(file, activeJob?.ai_job_id);
              }}
            />
          </label>
          <p className="muted" style={{ margin: 0, fontSize: "0.85rem" }}>
            Uses the first selected package tier
            {selectedPackageTiers[0]
              ? ` (${TIER_LABELS[selectedPackageTiers[0]] || selectedPackageTiers[0]})`
              : " (Essential)"}
            , or replaces the concept on the selected job.
          </p>
        </div>
      </OpsAccordion>

      {activeJob?.generated_document_id ? (
        <VisualizationConceptGallery job={activeJob} />
      ) : null}

      <OpsAccordion
        title="Jobs for this photo"
        hint={
          photoJobs.length
            ? `${photoJobs.length} job${photoJobs.length === 1 ? "" : "s"}${
                activeJob?.review_status === "approved" ? " · approved after above" : ""
              }`
            : "None yet"
        }
        open={jobsOpen}
        onOpenChange={setJobsOpen}
      >
        {photoJobs.length ? (
          <div className="ai-phase-jobs">
            <div
              className="ai-phase-job-tabs"
              role="tablist"
              aria-label="Visualization jobs for this photo"
            >
              {photoJobs.map((job) => {
                const selected = activeJob?.ai_job_id === job.ai_job_id;
                const tierLabel = TIER_LABELS[job.package_level] || job.package_level;
                const phaseLabel = job.current_phase || job.status;
                return (
                  <button
                    key={job.ai_job_id}
                    type="button"
                    role="tab"
                    id={`ai-job-tab-${job.ai_job_id}`}
                    aria-selected={selected}
                    aria-controls={`ai-job-panel-${job.ai_job_id}`}
                    tabIndex={selected ? 0 : -1}
                    className={selected ? "ai-phase-job-tab is-active" : "ai-phase-job-tab"}
                    onClick={() => setSelectedJobId(job.ai_job_id)}
                  >
                    {tierLabel}
                  <span>
                    {job.review_status === "approved"
                      ? "approved"
                      : phaseLabel}
                  </span>
                  <span className="visually-hidden">
                    {`, ${
                      job.review_status === "approved" ? "approved" : phaseLabel
                    }${
                      job.product_labels?.length
                        ? `, products ${job.product_labels.join(", ")}`
                        : ""
                    }`}
                  </span>
                  </button>
                );
              })}
            </div>
            {activeJob ? (
              <div
                className="ai-phase-job-panel"
                role="tabpanel"
                id={`ai-job-panel-${activeJob.ai_job_id}`}
                aria-labelledby={`ai-job-tab-${activeJob.ai_job_id}`}
              >
                <VisualizationPhaseBoard
                  mode="job"
                  job={activeJob}
                  analysisResult={analysisResult}
                  onRunAnalysis={() => void runAnalysis({ force: true })}
                  onReview={(action, notes) => handleReview(activeJob.ai_job_id, action, notes)}
                  onUploadConcept={(file) => handleUploadConcept(file, activeJob.ai_job_id)}
                  busy={busy}
                  showConceptGallery={false}
                />
              </div>
            ) : null}
          </div>
        ) : (
          <p className="muted" style={{ margin: 0 }}>
            No visualization jobs for this photo yet — open Plan & generate above.
          </p>
        )}
      </OpsAccordion>
    </section>
  );
}

function OpsAccordion({
  title,
  hint,
  open,
  onOpenChange,
  children,
}: {
  title: string;
  hint?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: ReactNode;
}) {
  return (
    <div className="ai-ops-accordion">
      <button
        type="button"
        className="ai-ops-accordion-toggle"
        aria-expanded={open}
        onClick={() => onOpenChange(!open)}
      >
        <span className="ai-ops-accordion-title">
          {title}
          {hint ? <em className="ai-ops-accordion-hint">{hint}</em> : null}
        </span>
        <span aria-hidden>{open ? "▲" : "▼"}</span>
      </button>
      {open ? <div className="ai-ops-accordion-body">{children}</div> : null}
    </div>
  );
}

function PhotoThumb({ documentId, caption }: { documentId: number; caption: string }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let url: string | null = null;
    let cancelled = false;
    fetchStaffPhotoBlob(documentId)
      .then((blobUrl) => {
        if (!cancelled) {
          url = blobUrl;
          setSrc(blobUrl);
        }
      })
      .catch(() => {
        if (!cancelled) setSrc(null);
      });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [documentId]);

  if (!src) {
    return <div className="home-safety-family-photo-placeholder">Photo #{documentId}</div>;
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={src} alt={caption || "Assessment photo"} className="ai-phase-setup-thumb" />;
}
