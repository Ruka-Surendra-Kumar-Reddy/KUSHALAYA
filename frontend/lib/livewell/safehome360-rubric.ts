import type { AssessmentCategory, AssessmentItem, SkipRule } from "./assessment";
import { RULE } from "./conditional-rules";
import type { RubricItemSource } from "./rubric-sources";
import { withPublicBrand } from "@/lib/public-brand";

export const SAFEHOME360_VERSION = "1.0";
/** Legacy v1.0 checklist title (the live one is LWA_TITLE in ./lwa-rubric). */
export const SAFEHOME360_TITLE = withPublicBrand("LiveWell360 Assessment");

type SectionGroup = {
  group?: string;
  labels: string[];
  critical?: string[];
  /** Default source for all labels in this group. */
  source?: RubricItemSource;
  /** Per-label skip rules (item hidden when rule matches). */
  itemSkipWhen?: Record<string, SkipRule>;
  /** Per-label source overrides. */
  itemSources?: Record<string, RubricItemSource>;
  /** Apply same skip rule to every label in this group. */
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
  points[count - 1] = Math.round((maxPoints - points.slice(0, -1).reduce((a, b) => a + b, 0)) * 100) / 100;
  return points;
}

function buildSection(
  id: string,
  title: string,
  sectionNumber: number,
  maxPoints: number,
  groups: SectionGroup[],
  categorySkipWhen?: SkipRule,
  defaultSource: RubricItemSource = "safehome360",
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

/** Legacy v1.0 scored sections (150 raw points → normalized 0–100). */
export const SAFEHOME360_CATEGORIES: AssessmentCategory[] = [
  buildSection("exterior", "Exterior & Entry", 2, 10, [
    {
      group: "Entrance",
      source: "aarp",
      labels: [
        "Pathway level",
        "Slip-resistant pathway",
        "Adequate lighting",
        "Door threshold safe",
        "Ramp required",
        "Ramp installed",
        "Entrance railing",
        "Door width adequate",
        "Door opens easily",
        "Video doorbell installed",
        "Visitor identification",
        "Security available",
        "Emergency vehicle access",
      ],
      critical: ["Slip-resistant pathway", "Door threshold safe", "Emergency vehicle access"],
      itemSkipWhen: {
        "Ramp required": RULE.RAMP,
        "Ramp installed": RULE.RAMP,
        "Door width adequate": RULE.WHEELCHAIR,
        "Entrance railing": RULE.STAIRS,
      },
      itemSources: {
        "Video doorbell installed": "safehome360",
        "Visitor identification": "safehome360",
        "Security available": "safehome360",
      },
    },
  ], undefined, "aarp"),
  buildSection("living_room", "Living Room", 3, 10, [
    {
      source: "aarp",
      labels: [
        "Walkway clear",
        "Walkway width adequate",
        "Loose rugs removed",
        "Furniture stable",
        "Chair height appropriate",
        "Sofa height appropriate",
        "Electrical cords secured",
        "Floor condition safe",
        "Lighting adequate",
        "Phone accessible",
        "Emergency button",
        "Coffee table hazard",
        "Pet trip hazards",
        "Remote controls accessible",
        "AC controls accessible",
      ],
      critical: ["Loose rugs removed", "Floor condition safe"],
      itemSkipWhen: {
        "Phone accessible": RULE.LIVES_ALONE,
        "Emergency button": RULE.LIVES_ALONE,
      },
      itemSources: {
        "Emergency button": "safehome360",
      },
    },
  ], undefined, "aarp"),
  buildSection("bathroom", "Bathroom", 4, 25, [
    {
      group: "Toilet area",
      source: "aarp",
      labels: [
        "Grab bar installed",
        "Toilet height appropriate",
        "Toilet support rails",
        "Transfer space adequate",
        "Flush easily accessible",
        "Toilet paper reachable",
      ],
      critical: ["Grab bar installed", "Transfer space adequate"],
      itemSkipWhen: {
        "Transfer space adequate": RULE.WHEELCHAIR,
        "Toilet support rails": RULE.WHEELCHAIR,
      },
    },
    {
      group: "Shower area",
      source: "aarp",
      labels: [
        "Grab bar",
        "Foldable grab bar",
        "Shower chair",
        "Anti-slip flooring",
        "Shower threshold safe",
        "Drainage adequate",
        "Handheld shower",
        "Mixer easy to use",
        "Water temperature safe",
      ],
      critical: ["Grab bar", "Anti-slip flooring", "Shower threshold safe"],
      itemSkipWhen: {
        "Shower chair": RULE.WHEELCHAIR,
        "Foldable grab bar": RULE.WHEELCHAIR,
      },
    },
    {
      group: "Sink area",
      source: "aarp",
      labels: [
        "Sink height appropriate",
        "Mirror height",
        "Soap reachable",
        "Storage accessible",
      ],
      itemSkipWhen: {
        "Sink height appropriate": RULE.WHEELCHAIR,
      },
    },
    {
      group: "Safety",
      source: "aarp",
      labels: [
        "Emergency bell",
        "Night light",
        "Door unlockable externally",
        "Floor dry",
        "Ventilation adequate",
      ],
      critical: ["Emergency bell", "Floor dry"],
      itemSkipWhen: {
        "Door unlockable externally": RULE.LIVES_ALONE,
      },
    },
  ], undefined, "aarp"),
  buildSection("bedroom", "Bedroom", 5, 15, [
    {
      source: "aarp",
      labels: [
        "Bed height",
        "Bed rail",
        "Night lamp",
        "Walking path",
        "Closet accessibility",
        "Chair available",
        "Curtains easy to operate",
        "Phone nearby",
        "Emergency button",
        "Medication table",
        "Water accessible",
        "Fan controls",
        "AC controls",
        "Reading light",
        "Fall mat",
      ],
      critical: ["Bed height", "Walking path", "Fall mat"],
      itemSkipWhen: {
        "Phone nearby": RULE.LIVES_ALONE,
        "Emergency button": RULE.LIVES_ALONE,
        "Closet accessibility": RULE.WHEELCHAIR,
      },
      itemSources: {
        "Emergency button": "safehome360",
      },
    },
  ], undefined, "aarp"),
  buildSection("kitchen", "Kitchen", 6, 10, [
    {
      source: "aarp",
      labels: [
        "Frequently used items accessible",
        "No climbing required",
        "Gas safety",
        "Fire extinguisher",
        "Smoke detector",
        "Lighting",
        "Slip-resistant floor",
        "Water leak protection",
        "Electrical safety",
        "Counter height appropriate",
      ],
      critical: ["Gas safety", "Fire extinguisher", "Smoke detector"],
      itemSkipWhen: {
        "Counter height appropriate": RULE.WHEELCHAIR,
        "No climbing required": RULE.WHEELCHAIR,
      },
    },
  ], undefined, "aarp"),
  buildSection("hallways", "Hallways", 7, 10, [
    {
      source: "aarp",
      labels: [
        "Lighting",
        "Motion lighting",
        "Handrails",
        "Clear pathway",
        "Safe thresholds",
        "Door width",
        "Furniture placement",
        "Slip hazards removed",
        "Emergency lighting",
        "Wall/floor contrast",
      ],
      critical: ["Handrails", "Clear pathway", "Slip hazards removed"],
      itemSkipWhen: {
        Handrails: RULE.STAIRS,
        "Safe thresholds": RULE.STAIRS,
        "Door width": RULE.WHEELCHAIR,
      },
    },
  ], undefined, "aarp"),
  buildSection("balcony", "Balcony", 8, 5, [
    {
      source: "aarp",
      labels: [
        "Railing height",
        "Furniture stable",
        "Slip resistance",
        "Drainage",
        "Trip hazards removed",
      ],
      critical: ["Railing height", "Trip hazards removed"],
    },
  ], RULE.BALCONY, "aarp"),
  buildSection("mobility", "Mobility Assessment", 9, 20, [
    {
      source: "cdc",
      labels: [
        "Stand independently",
        "Sit safely",
        "Turn safely",
        "Walk independently",
        "Uses assistive device correctly",
        "Transfer safely",
        "Climb one step",
        "Open doors",
        "Reach shelves",
        "Bend safely",
        "Recover balance",
        "Carry light object",
        "Walking speed",
        "Balance",
        "Endurance",
      ],
      critical: ["Transfer safely", "Recover balance"],
      itemSkipWhen: {
        "Climb one step": RULE.STAIRS,
        "Uses assistive device correctly": RULE.ASSISTIVE_DEVICE,
      },
    },
  ], undefined, "cdc"),
  buildSection("emergency", "Emergency Preparedness", 10, 10, [
    {
      source: "aarp",
      labels: [
        "Emergency contacts displayed",
        "Doctor information available",
        "Medication list available",
        "Medical records accessible",
        "Backup power",
        "Flashlight available",
        "Emergency key",
        "Neighbor support",
        "Family response plan",
        "Preferred hospital identified",
      ],
      critical: ["Emergency contacts displayed", "Medication list available"],
      itemSkipWhen: {
        "Neighbor support": RULE.LIVES_ALONE,
        "Emergency key": RULE.LIVES_ALONE,
      },
      itemSources: {
        "Doctor information available": "cdc",
        "Medication list available": "cdc",
        "Medical records accessible": "cdc",
        "Family response plan": "safehome360",
        "Preferred hospital identified": "safehome360",
      },
    },
  ], undefined, "aarp"),
  buildSection("smart_home", "Smart Home Readiness", 11, 10, [
    {
      labels: [
        "Internet available",
        "Smart doorbell",
        "Smart lock",
        "Motion sensors",
        "Indoor camera",
        "SOS button",
        "Smoke detector",
        "Water leak sensor",
        "Medication reminder",
        "Voice assistant",
      ],
      itemSkipWhen: {
        "Smart doorbell": RULE.SMART_ADVANCED,
        "Smart lock": RULE.SMART_ADVANCED,
        "Motion sensors": RULE.SMART_ADVANCED,
        "Indoor camera": RULE.SMART_ADVANCED,
        "Water leak sensor": RULE.SMART_ADVANCED,
        "Medication reminder": RULE.SMART_ADVANCED,
        "Voice assistant": RULE.SMART_ADVANCED,
      },
    },
  ], RULE.NO_SMART_HOME, "safehome360"),
  buildSection("wellness", "Wellness Observation", 12, 15, [
    {
      source: "cdc",
      labels: [
        "Personal hygiene",
        "Nutrition",
        "Hydration",
        "Weight loss signs",
        "Medication adherence",
        "Mood",
        "Memory",
        "Speech",
        "House cleanliness",
        "Food availability",
        "Water availability",
        "Social interaction",
        "Depression indicators",
        "Confusion",
        "Overall wellbeing",
      ],
      itemSources: {
        "House cleanliness": "aarp",
        "Food availability": "aarp",
        "Water availability": "aarp",
      },
    },
  ], undefined, "cdc"),
  buildSection("family_support", "Family Support Assessment", 13, 10, [
    {
      source: "safehome360",
      labels: [
        "Children call regularly",
        "Children visit regularly",
        "Emergency contacts verified",
        "Neighbor support",
        "Domestic helper verified",
        "Transportation available",
        "Medical escort available",
        "Pharmacy nearby",
        "Family support network",
        "Communication plan",
      ],
      itemSkipWhen: {
        "Neighbor support": RULE.LIVES_ALONE,
        "Domestic helper verified": RULE.DOMESTIC_HELPER,
      },
    },
  ], undefined, "safehome360"),
];

export const SAFEHOME360_RAW_MAX = SAFEHOME360_CATEGORIES.reduce((s, c) => s + c.maxPoints, 0);
