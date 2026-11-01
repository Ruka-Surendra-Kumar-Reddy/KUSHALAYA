/**
 * Answer options for a question: what the caregiver taps, and which rating each saves.
 * Admins can set them per question in the rubric editor; otherwise they come from the
 * caregiver wording (caregiver-answers.ts), then from the old help text, then generic.
 * Used by the editor, the caregiver form and the report. Scoring is unchanged.
 */
import type { OptionRating, QuestionOption } from "./assessment";
import { caregiverAnswers } from "./caregiver-answers";

export type { OptionRating, QuestionOption };

export const OPTION_RATINGS: OptionRating[] = ["excellent", "acceptable", "unsafe", "na"];
export const MAX_OPTIONS = 8;
export const MAX_OPTION_LABEL = 100;
export const MAX_ASK = 200;
/** A help line becomes a button only when it is this short; longer = generic word. */
export const MAX_HELP_OPTION = 60;

/** What each rating means, in plain words (the "Means" select and the chips). */
export const RATING_MEANS: Record<OptionRating, string> = {
  excellent: "Safe",
  acceptable: "Needs attention",
  unsafe: "Risk",
  na: "Doesn't apply",
};

type ItemLike = {
  id: string;
  label?: string;
  help?: string;
  ask?: string;
  options?: QuestionOption[] | null;
};

const GENERIC: QuestionOption[] = OPTION_RATINGS.map((rating) => ({ label: RATING_MEANS[rating], rating }));

/** Trim, drop empty or unknown, cap at 8 (same rules as the backend). */
export function cleanOptions(list: unknown): QuestionOption[] {
  if (!Array.isArray(list)) return [];
  const out: QuestionOption[] = [];
  for (const o of list) {
    if (!o || typeof o !== "object") continue;
    const label = String((o as { label?: unknown }).label ?? "").trim().slice(0, MAX_OPTION_LABEL).trim();
    const rating = String((o as { rating?: unknown }).rating ?? "").trim().toLowerCase() as OptionRating;
    if (label && OPTION_RATINGS.includes(rating)) out.push({ label, rating });
    if (out.length >= MAX_OPTIONS) break;
  }
  return out;
}

const HELP_LINES: [RegExp, OptionRating][] = [
  [/^\s*★\s*excellent\s*:\s*(.+)$/i, "excellent"],
  [/^\s*~\s*acceptable\s*:\s*(.+)$/i, "acceptable"],
  [/^\s*✕\s*unsafe\s*:\s*(.+)$/i, "unsafe"],
  [/^\s*—\s*n\/a\s*:\s*(.+)$/i, "na"],
];

/** Options read from old help text lines ("★ Excellent: …"). Empty when none found. */
export function optionsFromHelp(help: string | undefined): QuestionOption[] {
  const out: QuestionOption[] = [];
  for (const line of (help || "").split(/\r?\n/)) {
    for (const [re, rating] of HELP_LINES) {
      const m = line.match(re);
      const text = m ? m[1].trim() : "";
      // Long assessor sentences are not buttons: over 60 characters → the plain word.
      if (text) out.push({ label: text.length <= MAX_HELP_OPTION ? text : RATING_MEANS[rating], rating });
    }
  }
  return out;
}

/** The standard options for a question (what "Reset to standard" restores). */
export function standardOptions(item: ItemLike): QuestionOption[] {
  const words = caregiverAnswers(item.id);
  if (words) {
    const out: QuestionOption[] = [
      { label: words.excellent, rating: "excellent" },
      { label: words.acceptable, rating: "acceptable" },
      { label: words.unsafe, rating: "unsafe" },
    ];
    if (words.na) out.push({ label: words.na, rating: "na" });
    return out;
  }
  const fromHelp = optionsFromHelp(item.help);
  return fromHelp.length ? fromHelp : GENERIC.map((o) => ({ ...o }));
}

/** True when the admin set the options for this question. */
export function hasCustomOptions(item: ItemLike): boolean {
  return cleanOptions(item.options).length > 0;
}

/** The options the caregiver sees: custom when set, else standard. */
export function questionOptions(item: ItemLike): QuestionOption[] {
  const custom = cleanOptions(item.options);
  return custom.length ? custom : standardOptions(item);
}

/** The question as asked in the home. */
export function standardAsk(item: ItemLike): string {
  return caregiverAnswers(item.id)?.ask || item.label || "";
}

export function questionAsk(item: ItemLike): string {
  return item.ask?.trim() || standardAsk(item);
}

/** Answer wording for a saved rating: the tapped label, else the first option with that rating. */
export function answerLabel(item: ItemLike, rating: string | null | undefined, chosen?: string): string | undefined {
  if (chosen?.trim()) return chosen.trim();
  if (!rating) return undefined;
  return questionOptions(item).find((o) => o.rating === rating)?.label;
}

/**
 * Splits help text into the short "Look for" sentence and the rest (the full assessor guide).
 * Help without a "Look for:" line is treated as all "look for" when it is one line.
 */
export function splitHelp(help: string | undefined): { lookFor: string; rest: string } {
  const lines = (help || "").split(/\r?\n/);
  const idx = lines.findIndex((l) => /^\s*look\s+for\s*:/i.test(l));
  if (idx >= 0) {
    const lookFor = lines[idx].replace(/^\s*look\s+for\s*:\s*/i, "").trim();
    const rest = lines.filter((_, i) => i !== idx).join("\n").trim();
    return { lookFor, rest };
  }
  const text = (help || "").trim();
  if (text && !text.includes("\n")) return { lookFor: text, rest: "" };
  return { lookFor: "", rest: text };
}

export function joinHelp(lookFor: string, rest: string): string {
  const head = lookFor.trim() ? `Look for: ${lookFor.trim()}` : "";
  return [head, rest.trim()].filter(Boolean).join("\n");
}
