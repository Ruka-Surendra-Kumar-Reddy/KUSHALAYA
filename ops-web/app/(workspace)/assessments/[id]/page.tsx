"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { getLegacyAppUrl } from "@/lib/api";
import { formatDate, statusTone } from "@/lib/format";
import { fetchAssessment, type AssessmentDetail } from "@/lib/opsApi";

export default function AssessmentDetailPage() {
  const params = useParams<{ id: string }>();
  const id = decodeURIComponent(params.id);
  const legacy = getLegacyAppUrl();
  const [row, setRow] = useState<AssessmentDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchAssessment(id)
      .then(setRow)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load assessment"));
  }, [id]);

  const rated = useMemo(() => {
    const ratings = row?.payload.ratings || {};
    return Object.values(ratings).filter((value) => value && value !== "na").length;
  }, [row]);

  if (!row && !error) return <p className="muted">Loading…</p>;
  if (!row) return <p className="error">{error}</p>;

  const p = row.payload;
  const name = `${p.clientFirstName} ${p.clientLastName}`.trim() || "Unnamed client";

  return (
    <>
      <div className="page-head">
        <div>
          <p className="muted">
            <Link href="/assessments">Assessments</Link>
          </p>
          <h1>{name}</h1>
          <p className="muted">{p.clientAddress || "No address"}</p>
        </div>
        <span className={`badge ${statusTone(row.status)}`}>{row.status}</span>
      </div>
      <section className="cards">
        <div className="card">
          <small>Updated</small>
          <p>{formatDate(row.updated_at)}</p>
        </div>
        <div className="card">
          <small>Completed</small>
          <p>{formatDate(row.completed_at)}</p>
        </div>
        <div className="card">
          <small>Rated items</small>
          <p>{rated}</p>
        </div>
      </section>
      <section className="panel">
        <h2>Household</h2>
        <div className="row">
          <span>Phone</span>
          <span>{p.clientPhone || "—"}</span>
        </div>
        <div className="row">
          <span>Email</span>
          <span>{p.clientEmail || "—"}</span>
        </div>
        <div className="row">
          <span>Family contact</span>
          <span>
            {p.familyContactName || "—"}
            {p.familyContactPhone ? ` · ${p.familyContactPhone}` : ""}
          </span>
        </div>
        <div className="row">
          <span>Assessor</span>
          <span>{p.assessorName || "—"}</span>
        </div>
        {p.elderId ? (
          <div className="row">
            <span>Client record</span>
            <Link href={`/clients/${p.elderId}`}>Open client</Link>
          </div>
        ) : null}
        {p.notes ? <p>{p.notes}</p> : null}
      </section>
      <section className="panel">
        <h2>Full checklist</h2>
        <p className="muted">
          The room-by-room wizard still lives in the current app. Phase 2 will move it here.
        </p>
        <p>
          <a className="btn" href={`${legacy}/livewell/assessments/${encodeURIComponent(id)}`}>
            Open checklist
          </a>
        </p>
      </section>
    </>
  );
}
