import type { SkipRule } from "./assessment";
import type { ResidentProfile } from "./resident-profile";

/** Named rules referenced from rubric items (skip item/section when rule matches). */
export type ConditionalRuleId =
  | "unless_has_stairs"
  | "unless_wheelchair_user"
  | "unless_lives_alone"
  | "unless_smart_home_advanced"
  | "unless_has_balcony"
  | "unless_domestic_helper"
  | "unless_full_time_caregiver"
  | "unless_assistive_device"
  | "unless_ramp_relevant";

export const RULE: Record<string, SkipRule> = {
  STAIRS: { when: "unless_has_stairs" },
  WHEELCHAIR: { when: "unless_wheelchair_user" },
  LIVES_ALONE: { when: "unless_lives_alone" },
  SMART_ADVANCED: { when: "unless_smart_home_advanced" },
  BALCONY: { when: "unless_has_balcony" },
  DOMESTIC_HELPER: { when: "unless_domestic_helper" },
  FULL_TIME_CAREGIVER: { when: "unless_full_time_caregiver" },
  ASSISTIVE_DEVICE: { when: "unless_assistive_device" },
  RAMP: { when: "unless_ramp_relevant" },
  NO_SMART_HOME: { field: "smartHomeAssessment", equals: false },
};

function hasAssistiveDevice(profile: ResidentProfile): boolean {
  const d = profile.mobilityDevice;
  return Boolean(d && d !== "none");
}

function isRampRelevant(profile: ResidentProfile): boolean {
  return profile.hasStairs === true || profile.mobilityDevice === "wheelchair";
}

/** Returns true when the item/section should be skipped (hidden). */
export function evaluateConditionalRule(
  ruleId: ConditionalRuleId,
  profile: ResidentProfile,
): boolean {
  switch (ruleId) {
    case "unless_has_stairs":
      return profile.hasStairs !== true;
    case "unless_wheelchair_user":
      return profile.mobilityDevice !== "wheelchair";
    case "unless_lives_alone":
      return profile.livesAlone !== true;
    case "unless_smart_home_advanced":
      return profile.smartHomeAdvanced !== true;
    case "unless_has_balcony":
      return profile.hasBalcony !== true;
    case "unless_domestic_helper":
      return profile.domesticHelper !== true;
    case "unless_full_time_caregiver":
      return profile.fullTimeCaregiver !== true;
    case "unless_assistive_device":
      return !hasAssistiveDevice(profile);
    case "unless_ramp_relevant":
      return !isRampRelevant(profile);
    default:
      return false;
  }
}
