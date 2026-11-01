/** Checklist item provenance — LiveWell360 Assessment (KAA) v2.0. */

import { withPublicBrand } from "@/lib/public-brand";

export type RubricItemSource = "aarp" | "cdc" | "livewell360" | "safehome360";

export type RubricSourceMeta = {
  id: RubricItemSource;
  shortLabel: string;
  label: string;
  description: string;
  reference: string;
};

export const RUBRIC_SOURCES: Record<RubricItemSource, RubricSourceMeta> = {
  aarp: {
    id: "aarp",
    shortLabel: "AARP",
    label: "AARP HomeFit®",
    description: "Room-by-room home safety and accessibility (falls, lighting, grab bars, pathways).",
    reference: "AARP HomeFit Guide — livable-communities housing checklists",
  },
  cdc: {
    id: "cdc",
    shortLabel: "CDC",
    label: "CDC STEADI",
    description: "Fall-risk and functional screening (mobility, balance, medications, wellness).",
    reference: "CDC STEADI — Stopping Elderly Accidents, Deaths & Injuries",
  },
  livewell360: {
    id: "livewell360",
    shortLabel: "KAA",
    label: withPublicBrand("LiveWell360 Assessment"),
    description: "KushAlaya KAA domains — ADL/IADL, family, benefits, lifestyle, home condition.",
    reference: withPublicBrand("LiveWell360 Assessment (KAA) Specification v2.0"),
  },
  safehome360: {
    id: "safehome360",
    shortLabel: "KAA",
    label: withPublicBrand("LiveWell360 Assessment"),
    description: withPublicBrand("Legacy source id — treated as LiveWell360."),
    reference: withPublicBrand("LiveWell360 Assessment (KAA) Specification v2.0"),
  },
};

export const RUBRIC_SOURCE_ORDER: RubricItemSource[] = ["aarp", "cdc", "livewell360"];

export function rubricSourceLabel(source: RubricItemSource | undefined): string {
  if (!source) return RUBRIC_SOURCES.livewell360.shortLabel;
  return RUBRIC_SOURCES[source]?.shortLabel ?? RUBRIC_SOURCES.livewell360.shortLabel;
}

export function countItemsBySource(
  items: { source?: RubricItemSource }[],
): Record<RubricItemSource, number> {
  const counts: Record<RubricItemSource, number> = {
    aarp: 0,
    cdc: 0,
    livewell360: 0,
    safehome360: 0,
  };
  for (const item of items) {
    const key = item.source ?? "livewell360";
    counts[key] += 1;
  }
  return counts;
}
