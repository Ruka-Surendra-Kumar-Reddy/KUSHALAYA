"use client";

import { useState } from "react";
import { formatIST } from "@/lib/ist";
import { isTodayIST, startFieldJob } from "@/lib/jobs";

/**
 * Start (or continue) a booked assessment. Marks arrival only after an inline
 * confirm when the booking is not for today (IST); shows any real error.
 */
export function StartAssessmentButton({
  job,
  label = "Start assessment",
  className = "cp-go",
}: {
  job: { id: number; status?: string | null; scheduled_at?: string | null };
  label?: string;
  className?: string;
}) {
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function go() {
    setBusy(true);
    setError("");
    try {
      await startFieldJob(job);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the assessment");
      setBusy(false);
    }
  }

  function click() {
    if (job.status === "checked_in" || isTodayIST(job.scheduled_at)) void go();
    else setAsking(true);
  }

  return (
    <span className="sa">
      {!asking ? (
        <button type="button" className={className} disabled={busy} onClick={click}>
          {busy ? "Opening…" : label}
        </button>
      ) : (
        <span className="sa-ask" role="alert">
          <span>
            This assessment is booked for{" "}
            {job.scheduled_at ? formatIST(job.scheduled_at, { dateOnly: true }) : "another day"}. Mark arrived now and
            start?
          </span>
          <button type="button" className={className} disabled={busy} onClick={() => void go()}>
            {busy ? "Opening…" : "Yes, start"}
          </button>
          <button type="button" className="secondary" disabled={busy} onClick={() => setAsking(false)}>
            Cancel
          </button>
        </span>
      )}
      {error ? <small className="error-text">{error}</small> : null}
    </span>
  );
}
