"use client";

import { useParams } from "next/navigation";
import { AssessmentReportLoader } from "@/components/livewell/AssessmentReportLoader";

/** Ops portal — read-only, printable assessment report. */
export default function OpsAssessmentReportPage() {
  const params = useParams();
  const id = String(params.id);
  return <AssessmentReportLoader id={id} listHref="/kushalaya/assessments" />;
}
