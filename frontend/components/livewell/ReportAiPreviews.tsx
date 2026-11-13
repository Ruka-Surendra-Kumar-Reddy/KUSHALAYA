"use client";

import { useEffect, useState } from "react";
import { useAuthedImage } from "@/components/useAuthedImage";
import { listPreviews, type PreviewJob } from "@/lib/aiPreview";

function Pair({ j }: { j: PreviewJob }) {
  const before = useAuthedImage(j.before_url);
  const after = useAuthedImage(j.after_url);
  const room = j.room_type.replace(/_/g, " ");
  const approved = j.review_status === "approved" || j.status === "completed";
  return (
    <li className={`rp-ai-pair rp-keep${approved ? "" : " no-print"}`}>
      <p className="rp-ai-room">
        {room.charAt(0).toUpperCase() + room.slice(1)}
        {approved ? null : <span className="rp-ai-draft"> · Not approved yet (not printed)</span>}
      </p>
      <div className="rp-ai-imgs">
        {(
          [
            ["Before", before],
            ["After", after],
          ] as const
        ).map(([label, src]) => (
          <figure key={label} className="rp-photo">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            {src ? <img src={src} alt={`${label}: ${room}`} /> : <div className="rp-photo-empty" />}
            <figcaption>{label}</figcaption>
          </figure>
        ))}
      </div>
    </li>
  );
}

/** Report section: the AI before/after room pictures made for this assessment. */
export function ReportAiPreviews({ assessmentId, title }: { assessmentId: string; title: React.ReactNode }) {
  const [jobs, setJobs] = useState<PreviewJob[]>([]);
  useEffect(() => {
    listPreviews({ assessment: assessmentId })
      .then((all) => {
        // A room that was regenerated keeps only its newest picture.
        const seen = new Set<string>();
        setJobs(
          all
            .filter((j) => j.after_url && j.review_status !== "rejected" && j.status !== "failed")
            .filter((j) => {
              const key = `${j.room_type}:${j.source_document_id}`;
              if (seen.has(key)) return false;
              seen.add(key);
              return true;
            }),
        );
      })
      .catch(() => setJobs([]));
  }, [assessmentId]);

  if (!jobs.length) return null;
  const printable = jobs.some((j) => j.review_status === "approved" || j.status === "completed");
  return (
    <section className={`rp-sec${printable ? "" : " no-print"}`}>
      {title}
      <ul className="rp-ai-list">
        {jobs.map((j) => (
          <Pair key={j.ai_job_id} j={j} />
        ))}
      </ul>
    </section>
  );
}
