/** KushLife: the four checks on every visit. Mirrors backend/app/livewell/kushlife.py. */

export type CheckKey = "safe" | "steady" | "settled" | "connected";
export type CheckState = { status: "ok" | "concern" | null; chips: string[]; note: string };
export type KushLifeCapture = {
  checks: Record<CheckKey, CheckState>;
  sleep: "well" | "poorly" | "unsure" | null;
  appetite: "usual" | "less" | "more" | null;
  vitals: { bp_sys?: string; bp_dia?: string; spo2?: string; pulse?: string; sugar?: string };
};

export const KL_CHECKS: { key: CheckKey; label: string; hint: string }[] = [
  { key: "safe", label: "Safe", hint: "Home and person safe today" },
  { key: "steady", label: "Steady", hint: "Moving as usual, no falls" },
  { key: "settled", label: "Settled", hint: "Mood, eating, sleep as usual" },
  { key: "connected", label: "Connected", hint: "In touch with people, anything for the family" },
];

export const KL_CHIPS: Record<CheckKey, { key: string; label: string }[]> = {
  safe: [
    { key: "new_hazard", label: "New hazard at home" },
    { key: "meds_missed", label: "Medicines missed" },
    { key: "meds_unsure", label: "Not sure medicines were taken" },
    { key: "stove_gas", label: "Stove / gas left on" },
    { key: "doors_locks", label: "Doors or locks unsafe" },
    { key: "poor_lighting", label: "Poor lighting" },
    { key: "footwear", label: "Unsafe footwear" },
  ],
  steady: [
    { key: "fall", label: "Had a fall" },
    { key: "near_fall", label: "Nearly fell" },
    { key: "unsteady", label: "Unsteady walking" },
    { key: "fear_of_falling", label: "Afraid of falling" },
    { key: "aid_not_used", label: "Walking aid not used" },
  ],
  settled: [
    { key: "ate_less", label: "Ate less" },
    { key: "drank_less", label: "Drank less" },
    { key: "poor_sleep", label: "Slept poorly" },
    { key: "low_mood", label: "Low mood" },
    { key: "confused", label: "More confused than usual" },
    { key: "pain", label: "In pain" },
    { key: "continence", label: "Continence change" },
    { key: "skin", label: "Skin or wound concern" },
    { key: "breathing", label: "Breathing different" },
  ],
  connected: [
    { key: "lonely", label: "Seemed lonely" },
    { key: "no_visitors", label: "No visitors or calls" },
    { key: "message_family", label: "Has a message for family" },
  ],
};

/** Chips that make a visit red straight away (the care manager calls the family within 2 hours). */
export const KL_RED_CHIPS = new Set(["fall", "confused", "breathing"]);

export function emptyCapture(): KushLifeCapture {
  const blank = (): CheckState => ({ status: null, chips: [], note: "" });
  return {
    checks: { safe: blank(), steady: blank(), settled: blank(), connected: blank() },
    sleep: null,
    appetite: null,
    vitals: {},
  };
}

/** What's still unanswered: every check plus sleep and appetite are required. */
export function missingAnswers(c: KushLifeCapture): string[] {
  const out = KL_CHECKS.filter((k) => !c.checks[k.key].status).map((k) => k.label);
  if (!c.sleep) out.push("Sleep");
  if (!c.appetite) out.push("Appetite");
  return out;
}

export function toPayload(c: KushLifeCapture) {
  const num = (v?: string) => (v && v.trim() ? Number(v) : undefined);
  return {
    checks: Object.fromEntries(
      KL_CHECKS.map((k) => [k.key, { status: c.checks[k.key].status, chips: c.checks[k.key].chips, note: c.checks[k.key].note }]),
    ),
    sleep: c.sleep,
    appetite: c.appetite,
    vitals: { bp_sys: num(c.vitals.bp_sys), bp_dia: num(c.vitals.bp_dia), spo2: num(c.vitals.spo2), pulse: num(c.vitals.pulse), sugar: num(c.vitals.sugar) },
  };
}

export type KushLifeVisit = {
  job_id: number;
  date: string | null;
  title: string;
  checks: Record<CheckKey, "ok" | "concern">;
  chips: Record<CheckKey, string[]>;
  sleep: string | null;
  appetite: string | null;
  vitals: Record<string, number>;
  note: string;
  level: "ok" | "amber" | "red";
  reasons: string[];
  photo_count: number;
};

