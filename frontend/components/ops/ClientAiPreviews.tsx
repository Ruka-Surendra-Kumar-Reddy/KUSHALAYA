"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuthedImage } from "@/components/useAuthedImage";
import { aiPreviewHref, listPreviews, type PreviewJob } from "@/lib/aiPreview";
import { can } from "@/lib/roles";
import "./ai-preview.css";

const WORD: Record<string, string> = {
  queued: "Making…",
  running: "Making…",
  needs_review: "Ready for review",
  completed: "Approved for family",
  failed: "Failed",
};

function status(j: PreviewJob): { text: string; tone: string } {
  if (j.review_status === "rejected") return { text: "Rejected", tone: "bad" };
  if (j.review_status === "approved" || j.status === "completed") return { text: "Approved for family", tone: "ok" };
  if (j.status === "failed") return { text: "Failed", tone: "bad" };
  if (j.status === "needs_review") return { text: "Ready for review", tone: "warn" };
  return { text: WORD[j.status] || j.status, tone: "info" };
}

function PreviewCard({ j }: { j: PreviewJob }) {
  const src = useAuthedImage(j.after_url || j.before_url);
  const s = status(j);
  const room = j.room_type.replace(/_/g, " ");
  const n = j.items.length;
  return (
    <li className="ap-tile">
      <Link className="ap-tile-link" href={aiPreviewHref({ assessment: j.assessment_id, job: j.ai_job_id })}>
        <span className="ap-tile-img">
          {src ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={src} alt={`AI preview of the ${room}`} />
          ) : (
            <span className={`ap-tile-ph${j.after_url || j.before_url ? " is-loading" : ""}`}>
              {j.after_url || j.before_url ? (
                <>
                  <span className="ap-spin" aria-hidden="true" />
                  <span className="ap-tile-ph-text">Loading picture…</span>
                </>
              ) : (
                <span className="ap-tile-ph-text">No picture yet</span>
              )}
            </span>
          )}
          <span className={`ap-tile-badge is-${s.tone}`}>{s.text}</span>
        </span>
        <span className="ap-tile-body">
          <strong>{room.charAt(0).toUpperCase() + room.slice(1)}</strong>
          <span className="muted">
            {n} product{n === 1 ? "" : "s"} · {j.package_level} ·{" "}
            {new Date(j.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
          </span>
        </span>
      </Link>
    </li>
  );
}

/** Health tab card: AI room previews for this client as picture cards, and the way in. */
export function ClientAiPreviews({ elderId }: { elderId: number }) {
  const [jobs, setJobs] = useState<PreviewJob[] | null>(null);
  useEffect(() => {
    listPreviews({ elder: elderId }).then(setJobs).catch(() => setJobs([]));
  }, [elderId]);

  return (
    <section className="card ap-client">
      <div className="ap-client-head">
        <div>
          <p className="ap-client-eyebrow">AI · before and after</p>
          <h2>See it in their home</h2>
          <p className="muted">The client&apos;s own room with the suggested safety products fitted. Families see it once you approve.</p>
        </div>
        <Link className="ap-client-cta" href={aiPreviewHref({ elder: elderId })}>
          {can("edit") ? "+ Make a preview" : "Open"}
        </Link>
      </div>
      {jobs === null ? (
        <p className="muted">Loading…</p>
      ) : jobs.length === 0 ? (
        <p className="ap-client-empty">No previews yet. Pick a room photo and the products, and the AI shows the room made safer.</p>
      ) : (
        <ul className="ap-tiles">
          {jobs.slice(0, 6).map((j) => (
            <PreviewCard key={j.ai_job_id} j={j} />
          ))}
        </ul>
      )}
    </section>
  );
}
