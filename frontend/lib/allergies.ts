/**
 * One rule for allergy wording everywhere: nothing on file is "Not recorded";
 * only a confirmed none ("none", "NKA", "no known allergies") reads "No known allergies".
 */
export type AllergyState = { kind: "none-recorded" | "none-known" | "listed"; text: string };

const NONE = /^(none|nil|nka|nkda|no|no known( drug)? allergies?|no allergies)\.?$/i;

export function allergyState(value: string | null | undefined): AllergyState {
  const v = (value || "").trim();
  if (!v) return { kind: "none-recorded", text: "Not recorded" };
  if (NONE.test(v)) return { kind: "none-known", text: "No known allergies" };
  return { kind: "listed", text: v };
}
