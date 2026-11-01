import { redirect } from "next/navigation";

/** The old one-page wizard is gone: new assessments start from Assessments (3-step checklist). */
export default function NewHomeSafetyAssessmentPage() {
  redirect("/kushalaya/assessments");
}
