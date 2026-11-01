"use client";

import { useParams } from "next/navigation";
import { OpenAssessment } from "@/components/ops/OpenAssessment";

export default function OpsAssessmentDetailPage() {
  const id = String(useParams().id);
  return (
    <OpenAssessment
      id={id}
      reportHref={`/kushalaya/assessments/${encodeURIComponent(id)}/report`}
      listHref="/kushalaya/assessments"
    />
  );
}
