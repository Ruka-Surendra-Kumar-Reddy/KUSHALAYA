import { persistDraftWithSync } from "./assessmentSync";
import { createEmptyAssessment, type HomeSafetyAssessment } from "./assessment";

const pendingKey = (id: string) => `home_safety_pending_${id}`;

export type StartAssessmentPrefill = {
  elderId?: number | null;
  prospectId?: number | null;
  clientFirstName?: string;
  clientLastName?: string;
  clientAddress?: string;
  clientPhone?: string;
  clientEmail?: string;
};

/** Create a draft assessment and return its id for navigation. */
export function startNewAssessment(prefill?: StartAssessmentPrefill): string {
  let assessment: HomeSafetyAssessment = createEmptyAssessment();
  if (prefill) {
    assessment = {
      ...assessment,
      elderId: prefill.elderId ?? null,
      prospectId: prefill.prospectId ?? null,
      clientFirstName: prefill.clientFirstName ?? "",
      clientLastName: prefill.clientLastName ?? "",
      clientAddress: prefill.clientAddress ?? "",
      clientPhone: prefill.clientPhone ?? "",
      clientEmail: prefill.clientEmail ?? "",
    };
  }
  try {
    sessionStorage.setItem(pendingKey(assessment.id), JSON.stringify(assessment));
  } catch {
    /* sessionStorage optional */
  }
  persistDraftWithSync(assessment);
  return assessment.id;
}

/** Hydrate a just-created assessment if localStorage read races navigation. */
export function hydratePendingAssessment(id: string): ReturnType<typeof persistDraftWithSync> | null {
  try {
    const raw = sessionStorage.getItem(pendingKey(id));
    if (!raw) return null;
    const assessment = JSON.parse(raw) as ReturnType<typeof createEmptyAssessment>;
    if (assessment.id !== id) return null;
    sessionStorage.removeItem(pendingKey(id));
    return persistDraftWithSync(assessment);
  } catch {
    return null;
  }
}
