/**
 * LiveWell360 Assessment (KAA) v2.0 — twelve domains.
 * @see docs/livewell360/KAA_SPEC.md
 */
import { withPublicBrand } from "@/lib/public-brand";
import type { AssessmentCategory, AssessmentItem, SkipRule } from "./assessment";
import { RULE } from "./conditional-rules";
import type { RubricItemSource } from "./rubric-sources";

export const LWA_VERSION = "2.1";
export const LWA_TITLE = withPublicBrand("LiveWell360 Assessment (KAA)");
/** @deprecated Use LWA_* */
export const SAFEHOME360_VERSION = LWA_VERSION;
/** @deprecated Use LWA_* */
export const SAFEHOME360_TITLE = LWA_TITLE;

type SectionGroup = {
  group?: string;
  labels: string[];
  critical?: string[];
  source?: RubricItemSource;
  itemSkipWhen?: Record<string, SkipRule>;
  itemSources?: Record<string, RubricItemSource>;
  groupSkipWhen?: SkipRule;
};

function slug(label: string): string {
  return label
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "")
    .slice(0, 40);
}

function distributePoints(maxPoints: number, count: number): number[] {
  if (count <= 0) return [];
  const base = Math.floor((maxPoints / count) * 100) / 100;
  const points = Array.from({ length: count }, () => base);
  let sum = Math.round(base * count * 100) / 100;
  let i = 0;
  while (sum < maxPoints && i < count * 10) {
    const idx = i % count;
    const step = Math.min(0.1, Math.round((maxPoints - sum) * 100) / 100);
    if (step <= 0) break;
    points[idx] = Math.round((points[idx] + step) * 100) / 100;
    sum = Math.round(points.reduce((a, b) => a + b, 0) * 100) / 100;
    i += 1;
  }
  points[count - 1] = Math.round(
    (maxPoints - points.slice(0, -1).reduce((a, b) => a + b, 0)) * 100,
  ) / 100;
  return points;
}

function buildSection(
  id: string,
  title: string,
  sectionNumber: number,
  maxPoints: number,
  groups: SectionGroup[],
  categorySkipWhen?: SkipRule,
  defaultSource: RubricItemSource = "livewell360",
): AssessmentCategory {
  const flat: {
    label: string;
    group?: string;
    critical?: boolean;
    skipWhen?: SkipRule;
    source: RubricItemSource;
  }[] = [];

  for (const g of groups) {
    const groupSource = g.source ?? defaultSource;
    for (const label of g.labels) {
      flat.push({
        label,
        group: g.group,
        critical: g.critical?.includes(label),
        skipWhen: g.itemSkipWhen?.[label] ?? g.groupSkipWhen,
        source: g.itemSources?.[label] ?? groupSource,
      });
    }
  }

  const weights = distributePoints(maxPoints, flat.length);
  const items: AssessmentItem[] = flat.map((entry, index) => ({
    id: `${id}_${slug(entry.label)}`,
    label: entry.label,
    maxPoints: weights[index] ?? 0,
    group: entry.group,
    scoringScale: entry.critical ? "critical" : "standard",
    skipWhen: entry.skipWhen,
    source: entry.source,
  }));

  return {
    id,
    title,
    sectionNumber,
    maxPoints,
    items,
    skipWhen: categorySkipWhen,
  };
}

/**
 * KAA scored domains — raw weights sum to 100 (Independence Score™ = earned/max × 100).
 *
 * `critical` items (scoringScale: "critical") earn points exactly like standard
 * items (excellent = max, acceptable = 50%, unsafe = 0, N/A excluded). What the
 * flag changes is the BAND: any applicable critical item rated unsafe caps the
 * Independence band at "High Risk" no matter how high the arithmetic score is
 * (assessment.safetyGradeFromScore / assessmentBand; backend
 * rule_engine_defaults.risk_band_for_score). The numeric score is never altered,
 * so trend lines stay comparable. Membership/ECM rules keep using the score.
 */
