"use client";

import { useParams } from "next/navigation";
import { OpenAssessment } from "@/components/ops/OpenAssessment";

/** Old wizard address: completed → report, unfinished → the 3-step checklist. */
export default function HomeSafetyAssessmentPage() {
  const id = String(useParams().id);
  return (
    <OpenAssessment
      id={id}
      reportHref={`/kushalaya/assess/${encodeURIComponent(id)}/report`}
      listHref="/kushalaya/assessments"
    />
  );
}
