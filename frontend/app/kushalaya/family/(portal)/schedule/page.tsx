"use client";

import { familyTime } from "@/lib/livewell/familyTime";
import { useFamilyTimezone } from "@/lib/family-zone";

import { FamilyLink as Link } from "@/components/livewell/family/FamilyLink";
import { useEffect, useState } from "react";
import { FamilyShell } from "@/components/livewell/family/FamilyShell";
import { FamilyError } from "@/components/livewell/family/FamilyError";
import { FamilyLiveVisit } from "@/components/livewell/family/FamilyLiveVisit";
import { fetchFamilySchedule, type FamilySchedule, type FamilyVisit } from "@/lib/livewell/familyApi";

/**
 * Page loads of /schedule redirect to Requests (middleware.ts, Phase 2E).
 * This view stays for old in-app links: visits only. Requests live on the
 * Requests page.
 */

const VISIT_STATUS: Record<string, string> = {
  completed: "Done",
  scheduled: "Booked",
  planned: "Booked",
  in_progress: "Happening now",
  cancelled: "Cancelled",
  missed: "Missed",
};

function VisitCard({ v, upcoming }: { v: FamilyVisit; upcoming?: boolean }) {
  const tz = useFamilyTimezone();
  const status = String(v.status || "").toLowerCase();
  return (
    <Link href={`/kushalaya/family/visits/${v.id}`} className="card home-safety-family-visit-card">
      <div className="home-safety-family-report-top">
        <strong>{v.visit_type}</strong>
        <span
          className={`home-safety-pill ${upcoming ? "home-safety-pill-good" : "home-safety-pill-neutral"}`}
        >
          {upcoming ? "Coming up" : (VISIT_STATUS[status] ?? "Visit")}
        </span>
      </div>
      <p className="muted home-safety-list-meta">
        {familyTime(v.visited_at, tz)}
        {v.staff_name ? ` · ${v.staff_name}` : ""}
      </p>
      {v.summary ? <p className="home-safety-visit-teaser">{v.summary}</p> : null}
      <span className="home-safety-visit-open">Details →</span>
    </Link>
  );
}

export default function FamilySchedulePage() {
  const [data, setData] = useState<FamilySchedule | null>(null);
  const [error, setError] = useState("");

  function load() {
    setError("");
    fetchFamilySchedule()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <FamilyShell title="Visits" subtitle="What is coming up and what has been done">
      <FamilyError message={error} onRetry={load} what="the visit schedule" />

      <nav className="fh-actions" aria-label="Visit actions">
        <Link className="fh-action" href="/kushalaya/family/services">
          Request a visit or service
        </Link>
      </nav>

      {!data ? (
        error ? null : <p>Loading…</p>
      ) : (
        <>
          <section className="home-safety-family-p0-section">
            <h2 className="home-safety-family-p0-heading">Coming up</h2>
            <FamilyLiveVisit className="card" />
            {data.upcoming.length === 0 ? (
              <div className="card home-safety-empty">
                <p>None booked.</p>
                <p className="muted">
                  <Link href="/kushalaya/family/services">Request a visit</Link>
                </p>
              </div>
            ) : (
              <ul className="home-safety-family-report-list">
                {data.upcoming.map((v) => (
                  <li key={v.id}>
                    <VisitCard v={v} upcoming />
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="home-safety-family-p0-section">
            <h2 className="home-safety-family-p0-heading">Recent</h2>
            {data.recent.length === 0 ? (
              <p className="muted">No visits yet.</p>
            ) : (
              <ul className="home-safety-family-report-list">
                {data.recent.map((v) => (
                  <li key={v.id}>
                    <VisitCard v={v} />
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </FamilyShell>
  );
}
