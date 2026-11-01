"use client";

import { useParams } from "next/navigation";
import { AssessmentReportLoader } from "@/components/livewell/AssessmentReportLoader";

/** Assessor app — read-only, printable assessment report. */
export default function AssessorReportPage() {
  const params = useParams();
  const id = String(params.id);
  return (
    <main className="home-safety-app home-safety-report-page">
      <AssessmentReportLoader id={id} listHref="/kushalaya" />
    </main>
  );
}
