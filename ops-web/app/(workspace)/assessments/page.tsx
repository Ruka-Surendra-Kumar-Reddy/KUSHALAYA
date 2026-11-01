"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { formatDate, statusTone } from "@/lib/format";
import { fetchAssessments, type AssessmentSummary } from "@/lib/opsApi";

export default function AssessmentsPage() {
  const [rows, setRows] = useState<AssessmentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetchAssessments()
      .then(setRows)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load assessments"))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((row) =>
      `${row.client_first_name} ${row.client_last_name} ${row.client_address} ${row.status}`
        .toLowerCase()
        .includes(needle),
    );
  }, [q, rows]);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Assessments</h1>
          <p className="muted">Stay in this workspace. Open a record to review or continue the checklist later.</p>
        </div>
      </div>
      <div className="toolbar">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search client or address" />
      </div>
      {error && <p className="error">{error}</p>}
      <section className="panel">
        {loading ? (
          <p className="empty">Loading…</p>
        ) : filtered.length === 0 ? (
          <p className="empty">No assessments yet. Start one from a client.</p>
        ) : (
          filtered.map((row) => (
            <div className="row" key={row.assessment_id}>
              <div>
                <Link href={`/assessments/${row.assessment_id}`}>
                  <strong>
                    {`${row.client_first_name} ${row.client_last_name}`.trim() ||
                      "Untitled assessment"}
                  </strong>
                </Link>
                <div className="muted">
                  {row.client_address || "No address"} · {formatDate(row.updated_at)}
                </div>
              </div>
              <span className={`badge ${statusTone(row.status)}`}>{row.status}</span>
            </div>
          ))
        )}
      </section>
    </>
  );
}
