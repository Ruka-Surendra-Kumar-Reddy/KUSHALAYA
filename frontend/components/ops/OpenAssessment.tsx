"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchServerAssessment } from "@/lib/livewell/assessmentApi";

/** "field-job-12" → 12: assessments made in the checklist belong to a job. */
export function jobIdOf(assessmentId: string): number | null {
  const m = /^field-job-(\d+)$/.exec(assessmentId);
  return m ? Number(m[1]) : null;
}

/**
 * The only way to open an assessment (the old one-page wizard is gone):
 * completed → the report; unfinished → the 3-step checklist for its job.
 */
export function OpenAssessment({ id, reportHref, listHref }: { id: string; reportHref: string; listHref: string }) {
  const router = useRouter();
  const [stuck, setStuck] = useState<"" | "missing" | "old-draft">("");

  useEffect(() => {
    let cancelled = false;
    void fetchServerAssessment(id).then((a) => {
      if (cancelled) return;
      if (!a) return setStuck("missing");
      if (a.status === "completed") return router.replace(reportHref);
      const job = jobIdOf(id);
      if (job) return router.replace(`/caregiver/assess/${job}?from=assessments`);
      setStuck("old-draft");
    });
    return () => {
      cancelled = true;
    };
  }, [id, reportHref, router]);

  if (!stuck) return <p className="muted">Opening the assessment…</p>;
  return (
    <div className="card">
      <h1 style={{ marginTop: 0 }}>{stuck === "missing" ? "Assessment not found" : "Old unfinished draft"}</h1>
      <p className="muted">
        {stuck === "missing"
          ? "It may have been removed."
          : "This draft was started in the old form, which is no longer used. Start a new assessment for this client from Assessments."}
      </p>
      <p>
        <Link href={listHref}>Back to assessments</Link>
      </p>
    </div>
  );
}