export type KushLifeFlag = {
  key: string;
  level: "amber" | "red";
  check: CheckKey | null;
  reason: string;
  job_id: number;
  date: string | null;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
};

export type KushLifeView = {
  checks: { key: CheckKey; label: string; hint: string }[];
  visits: KushLifeVisit[];
  streaks: Record<CheckKey, number>;
  pct_ok_30d: number | null;
  flags: KushLifeFlag[];
  status: string;
  summary_line: string;
  explain: string;
  baseline?: KushLifeBaseline;
  latest_vitals?: ({ date: string | null } & Record<string, number | string | null>) | null;
};

/** "Normal for Amma": the client's own baseline (staff override per item, else from the last visits). */
export type BaselineKey = "bp_sys" | "bp_dia" | "spo2" | "pulse" | "sleep" | "appetite" | "mood";
export type KushLifeBaseline = {
  values: Partial<Record<BaselineKey, number | string | null>>;
  computed: Partial<Record<BaselineKey, number | string | null>>;
  source: Partial<Record<BaselineKey, "override" | "visits" | null>>;
  visits_used: number;
  override_by: string | null;
  override_at: string | null;
  label: string;
};

/**
 * "Normal for Amma: BP 130/85 · Oxygen 96% · Pulse 72" — empty when there is no baseline yet.
 * With `measured` (a visit's readings) it lists only the items taken at that visit.
 */
export function normalLine(b?: KushLifeBaseline | null, measured?: Record<string, unknown>): string {
  if (!b) return "";
  const v = b.values;
  const took = (k: string) => !measured || measured[k] != null;
  const parts = [
    v.bp_sys && v.bp_dia && took("bp_sys") ? `BP ${v.bp_sys}/${v.bp_dia}` : "",
    v.spo2 && took("spo2") ? `Oxygen ${v.spo2}%` : "",
    v.pulse && took("pulse") ? `Pulse ${v.pulse}` : "",
  ].filter(Boolean);
  return parts.length ? `${b.label}: ${parts.join(" · ")}` : "";
}

/** The Monday card: last full week (IST) vs the week before. */
export type WeekShare = { good: number; answered: number; prev_good: number; prev_answered: number; trend: "better" | "same" | "worse" | null };
export type KushLifeWeekCard = {
  name: string;
  week_start: string;
  week_end: string;
  visits_done: number;
  visits_prev: number;
  trend: { mood: WeekShare; sleep: WeekShare; appetite: WeekShare };
  vitals: Partial<Record<"bp_sys" | "bp_dia" | "spo2" | "pulse", number | null>>;
  vitals_prev: Partial<Record<"bp_sys" | "bp_dia" | "spo2" | "pulse", number | null>>;
  baseline: Partial<Record<"bp_sys" | "bp_dia" | "spo2" | "pulse", number | null>>;
  flags: { raised: number; closed: number };
  next_visits: { date: string; title: string }[];
};
export type KushLifeWeekly = {
  id: number;
  elder_id: number;
  week_start: string;
  status: "draft" | "approved";
  text: string;
  draft_text: string;
  approved_at: string | null;
  overdue: boolean;
};

/**
 * KushLife lifeline score for one visit — 50 is their usual (all four checks as usual).
 * Built only from what the caregiver recorded: each changed check pulls it down, an amber or
 * red visit pulls it further, and good sleep / usual appetite lift it a little. Not medical.
 */
export function lifelineScore(v: Pick<KushLifeVisit, "checks" | "level" | "sleep" | "appetite">): number {
  let s = 50;
  for (const c of Object.values(v.checks)) if (c === "concern") s -= 7;
  if (v.level === "red") s -= 8;
  else if (v.level === "amber") s -= 3;
  if (v.sleep === "well") s += 2;
  else if (v.sleep === "poorly") s -= 3;
  if (v.appetite === "usual") s += 2;
  else if (v.appetite === "less") s -= 3;
  return Math.max(5, Math.min(60, s));
}

/** Plain word for a lifeline score. */
export function lifelineWord(score: number): "Doing well" | "As usual" | "Watch" | "Needs care" {
  return score > 52 ? "Doing well" : score >= 48 ? "As usual" : score >= 40 ? "Watch" : "Needs care";
}
