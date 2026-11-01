"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  TIER_LABELS,
  listVisualizationJobs,
  reviewVisualizationJob,
  type AIVisualizationJob,
} from "@/lib/livewell/aiVisualizations";
import { VisualizationPhaseBoard } from "@/components/livewell/VisualizationPhaseBoard";

export function AIJobsAdminEditor() {
  const [jobs, setJobs] = useState<AIVisualizationJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterAssessment, setFilterAssessment] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await listVisualizationJobs(filterAssessment.trim() || undefined);
      setJobs(rows);
      if (selectedId && !rows.some((j) => j.ai_job_id === selectedId)) {
        setSelectedId(rows[0]?.ai_job_id ?? null);
      } else if (!selectedId && rows[0]) {
        setSelectedId(rows[0].ai_job_id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load AI jobs");
    } finally {
      setLoading(false);
    }
  }, [filterAssessment, selectedId]);

  useEffect(() => {
    reload();
  }, [reload]);

  const selected = jobs.find((j) => j.ai_job_id === selectedId) || null;

  async function review(action: "approve" | "reject" | "regenerate", notes?: string) {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await reviewVisualizationJob(selected.ai_job_id, action, notes);
      setJobs((prev) => prev.map((j) => (j.ai_job_id === updated.ai_job_id ? updated : j)));
      setSelectedId(updated.ai_job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Review failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="home-safety-ai-admin">
      <div className="home-safety-rubric-admin actions" style={{ marginBottom: "1rem" }}>
        <input aria-label="Filter by assessment ID"
          type="search"
          placeholder="Filter by assessment ID"
          value={filterAssessment}
          onChange={(e) => setFilterAssessment(e.target.value)}
        />
        <button type="button" onClick={reload} disabled={loading}>
          Refresh
        </button>
      </div>

      {error && <p className="error-text">{error}</p>}
      {loading ? (
        <p className="muted">Loading…</p>
      ) : jobs.length === 0 ? (
        <p className="muted">No AI visualization jobs yet.</p>
      ) : (
        <div className="ai-admin-layout">
          <table className="data-table">
            <thead>
              <tr>
                <th>Job</th>
                <th>Assessment</th>
                <th>Room</th>
                <th>Tier</th>
                <th>Products</th>
                <th>Phase</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr
                  key={job.ai_job_id}
                  className={selectedId === job.ai_job_id ? "is-selected" : undefined}
                  onClick={() => setSelectedId(job.ai_job_id)}
                  style={{ cursor: "pointer" }}
                >
                  <td>{job.ai_job_id}</td>
                  <td>
                    <Link href={`/kushalaya/assess/${job.assessment_id}/visualizations`} title={job.assessment_id}>
                      Home safety assessment
                    </Link>
                  </td>
                  <td>{job.room_type}</td>
                  <td>{TIER_LABELS[job.package_level] || job.package_level}</td>
                  <td>
                    {(job.product_labels?.length
                      ? job.product_labels
                      : job.product_codes
                    )?.slice(0, 2).join(", ") || "—"}
                    {(job.product_labels?.length || job.product_codes?.length || 0) > 2
                      ? "…"
                      : ""}
                  </td>
                  <td>{job.current_phase || "—"}</td>
                  <td>
                    {job.status}
                    {job.review_status !== "pending" ? ` / ${job.review_status}` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {selected ? (
            <div className="ai-admin-phase">
              <h2>
                Phase board · {selected.ai_job_id} ·{" "}
                {TIER_LABELS[selected.package_level] || selected.package_level}
              </h2>
              <VisualizationPhaseBoard
                mode="job"
                job={selected}
                onReview={review}
                busy={busy}
              />
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
