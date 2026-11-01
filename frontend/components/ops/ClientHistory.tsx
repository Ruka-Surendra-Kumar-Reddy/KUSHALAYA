"use client";

import { useEffect, useMemo, useState } from "react";
import { jobWhen, listJobs, type CareJob } from "@/lib/jobs";
import { arrivalAt, isStaleCheckIn, staleLabel } from "@/lib/run-sheet";
import { checklistLine } from "@/lib/incident-reports";
import { placeLines, type PlaceLine } from "@/lib/visit-location";
import type { SafeHomeVisit } from "@/lib/livewell/visit-types";
import Link from "next/link";
import { StaffVisitPhoto } from "@/components/ops/StaffVisitPhoto";
import "./client-history.css";
import { publicSafetyScoreName } from "@/lib/public-brand";

type Kind = "visit" | "assessment" | "install" | "request";
type Item = {
  key: string;
  kind: Kind;
  title: string;
  when: string | null;
  status: string;
  statusLabel: string;
  who: string;
  lines: string[];
  /** Check-in / check-out location with a map link (jobs only, staff only). */
  places?: PlaceLine[];
  photoIds?: number[];
};

type Assessment = { id: string; status: string; score: number | null; assessor: string; completed_at: string | null; updated_at: string | null };
type Request = { id: string; title?: string; service_name?: string; service_label?: string; status?: string; created_at?: string; notes?: string };

const KIND_LABEL: Record<Kind, string> = {
  visit: "Visit",
  assessment: "Assessment",
  install: "Installation",
  request: "Request",
};

const STATUS_LABEL: Record<string, string> = {
  requested: "Requested",
  confirmed: "Scheduled",
  scheduled: "Scheduled",
  on_the_way: "On the way",
  checked_in: "Checked in",
  completed: "Completed",
  done: "Completed",
  cancelled: "Cancelled",
  declined: "Declined",
  missed: "Missed",
  draft: "In progress",
};

const OPEN = new Set(["requested", "scheduled", "confirmed", "on_the_way", "checked_in", "draft"]);

/**
 * Everything that happened for one client, newest first: scheduled and finished
 * jobs, logged visits, assessments and family requests, each with its status.
 */
