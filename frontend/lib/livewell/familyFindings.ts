/**
 * Family wording for assessment findings and score summaries.
 *
 * Rubric labels name the safe state ("Toilet grab bar installed"), so shown
 * bare a finding reads as already done. Say the problem (and the fix) instead.
 */

const SAFE_STATE_RE = /^(.*?)\s+(installed|fitted|present|available|in place)$/i;

/**
 * Explicit problem wording for checklist labels that don't follow the
 * "<thing> installed" pattern. Keys are lower-case rubric labels; add a row
 * here when a new label reads wrong to families.
 */
export const FINDING_WORDS: Record<string, string> = {
  "anti-slip flooring": "Slippery floors",
  "slip-resistant floor": "Slippery floors",
  "slip resistance": "Slippery floors",
  "floor dry": "Wet floors",
  "pathway level and clear": "Uneven or cluttered pathway",
  "clear pathway": "Cluttered pathway",
  "walkway clear": "Cluttered walkway",
  "living area walkways clear": "Cluttered walkways in the living area",
  "hallways free of trip hazards": "Trip hazards in the hallways",
  "trip hazards removed": "Trip hazards",
  "wheelchair or walker path clear": "No clear path for the walker or wheelchair",
  "loose rugs secured or removed": "Loose rugs",
  "loose rugs removed": "Loose rugs",
  "emergency contacts posted": "No emergency contacts posted",
  "emergency contacts displayed": "No emergency contacts posted",
  "bedroom night lighting": "No bedroom night light",
  "night light": "No night light",
  "night lamp": "No night lamp",
  "adequate entry lighting": "Entrance too dark",
  "adequate lighting": "Too dark",
  "lighting adequate": "Too dark",
  "light switches easy to reach and operate": "Light switches hard to reach",
  "toilet height appropriate": "Toilet too low or too high",
  "chair height appropriate": "Chair too low or too high",
  "bed height": "Bed too low or too high",
  "shower threshold safe": "Unsafe shower step",
  "door widths / thresholds accessible": "Narrow doors or raised thresholds",
  "zero-step or ramped main entry": "Steps at the main entrance",
  "entrance railing if needed": "No railing at the entrance",
  "stairs manageable or alternative exists": "Stairs are hard to manage",
  "smoke and co detectors on each level": "No smoke or gas alarm on each floor",
  "hot water scald risk controlled": "Hot water can scald",
  "water temperature safe": "Hot water can scald",
  "electrical outlets/wiring safe": "Unsafe sockets or wiring",
  "stove / gas safety controls": "Stove or gas not safe",
  "sos / alert method available": "No way to call for help",
  "can use phone for emergencies": "Can't use the phone in an emergency",
  "first aid / flashlight accessible": "No first-aid kit or torch to hand",
  "evacuation path understood": "No clear way out in an emergency",
  "family response plan documented": "No family emergency plan",
  "bathroom well ventilated": "Bathroom poorly ventilated",
  "damp / mold controlled": "Damp or mould",
  "no major structural hazards": "Structural hazards in the home",
  "home secure (locks, visitor check)": "Home not secure",
  "steady when walking": "Unsteady when walking",
  "balance adequate for home": "Poor balance",
  "transfers bed/chair safely": "Unsafe getting in and out of bed or chairs",
  "bed transfer support": "Hard to get in and out of bed",
  "stands from chair without arm push": "Needs arms to stand from a chair",
  "no falls in the past year": "Had a fall in the past year",
  "not worried about falling": "Worried about falling",
};

const PROBLEM_WORDS = new Set(Object.values(FINDING_WORDS));

function mappedWords(label: string): string | null {
  return FINDING_WORDS[label.trim().toLowerCase()] ?? null;
}

function lowerFirst(s: string): string {
  // Keep acronyms ("SOS button") as they are.
  return /^[A-Z]{2,}/.test(s) ? s : s.charAt(0).toLowerCase() + s.slice(1);
}

/**
 * "Toilet grab bar installed" -> "No toilet grab bar". One style everywhere
 * (the "— fit one" tail only ever showed on some items).
 */
export function findingProblem(label: string): string {
  return findingNeed(label);
}

/** Short chip / heading form: "Toilet grab bar installed" -> "No toilet grab bar". */
export function findingNeed(label: string): string {
  const t = (label || "").trim();
  const mapped = mappedWords(t);
  if (mapped) return mapped;
  const m = t.match(SAFE_STATE_RE);
  if (m) return `No ${lowerFirst(m[1])}`;
  return t ? `${t} — needs fixing` : t;
}

