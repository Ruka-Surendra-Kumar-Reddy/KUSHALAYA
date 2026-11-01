import {
  DEFAULT_VERTICAL,
  normalizeVertical,
  verticalFeatures as coreVerticalFeatures,
  verticalHasFeature as coreVerticalHasFeature,
  type VerticalId,
} from "@workforceos/contracts";
import {
  filterNavGroupsForVertical,
  isNavItemEnabled,
  isPathAllowedForVertical,
  requiredFeatureForPath,
} from "@workforceos/contracts/shell";

export {
  filterNavGroupsForVertical,
  isNavItemEnabled,
  isPathAllowedForVertical,
  requiredFeatureForPath,
};

/** Effective feature set for a vertical (pack + shared core). */
export function verticalFeatures(
  vertical: string | undefined | null,
): ReadonlySet<string> {
  return coreVerticalFeatures(vertical ?? DEFAULT_VERTICAL);
}

/** @deprecated Use verticalFeatures() — kept for callers expecting the raw map. */
export const VERTICAL_FEATURES: Record<VerticalId, ReadonlySet<string>> =
  Object.fromEntries(
    ([
      "ELDER_CARE",
      "SECURITY",
      "HOUSEKEEPING",
      "DRIVER_SERVICES",
      "HOME_HEALTHCARE",
      "SAFEHOME360",
      "LIVEWELL360",
    ] as const).map((id) => [id, verticalFeatures(id)]),
  ) as Record<VerticalId, ReadonlySet<string>>;

export function verticalHasFeature(
  vertical: string | undefined | null,
  feature: string,
): boolean {
  return coreVerticalHasFeature(vertical ?? DEFAULT_VERTICAL, feature);
}
