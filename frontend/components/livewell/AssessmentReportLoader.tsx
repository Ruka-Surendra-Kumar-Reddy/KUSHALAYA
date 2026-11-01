"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AssessmentReportView } from "@/components/livewell/AssessmentReportView";
import type { HomeSafetyAssessment } from "@/lib/livewell/assessment";
import { normalizeAssessment } from "@/lib/livewell/assessment";
import { loadAssessmentMerged } from "@/lib/livewell/assessmentSync";
import { getAssessment } from "@/lib/livewell/storage";

/** Loads an assessment (local + server merge) and renders the read-only report. */
export function AssessmentReportLoader({
  id,
  listHref,
}: {
  id: string;
  /** Where "← Assessments" goes (the old wizard page is gone, so no "back to assessment"). */
  listHref: string;
}) {
  const [draft, setDraft] = useState<HomeSafetyAssessment | null>(null);
  const [missing, setMissing] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      let found = getAssessment(id);
      const merged = await loadAssessmentMerged(id);
      if (merged) found = merged;
      if (cancelled) return;
      if (!found) {
        setMissing(true);
        setDraft(null);
      } else {
        setMissing(false);
        setDraft(normalizeAssessment(found));
      }
      setLoading(false);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading) return <p className="muted">Loading report…</p>;

  if (missing || !draft) {
    return (
      <div className="card">
        <h1 style={{ marginTop: 0 }}>Assessment not found</h1>
        <p className="muted">It may still be syncing, or it was deleted.</p>
        <p>
          <Link href={listHref}>Back to assessments</Link>
        </p>
      </div>
    );
  }

  return <AssessmentReportView assessment={draft} backHref={listHref} />;
}
