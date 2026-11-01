"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { formatIST } from "@/lib/ist";
import { assessmentDraft, startAssessment, type AssessmentDraft, type AssessmentFor } from "@/lib/jobs";
import "./new-assessment.css";

/** "Kamala has an unfinished assessment (12 answered, 27 Oct)." */
export function draftText(name: string, d: AssessmentDraft): string {
  const bits = [`${d.answered} answered`];
  if (d.since) bits.push(`from ${formatIST(d.since, { dateOnly: true })}`);
  return `${name || "This client"} already has an unfinished assessment (${bits.join(", ")}).`;
}

/**
 * Opens the checklist for a client or a lead (backend app/livewell/assessment_start.py).
 * An unfinished assessment is offered first: "Continue the draft" is the default,
 * "Start a new one" is the deliberate choice — never a silent second assessment.
 */
export function NewAssessment({
  who,
  name,
  from,
  draft,
  label = "Start assessment",
  className = "",
  disabled = false,
}: {
  who: AssessmentFor | null;
  name: string;
  from: "assessments" | "leads";
  /** Already known (from the picker list); undefined = ask the server on click. */
  draft?: AssessmentDraft | null;
  label?: string;
  className?: string;
  disabled?: boolean;
}) {
  const router = useRouter();
  const [asking, setAsking] = useState<AssessmentDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function open(fresh: boolean) {
    if (!who) return;
    setBusy(true);
    setError("");
    try {
      const res = await startAssessment(who, fresh);
      router.push(`/caregiver/assess/${res.job_id}?from=${from}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the assessment");
      setBusy(false);
    }
  }

  async function click() {
    if (!who) return;
    setError("");
    let d = draft;
    if (d === undefined) {
      setBusy(true);
      try {
        d = (await assessmentDraft(who)).draft;
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not check for a draft");
        setBusy(false);
        return;
      }
      setBusy(false);
    }
    if (d) setAsking(d);
    else void open(false);
  }

  return (
    <span className="sa na-start">
      {!asking ? (
        <button type="button" className={className} disabled={busy || disabled || !who} onClick={() => void click()}>
          {busy ? "Opening…" : label}
        </button>
      ) : (
        <span className="sa-ask" role="alert">
          <span>{draftText(name, asking)}</span>
          <button type="button" className={className} disabled={busy} autoFocus onClick={() => void open(false)}>
            {busy ? "Opening…" : "Continue the draft"}
          </button>
          <button type="button" className="secondary" disabled={busy} onClick={() => void open(true)}>
            Start a new one
          </button>
          <button type="button" className="secondary" disabled={busy} onClick={() => setAsking(null)}>
            Cancel
          </button>
        </span>
      )}
      {error ? <small className="error-text">{error}</small> : null}
    </span>
  );
}
