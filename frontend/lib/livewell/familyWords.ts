/**
 * Plain words for families. Clinical and internal terms from the rubric, plan
 * and service catalogue are swapped here, in one place, before they are shown.
 */

const PLAIN_TERMS: [RegExp, string][] = [
  // Area names: one plain name, never "Activities of Daily Living (daily activities)".
  [/\binstrumental activities of daily living\b(?:\s*\((?:I?ADLs?|household tasks)\))?/gi, "household tasks"],
  [/\bactivities of daily living\b(?:\s*\((?:ADLs?|daily activities)\))?/gi, "daily self-care"],
  [/\bhousehold tasks\s*\((?:I?ADLs?|household tasks)\)/gi, "household tasks"],
  [/\bmedication non-adherence\b/gi, "missed medicines"],
  [/\bunsafe toilet transfers?\b/gi, "getting on and off the toilet safely"],
  [/\btoilet transfer safety\b/gi, "getting on and off the toilet safely"],
  [/\bunsafe bed transfers?\b/gi, "getting in and out of bed safely"],
  [/\bbed transfer safety\b/gi, "getting in and out of bed safely"],
  [/\bsafer ambulation\b/gi, "safer walking"],
  [/\bambulation\b/gi, "walking"],
  [/\binstrumental ADLs\b/gi, "household tasks"],
  [/\bIADLs?\b/g, "household tasks"],
  [/\bADLs?\b/g, "daily activities"],
  [/\ban (?:elder ?care|eldercare\/care) manager \(ECM\)/gi, "a care manager"],
  [/\b(?:elder ?care|eldercare\/care) manager \(ECM\)/gi, "care manager"],
  [/\bECM\b/g, "care manager"],
  [/\bOT\b/g, "occupational therapist"],
  [/\bgait assessment\b/gi, "walking check"],
  [/\bunsteady gait\b/gi, "unsteady walking"],
  [/\bgait\b/gi, "walking"],
  // Plan titles and steps from the solution library, in plain words (the
  // finding titles match "What we found" where the two name the same thing).
  [/\bunsafe shower entry\b/gi, "shower hard to step into"],
  [/\bunstable bathing position\b/gi, "no seat for bathing"],
  [/\bno accessible main entry\b/gi, "steps at the front door"],
  [/\bno entrance handrail\b/gi, "no railing at the entrance"],
  [/\bkitchen burn \/ fire hazard\b/gi, "risk of burns or fire in the kitchen"],
  [/\bmissing smoke or CO detectors\b/gi, "no smoke or gas alarm on each floor"],
  [/\buneven walkway\b/gi, "uneven or cluttered pathway"],
  [/\bloose rugs \/ trip hazards in living areas\b/gi, "loose rugs and trip hazards"],
  [/\belectrical hazards\b/gi, "unsafe sockets or wiring"],
  [/\bthreshold reduction\b/gi, "lower the raised step"],
  [/\btransfer pole\b/gi, "floor-to-ceiling grab pole"],
  [/\bpharmacist review for sedating meds\b/gi, "ask a pharmacist to check medicines that cause drowsiness"],
];

/** "≤120°F" -> "≤49°C": families in India read Celsius. */
function toCelsius(text: string): string {
  return text.replace(/(\d{2,3}(?:\.\d+)?)\s*°\s*F\b/g, (_all, f: string) => `${Math.round(((Number(f) - 32) * 5) / 9)}°C`);
}

/** "≤49°C / 49°C" (a converted value beside its own Celsius) -> "≤49°C". */
function withoutEchoTemp(text: string): string {
  return text.replace(/(≤\s*)?(\d{2,3})°C\s*\/\s*≤?\s*\2°C/g, (_all, le: string | undefined, c: string) => `${le ?? ""}${c}°C`);
}

/** "Household tasks (household tasks)" -> "Household tasks". */
function withoutEchoGloss(text: string): string {
  return text.replace(/\b([A-Za-z][\w -]{2,40}?)\s*\(\s*\1\s*\)/gi, "$1");
}

/** "Medication non-adherence" -> "Missed medicines"; keeps a leading capital. */
export function plainWords(text: string | null | undefined): string {
  let out = text || "";
  if (!out) return out;
  const capital = /^[A-Z]/.test(out);
  for (const [re, plain] of PLAIN_TERMS) out = out.replace(re, plain);
  out = withoutEchoGloss(withoutEchoTemp(toCelsius(out)));
  return capital ? out.charAt(0).toUpperCase() + out.slice(1) : out;
}

/**
 * Photo captions without internal ids: "Home safety photo (hsa-1784…-l3qdo0e)" -> fallback,
 * "Bathroom (hsa-…)" -> "Bathroom".
 */
export function photoCaption(caption: string | null | undefined, fallback = "Room photo"): string {
  const t = (caption || "")
    .replace(/\s*\((?:hs[a-z]?|wr|ph|img|photo)[-_][^)]*\)\s*/gi, " ")
    .replace(/\b(?:hs[a-z]?|wr)[-_][a-z0-9-]{6,}\b/gi, "")
    .replace(/\s{2,}/g, " ")
    .trim();
  if (!t || /^home safety photo$/i.test(t)) return fallback;
  return plainWords(t);
}

/** Drops internal "Context: …" lines from staff notes before a family sees them. */
export function withoutContextLines(text: string | null | undefined): string {
  return (text || "")
    .split(/\r?\n/)
    .filter((line) => !/^\s*context\s*:/i.test(line))
    .join("\n")
    .replace(/(?:^|\s*[.·|]\s*)context\s*:\s*[^.\n|·]*/gi, "")
    .trim();
}