export const LWA_CATEGORIES: AssessmentCategory[] = [
  buildSection("home_safety", "1. Home Safety", 2, 12, [
    {
      group: "Bath & wet areas",
      source: "aarp",
      labels: [
        "Toilet grab bar installed",
        "Shower grab bar installed",
        "Anti-slip flooring",
        "Shower chair available",
        "Toilet height appropriate",
        "Hot water scald risk controlled",
        "Bathroom well ventilated",
      ],
      critical: ["Toilet grab bar installed", "Anti-slip flooring"],
      itemSources: { "Bathroom well ventilated": "livewell360" },
    },
    {
      group: "Entry & circulation",
      source: "aarp",
      labels: [
        "Pathway level and clear",
        "Zero-step or ramped main entry",
        "Entrance railing if needed",
        "Adequate entry lighting",
        "Hallways free of trip hazards",
        "Loose rugs secured or removed",
      ],
      critical: ["Pathway level and clear", "Loose rugs secured or removed"],
      itemSkipWhen: { "Entrance railing if needed": RULE.STAIRS },
    },
    {
      group: "Rooms",
      source: "aarp",
      labels: [
        "Bedroom night lighting",
        "Bed transfer support",
        "Smoke and CO detectors on each level",
        "Stove / gas safety controls",
        "Living area walkways clear",
      ],
      critical: ["Smoke and CO detectors on each level"],
      itemSources: {
        "Smoke and CO detectors on each level": "aarp",
        "Stove / gas safety controls": "aarp",
      },
    },
  ]),
  buildSection("mobility", "2. Mobility & Accessibility", 3, 10, [
    {
      source: "cdc",
      labels: [
        "Walks independently or with correct device",
        "Balance adequate for home",
        "Stands from chair without arm push",
        "Transfers bed/chair safely",
        "Stairs manageable or alternative exists",
        "Door widths / thresholds accessible",
        "Wheelchair or walker path clear",
      ],
      critical: ["Transfers bed/chair safely", "Stands from chair without arm push"],
      itemSkipWhen: {
        "Stairs manageable or alternative exists": RULE.STAIRS,
        "Door widths / thresholds accessible": RULE.WHEELCHAIR,
      },
      itemSources: {
        "Door widths / thresholds accessible": "aarp",
        "Wheelchair or walker path clear": "aarp",
        "Stands from chair without arm push": "cdc",
      },
    },
  ]),
  buildSection("health_wellness", "3. Health & Wellness", 4, 9, [
    {
      group: "Clinical baseline",
      labels: [
        "Chronic conditions documented",
        "Medications reconciled",
        "Meds checked for dizziness/sedation",
        "Pain managed acceptably",
        "Vision/hearing supports in place",
        "Nutrition adequate",
        "BP / sugar checked regularly",
      ],
      critical: ["Medications reconciled"],
      itemSources: {
        "Medications reconciled": "cdc",
        "Meds checked for dizziness/sedation": "cdc",
        "Vision/hearing supports in place": "cdc",
      },
    },
    {
      group: "Fall risk (STEADI)",
      source: "cdc",
      labels: [
        "No falls in the past year",
        "Steady when walking",
        "Not worried about falling",
        "Rush to toilet / urgency managed",
        "Foot sensation adequate for walking",
      ],
      critical: ["No falls in the past year", "Steady when walking"],
    },
  ]),
  buildSection("adl", "4. Activities of Daily Living (ADL)", 5, 10, [
    {
      labels: [
        "Bathing independently or with plan",
        "Dressing independently or with plan",
        "Toileting independently or with plan",
        "Eating / feeding independence",
        "Transfer / mobility for ADLs",
        "Personal hygiene maintained",
      ],
      critical: ["Toileting independently or with plan"],
    },
  ]),
  buildSection("iadl", "5. Instrumental ADLs (IADL)", 6, 9, [
    {
      labels: [
        "Manages medications schedule",
        "Prepares or receives meals safely",
        "Handles shopping / errands",
        "Manages finances or has help",
        "Uses transportation safely",
        "Light housework manageable",
      ],
    },
  ]),
  buildSection("cognitive_emotional", "6. Cognitive & Emotional Wellness", 7, 7, [
    {
      labels: [
        "Orientation to person/place/time",
        "Mood stable / no untreated depression",
        "Memory adequate for daily safety",
        "Judgment safe for leaving stove/doors",
        "Social engagement present",
        "Safe from wandering / getting lost",
      ],
      critical: ["Judgment safe for leaving stove/doors"],
      itemSources: {
        "Mood stable / no untreated depression": "cdc",
      },
    },
  ]),
  buildSection("emergency", "7. Emergency Preparedness", 8, 8, [
    {
      labels: [
        "Emergency contacts posted",
        "SOS / alert method available",
        "Evacuation path understood",
        "First aid / flashlight accessible",
        "Family response plan documented",
      ],
      critical: ["Emergency contacts posted"],
    },
  ]),
  buildSection("home_condition", "8. Home Condition & Maintenance", 9, 8, [
    {
      labels: [
        "No major structural hazards",
        "Electrical outlets/wiring safe",
        "Damp / mold controlled",
        "Plumbing reliable",
        "Repairs backlog acceptable",
      ],
      critical: ["Electrical outlets/wiring safe"],
    },
  ]),
  buildSection("technology", "9. Technology Readiness", 10, 6, [
    {
      labels: [
        "Can use phone for emergencies",
        "Video call capable (self or family)",
        "Smart safety devices appropriate",
        "Medication reminder tech if needed",
        "Wi‑Fi / power backup considered",
        "Light switches easy to reach and operate",
        "Home secure (locks, visitor check)",
      ],
    },
  ]),
  buildSection("family_support", "10. Family & Caregiver Support", 11, 9, [
    {
      labels: [
        "Primary caregiver / family identified",
        "Check-in frequency adequate",
        "NRI / remote family plan if applicable",
        "Caregiver stress manageable",
        "Advance directive / decision-maker known",
        "Willing to engage ECM if recommended",
      ],
    },
  ]),
  buildSection("financial_benefits", "11. Financial & Government Benefits", 12, 6, [
    {
      labels: [
        "Income / pension status known",
        "Health insurance / schemes reviewed",
        "Eligible government benefits identified",
        "Documents available for applications",
        "Budget for home improvements realistic",
      ],
    },
  ]),
  buildSection("lifestyle", "12. Lifestyle & Social Engagement", 13, 6, [
    {
      labels: [
        "Day structure / routine present",
        "Social contacts weekly",
        "Meaningful activities available",
        "Outdoor / community access",
        "Sleep environment supportive",
      ],
    },
  ]),
];

/** Alias for transitional imports */
export const SAFEHOME360_CATEGORIES = LWA_CATEGORIES;

export const LWA_RAW_MAX = LWA_CATEGORIES.reduce((s, c) => s + c.maxPoints, 0);
export const SAFEHOME360_RAW_MAX = LWA_RAW_MAX;