export type FocusArea = { name: string; score: number };

/** "1. Home Safety" -> "Home safety" (no section number, sentence case, acronyms kept). */
export function plainAreaName(title: string): string {
  const t = (title || "").replace(/^\s*\d+[.)]\s*/, "").replace(/_/g, " ").trim();
  const out = t
    .split(/\s+/)
    .map((w, i) => (i === 0 || /^[A-Z0-9&]{2,}$/.test(w) ? w : w.toLowerCase()))
    .join(" ");
  return out.charAt(0).toUpperCase() + out.slice(1);
}

// The list ends at the first "<name> <score>" followed by "." or end of text
// (section numbers follow ": " or ", ", so "1. Home Safety" does not end it).
const AREAS_RE = /(?:Areas to focus on|Focus domains):\s*([^\n]*?[A-Za-z)&]\s\d{1,3})\s*(?:\.|$)/im;

/**
 * Lowest areas (up to `limit`) for chips: from domain scores when the API sends
 * them, else parsed from the stored summary sentence.
 */
export function focusAreas(
  summary: string | null | undefined,
  domains?: { title: string; score: number }[] | null,
  limit = 3,
): FocusArea[] {
  if (domains && domains.length) {
    return [...domains]
      .filter((d) => d && d.title && Number.isFinite(d.score))
      .sort((a, b) => a.score - b.score)
      .slice(0, limit)
      .map((d) => ({ name: plainAreaName(d.title), score: Math.round(d.score) }));
  }
  const m = (summary || "").match(AREAS_RE);
  if (!m) return [];
  const out: FocusArea[] = [];
  for (const part of m[1].split(/,\s*/)) {
    const p = part.trim().match(/^(.*?)\s+(\d+)$/);
    if (p) out.push({ name: plainAreaName(p[1]), score: Number(p[2]) });
  }
  return out.sort((a, b) => a.score - b.score).slice(0, limit);
}

/** Summary text without the "Areas to focus on: …" sentence (shown as chips instead). */
export function summaryWithoutAreas(summary: string | null | undefined): string {
  return (summary || "").replace(AREAS_RE, "").replace(/[ \t]{2,}/g, " ").trim();
}

/**
 * Older "Urgent safety fixes found" notices list bare rubric labels as "- label"
 * lines; reword each so it never reads as already done.
 */
export function rewordFindingLines(body: string): string {
  return body.replace(/^([-•]\s+)(.+)$/gm, (all, dash: string, label: string) =>
    /^and \d+ more$/i.test(label.trim()) || /—/.test(label) || PROBLEM_WORDS.has(label.trim())
      ? `${dash}${label.replace(FIT_TAIL_RE, "")}`
      : `${dash}${findingProblem(label)}`,
  );
}

/** Older notices said "No toilet grab bar — fit one"; the tail is dropped everywhere now. */
const FIT_TAIL_RE = /\s+—\s+fit (?:one|them)\s*$/i;

export type CriticalFinding = { id?: string; label: string; area?: string; category?: string };

/**
 * The one "urgent" list: the assessment's critical findings (a critical item
 * rated Risk). The /safety hero ("Fix first"), "What we found", the "Why this
 * score?" sheet, /plan and Home's "N critical" all read this list, so they
 * name the same things. Problem words, no duplicates, in assessment order.
 */
export function urgentFindings(critical: CriticalFinding[] | null | undefined): string[] {
  const out: string[] = [];
  for (const c of critical ?? []) {
    const words = findingNeed(c?.label || "");
    if (words && !out.includes(words)) out.push(words);
  }
  return out;
}

/**
 * "… Top priorities: Unsafe shower entry; Grab bar; Loose rugs. …" -> the first
 * `limit` priorities as a list, so the card never cuts a sentence mid-word.
 */
export function topPriorities(summary: string | null | undefined, limit = 3): string[] {
  const m = (summary || "").match(/Top priorities:\s*([^\n]*?)\.(?:\s|$)/i);
  if (!m) return [];
  return m[1]
    .split(/;\s*/)
    .map((p) => p.trim())
    .filter(Boolean)
    .slice(0, limit)
    // Priorities are usually already problems ("Unsafe shower entry"): only reword safe-state labels.
    .map(planTitle);
}

/**
 * A plan or priority title in problem words: rubric labels ("Pathway level and
 * clear") are reworded, plan titles that already name a problem are kept.
 */
export function planTitle(title: string): string {
  const t = (title || "").trim();
  return mappedWords(t) || SAFE_STATE_RE.test(t) ? findingNeed(t) : t;
}
