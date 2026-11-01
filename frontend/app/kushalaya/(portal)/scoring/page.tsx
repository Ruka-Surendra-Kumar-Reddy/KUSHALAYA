"use client";

import Link from "next/link";
import { canOpen } from "@/lib/roles";
import { HomeSafetyShell } from "@/components/livewell/HomeSafetyShell";
import { ScoringGuide } from "@/components/livewell/ScoringGuide";
import { AssessorItemTrainingGuide } from "@/components/livewell/AssessorItemTrainingGuide";
import { useSafetyRubric } from "@/lib/livewell/useSafetyRubric";

export default function HomeSafetyScoringPage() {
  const categories = useSafetyRubric();

  return (
    <HomeSafetyShell
      title="Scoring & training"
      subtitle="How to score — and what to look for on every checklist item"
      backHref="/kushalaya"
      showNav={false}
    >
      <ScoringGuide categories={categories} defaultOpen />
      <div style={{ marginTop: "1rem" }}>
        <AssessorItemTrainingGuide categories={categories} defaultOpen />
      </div>
      {canOpen("/kushalaya/rubric") ? (
        <p className="muted" style={{ marginTop: "1rem", fontSize: "0.9rem" }}>
          <Link href="/kushalaya/rubric">Edit checklist items</Link>
        </p>
      ) : null}
    </HomeSafetyShell>
  );
}
