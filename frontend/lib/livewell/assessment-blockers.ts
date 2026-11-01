/**
 * What stops the field checklist (app/caregiver/assess/[id]/page.tsx) from being
 * submitted, worked out in one place so the screen can say exactly what is left
 * and jump to it. Saving a draft is never blocked.
 */

export type ChecklistQuestion = { id: string; label: string; input: string; cat: string };
export type ChecklistStep = { kind: string; cat?: string; items?: ChecklistQuestion[] };
export type Unanswered = { id: string; label: string; cat: string; step: number };

export function isAnswered(
  q: Pick<ChecklistQuestion, "id" | "input">,
  ratings: Record<string, string>,
  notes: Record<string, string>,
): boolean {
  return Boolean(ratings[q.id] || (q.input === "text" && (notes[q.id] || "").trim()));
}

/** Unanswered questions in screen order, each with the step (screen) it is on. */
export function unansweredQuestions(
  steps: ChecklistStep[],
  ratings: Record<string, string>,
  notes: Record<string, string>,
): Unanswered[] {
  const out: Unanswered[] = [];
  steps.forEach((s, step) => {
    for (const q of s.items ?? []) {
      if (!isAnswered(q, ratings, notes)) out.push({ id: q.id, label: q.label, cat: q.cat, step });
    }
  });
  return out;
}

export function unansweredTitle(n: number): string {
  return `${n} question${n === 1 ? "" : "s"} not answered yet`;
}

/** Sections with unanswered questions: "Bathroom (2), Kitchen (1)". */
export function unansweredBySection(list: Unanswered[]): { cat: string; step: number; count: number }[] {
  const out: { cat: string; step: number; count: number }[] = [];
  for (const u of list) {
    const last = out[out.length - 1];
    if (last && last.step === u.step) last.count += 1;
    else out.push({ cat: u.cat, step: u.step, count: 1 });
  }
  return out;
}