export function ClientHistory({
  elderId,
  visits,
  assessments,
  requests,
}: {
  elderId: number;
  visits: SafeHomeVisit[];
  assessments: Assessment[];
  requests: Request[];
}) {
  const [jobs, setJobs] = useState<CareJob[]>([]);
  const [kind, setKind] = useState<Kind | "all">("all");
  const [state, setState] = useState<"all" | "open" | "done">("all");

  useEffect(() => {
    listJobs({ elder_id: elderId }).then(setJobs).catch(() => undefined);
  }, [elderId]);

  const items = useMemo<Item[]>(() => {
    const out: Item[] = [];
    for (const j of jobs) {
      // History is the past: a cancelled visit that was booked for a later date is not shown.
      if (j.status === "cancelled" && j.scheduled_at && new Date(j.scheduled_at).getTime() > Date.now()) continue;
      out.push({
        key: `j${j.id}`,
        kind: j.kind,
        title: j.title,
        when: j.completed_at ?? j.scheduled_at,
        status: j.status,
        statusLabel: isStaleCheckIn(j) ? staleLabel(j) : j.status_label,
        // A finished visit with no caregiver was logged by the care manager.
        who: j.caregiver_name || (j.status === "completed" ? "Logged by staff" : "Not assigned"),
        lines: [
          j.tasks,
          arrivalAt(j) ? `Checked in ${jobWhen(arrivalAt(j) as string)}` : "",
          j.report?.checks
            ? `KushLife check: ${Object.entries(j.report.checks)
                .map(([k, v]) => `${k} ${v === "ok" ? "✓" : "!"}`)
                .join(" · ")}`
            : "",
          j.caregiver_note ? `Caregiver: ${j.caregiver_note}` : "",
          checklistLine(j.report?.checklist),
          j.report?.photo_ids?.length ? `${j.report.photo_ids.length} photo${j.report.photo_ids.length === 1 ? "" : "s"}` : "",
          j.report?.hazard_ids?.length ? "Flagged a new hazard" : "",
          j.staff_note ? `Staff note: ${j.staff_note}` : "",
        ].filter(Boolean),
        places: placeLines(j.visit_location, j.status),
        photoIds: (j.report?.photo_ids ?? []).slice(0, 12),
      });
    }
    for (const v of visits) {
      const at = (v as { visited_at?: string }).visited_at ?? null;
      const status = String((v as { status?: string }).status || "completed");
      const score = (v as { stability_score?: number | null }).stability_score;
      out.push({
        key: `v${v.id}`,
        kind: "visit",
        title: String((v as { visit_type?: string }).visit_type || "Visit"),
        when: at,
        status,
        statusLabel: STATUS_LABEL[status] ?? status,
        who: String((v as { staff_name?: string }).staff_name || ""),
        lines: [
          String((v as { summary?: string }).summary || ""),
          score != null ? `KushLife stability ${score}/100 (higher is steadier)` : "",
          (v as { location?: { at_home?: boolean } | null }).location?.at_home === false ? "Logged away from home" : "",
        ].filter(Boolean),
      });
    }
    for (const a of assessments) {
      out.push({
        key: `a${a.id}`,
        kind: "assessment",
        title: "Home safety assessment",
        when: a.completed_at ?? a.updated_at,
        status: a.status,
        statusLabel: STATUS_LABEL[a.status] ?? a.status,
        who: a.assessor,
        lines: a.score != null && a.status === "completed" ? [`${publicSafetyScoreName()} ${a.score}/100`] : [],
      });
    }
    for (const r of requests) {
      const status = String(r.status || "requested");
      out.push({
        key: `r${r.id}`,
        kind: "request",
        title: r.service_label || r.title || r.service_name || "Request",
        when: r.created_at ?? null,
        status,
        statusLabel: STATUS_LABEL[status] ?? status,
        who: "Family",
        lines: r.notes ? [`“${r.notes}”`] : [],
      });
    }
    return out.sort((a, b) => new Date(b.when ?? 0).getTime() - new Date(a.when ?? 0).getTime());
  }, [jobs, visits, assessments, requests]);

  const shown = items.filter(
    (i) =>
      (kind === "all" || i.kind === kind) &&
      (state === "all" || (state === "open" ? OPEN.has(i.status) : !OPEN.has(i.status))),
  );

  return (
    <>
      <section className="card ch">
        <div className="ch-head">
          <h2>Timeline</h2>
          <div className="ch-filters">
            {(["all", "visit", "assessment", "install", "request"] as const).map((k) => (
              <button key={k} type="button" className={kind === k ? "is-on" : ""} aria-pressed={kind === k} onClick={() => setKind(k)}>
                {k === "all" ? "Everything" : `${KIND_LABEL[k]}s`}
              </button>
            ))}
            <select value={state} onChange={(e) => setState(e.target.value as typeof state)} aria-label="Status">
              <option value="all">Any status</option>
              <option value="open">Open</option>
              <option value="done">Finished</option>
            </select>
          </div>
        </div>
        {items.length === 0 ? (
          <p className="ch-empty">
            No visits yet —{" "}
            <Link href={`/kushalaya/visits?schedule=1&elder=${elderId}&kind=assessment`}>Book first assessment</Link>
          </p>
        ) : shown.length === 0 ? (
          <p className="ch-empty">Nothing matches these filters.</p>
        ) : (
          <ol className="ch-list">
            {shown.map((i) => (
              <li key={i.key} className={`is-${i.kind}`}>
                <span className="ch-dot" aria-hidden="true" />
                <div className="ch-body">
                  <div className="ch-top">
                    <span className="ch-kind">{KIND_LABEL[i.kind]}</span>
                    <strong>{i.title}</strong>
                    <span className={`ch-status is-${i.status}`}>{i.statusLabel}</span>
                  </div>
                  <p className="ch-meta">
                    {i.when ? jobWhen(i.when) : "No date"}
                    {i.who ? ` · ${i.who}` : ""}
                  </p>
                  {i.lines.map((l) => (
                    <p key={l} className="ch-line">
                      {l}
                    </p>
                  ))}
                  {i.places?.map((p) => (
                    <p key={p.text} className={`ch-line${p.away ? " is-away" : ""}`}>
                      {p.text}
                      {p.href ? (
                        <>
                          {" · "}
                          <a href={p.href} target="_blank" rel="noopener noreferrer">
                            View on map
                          </a>
                        </>
                      ) : null}
                    </p>
                  ))}
                  {i.photoIds?.length ? (
                    <div className="cp-photos">
                      {i.photoIds.map((id) => (
                        <StaffVisitPhoto key={id} id={id} />
                      ))}
                    </div>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>
    </>
  );
}
