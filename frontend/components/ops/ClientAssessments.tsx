"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { formatIST } from "@/lib/ist";
import { fetchClientAssessments, type ClientAssessments as Data } from "@/lib/livewell/clientProfileApi";
import { StartAssessmentButton } from "./StartAssessmentButton";
import { can } from "@/lib/roles";
import { publicSafetyScoreName } from "@/lib/public-brand";

function Change({ value }: { value: number | null }) {
  if (value == null || value === 0) return value === 0 ? <span className="muted">No change</span> : null;
  return <span className={value > 0 ? "ca-up" : "ca-down"}>{value > 0 ? `+${value}` : value}</span>;
}

/** Assessments tab: every assessment for this client, booked ones, and the last two compared. */
export function ClientAssessments({ elderId }: { elderId: number }) {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");
  const [showCompare, setShowCompare] = useState(false);
  const bookHref = `/kushalaya/visits?schedule=1&elder=${elderId}&kind=assessment`;

  useEffect(() => {
    fetchClientAssessments(elderId)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load assessments"));
  }, [elderId]);

  if (error) return <p className="card error-text">{error}</p>;
  if (!data) return <p className="card muted">Loading assessments…</p>;

  const empty = data.assessments.length === 0 && data.booked.length === 0;
  const c = data.compare;

  return (
    <section className="card ca">
      <div className="cp-card-head">
        <h2>Assessments</h2>
        <div className="ca-head-actions">
          {c ? (
            <button type="button" className="cp-linkbtn" onClick={() => setShowCompare((v) => !v)}>
              {showCompare ? "Hide comparison" : "Compare with previous"}
            </button>
          ) : null}
          {can("edit") && data.booked.length === 0 ? (
            <Link className="secondary" href={bookHref}>
              Book new assessment
            </Link>
          ) : null}
        </div>
      </div>

      {showCompare && c ? (
        <div className="ca-compare">
          <div className="ca-compare-scores">
            <div>
              <span>Previous · {formatIST(c.before.date, { dateOnly: true }) || "Not recorded"}</span>
              <strong>{c.before.score ?? "Not recorded"}</strong>
            </div>
            <div>
              <span>Latest · {formatIST(c.now.date, { dateOnly: true }) || "Not recorded"}</span>
              <strong>{c.now.score ?? "Not recorded"}</strong>
            </div>
          </div>
          {c.areas.length ? (
            <ul className="ca-areas">
              {c.areas.map((a) => (
                <li key={a.area}>
                  <strong>{a.area}</strong>
                  <span className="muted">
                    {" "}
                    {a.before} → {a.now}{" "}
                  </span>
                  <Change value={a.change} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No area changed between the two assessments.</p>
          )}
        </div>
      ) : null}

      {empty ? (
        <p className="muted">
          No assessments yet.{" "}
          <Link href={bookHref}>Book first assessment</Link>
        </p>
      ) : null}

      <ul className="ca-list">
        {data.booked.map((b) => (
          <li key={`b${b.job_id}`}>
            <div className="ca-main">
              <strong>{b.title || "Home safety assessment"}</strong>
              <span className="muted"> · {b.scheduled_at ? formatIST(b.scheduled_at) : "Not scheduled yet"}</span>
            </div>
            <span className="cp-pill cp-pill-scheduled">{b.started ? "In progress" : "Booked"}</span>
            {can("edit") ? (
              <StartAssessmentButton
                job={{ id: b.job_id, status: b.status, scheduled_at: b.scheduled_at }}
                label={b.started ? "Continue" : "Start"}
                className="ca-go"
              />
            ) : null}
          </li>
        ))}
        {data.assessments.map((a) => (
          <li key={a.id}>
            <div className="ca-main">
              <strong>{a.date ? formatIST(a.date, { dateOnly: true }) : "Not recorded"}</strong>
              {a.score != null ? (
                <span>
                  {" "}
                  · {publicSafetyScoreName()} {a.score} out of 100{a.band ? ` (${a.band})` : ""} <Change value={a.change} />
                </span>
              ) : null}
              <div className="muted">{a.assessor ? `By ${a.assessor}` : "Assessor not recorded"}</div>
            </div>
            <span className={`cp-pill ${a.status === "completed" ? "cp-pill-completed" : "cp-pill-open"}`}>
              {a.status_label}
            </span>
            {a.status === "completed" ? (
              <Link className="ca-act" href={`/kushalaya/assessments/${encodeURIComponent(a.id)}/report`}>
                View report
              </Link>
            ) : !can("edit") ? null : a.job_id ? (
              <Link className="ca-act" href={`/caregiver/assess/${a.job_id}`}>
                Continue
              </Link>
            ) : (
              <Link className="ca-act" href={`/kushalaya/assessments/${encodeURIComponent(a.id)}`}>
                Continue
              </Link>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
