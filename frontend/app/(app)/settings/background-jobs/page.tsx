"use client";

import Link from "next/link";
import { dateTimeIST } from "@/lib/ist";
import { Fragment, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getStoredAuth } from "@/lib/api";
import { canManageTenants } from "@/lib/auth";
import { Flash } from "@/components/Flash";
import { PageHeader } from "@/components/PageHeader";
import {
  JOB_STATUSES,
  cancelBackgroundJob,
  fetchAdminBackgroundJobs,
  jobTypeLabel,
  parseJobJson,
  retryBackgroundJob,
  runBackgroundJobNow,
  scheduleAttendanceScanJob,
  scheduleWorkflowScanJob,
  updateBackgroundJobStatus,
  type BackgroundJob,
} from "@/lib/backgroundJobs";

function formatWhen(value: string | null) {
  if (!value) return "—";
  return dateTimeIST(value);
}

function statusClass(status: string) {
  if (status === "SUCCEEDED") return "success";
  if (status === "FAILED") return "danger";
  if (status === "RUNNING") return "warning";
  if (status === "CANCELLED") return "muted";
  return "";
}

export default function BackgroundJobsAdminPage() {
  const router = useRouter();
  const auth = getStoredAuth();
  const [rows, setRows] = useState<BackgroundJob[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const data = await fetchAdminBackgroundJobs({
      status: statusFilter || undefined,
      limit: 100,
    });
    setRows(data);
    setLoading(false);
  }, [statusFilter]);

  useEffect(() => {
    if (!canManageTenants(auth?.role || "")) {
      router.replace("/unauthorized");
      return;
    }
    load().catch((e) => setError(String(e)));
  }, [auth?.role, load, router]);

  async function withAction(jobId: number, action: () => Promise<BackgroundJob>) {
    setBusyId(jobId);
    setError("");
    setMessage("");
    try {
      const updated = await action();
      setMessage(`Job #${updated.id} → ${updated.status}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  }

  async function enqueueScans() {
    setError("");
    setMessage("");
    try {
      await scheduleWorkflowScanJob();
      await scheduleAttendanceScanJob();
      setMessage("Workflow and attendance scans queued");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  if (!canManageTenants(auth?.role || "")) return null;

  return (
    <>
      <PageHeader
        title="Background jobs"
        subtitle="Super admin — inspect async work, retry failures, and run the next step"
        action={
          <Link href="/settings">
            <button type="button" className="secondary">
              Back to settings
            </button>
          </Link>
        }
      />
      <Flash
        error={error}
        message={message}
        onClear={() => {
          setError("");
          setMessage("");
        }}
      />

      <div className="card" style={{ marginBottom: "1rem" }}>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "0.75rem",
            alignItems: "flex-end",
            justifyContent: "space-between",
          }}
        >
          <div>
            <label>
              Status filter
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                style={{ display: "block", marginTop: "0.35rem", minWidth: "10rem" }}
              >
                <option value="">All</option>
                {JOB_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <button type="button" className="secondary" onClick={() => load()}>
              Refresh
            </button>
            <button type="button" onClick={enqueueScans}>
              Queue platform scans
            </button>
          </div>
        </div>
      </div>

      {loading ? (
        <p>Loading…</p>
      ) : rows.length === 0 ? (
        <div className="card">
          <p className="muted">No background jobs match this filter.</p>
        </div>
      ) : (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Type</th>
                <th>Tenant</th>
                <th>Status</th>
                <th>Attempts</th>
                <th>Scheduled</th>
                <th>Progress</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((job) => {
                const expanded = expandedId === job.id;
                const busy = busyId === job.id;
                return (
                  <Fragment key={job.id}>
                    <tr>
                      <td>
                        <button
                          type="button"
                          className="link-button"
                          onClick={() =>
                            setExpandedId(expanded ? null : job.id)
                          }
                        >
                          #{job.id}
                        </button>
                      </td>
                      <td>
                        <code>{jobTypeLabel(job.job_type)}</code>
                      </td>
                      <td>{job.tenant_id ?? "all"}</td>
                      <td>
                        <span className={statusClass(job.status)}>
                          {job.status}
                        </span>
                      </td>
                      <td>
                        {job.attempts}/{job.max_attempts}
                      </td>
                      <td>{formatWhen(job.scheduled_at)}</td>
                      <td className="muted" style={{ fontSize: "0.85rem" }}>
                        {job.progress_message || "—"}
                      </td>
                      <td>
                        <div
                          style={{
                            display: "flex",
                            flexWrap: "wrap",
                            gap: "0.35rem",
                          }}
                        >
                          {(job.status === "PENDING" ||
                            job.status === "RUNNING") && (
                            <button
                              type="button"
                              className="link-button"
                              disabled={busy}
                              onClick={() =>
                                withAction(job.id, () =>
                                  runBackgroundJobNow(job.id),
                                )
                              }
                            >
                              Run now
                            </button>
                          )}
                          {(job.status === "FAILED" ||
                            job.status === "CANCELLED") && (
                            <button
                              type="button"
                              className="link-button"
                              disabled={busy}
                              onClick={() =>
                                withAction(job.id, () =>
                                  retryBackgroundJob(job.id),
                                )
                              }
                            >
                              Retry
                            </button>
                          )}
                          {(job.status === "PENDING" ||
                            job.status === "RUNNING") && (
                            <button
                              type="button"
                              className="link-button"
                              disabled={busy}
                              onClick={() =>
                                withAction(job.id, () =>
                                  cancelBackgroundJob(job.id),
                                )
                              }
                            >
                              Cancel
                            </button>
                          )}
                          {job.status === "RUNNING" && (
                            <button
                              type="button"
                              className="link-button"
                              disabled={busy}
                              onClick={() =>
                                withAction(job.id, () =>
                                  updateBackgroundJobStatus(
                                    job.id,
                                    "PENDING",
                                    "Reset from running by administrator",
                                  ),
                                )
                              }
                            >
                              Reset
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {expanded && (
                      <tr key={`${job.id}-detail`}>
                        <td colSpan={8}>
                          <div
                            style={{
                              fontSize: "0.85rem",
                              display: "grid",
                              gap: "0.5rem",
                            }}
                          >
                            <div>
                              <strong>Started:</strong>{" "}
                              {formatWhen(job.started_at)} ·{" "}
                              <strong>Finished:</strong>{" "}
                              {formatWhen(job.finished_at)}
                            </div>
                            {job.error_message && (
                              <div style={{ color: "var(--danger, #c0392b)" }}>
                                <strong>Error:</strong> {job.error_message}
                              </div>
                            )}
                            <div>
                              <strong>Payload</strong>
                              <pre
                                style={{
                                  margin: "0.25rem 0 0",
                                  whiteSpace: "pre-wrap",
                                  fontSize: "0.8rem",
                                }}
                              >
                                {JSON.stringify(
                                  parseJobJson(job.payload_json),
                                  null,
                                  2,
                                )}
                              </pre>
                            </div>
                            {job.result_json && (
                              <div>
                                <strong>Result</strong>
                                <pre
                                  style={{
                                    margin: "0.25rem 0 0",
                                    whiteSpace: "pre-wrap",
                                    fontSize: "0.8rem",
                                  }}
                                >
                                  {JSON.stringify(
                                    parseJobJson(job.result_json),
                                    null,
                                    2,
                                  )}
                                </pre>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
