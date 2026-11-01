import { describe, expect, it } from "vitest";
import { CAREGIVER_ANSWERS } from "./caregiver-answers";

// Owner decision 28 Oct: these last options described a real situation, not
// "does not apply", so they now live inside a real rating (the N/A chip remains).
const NOW_RISK: Record<string, RegExp> = {
  mobility_balance_adequate_for_home: /can't stand alone/,
  adl_transfer_mobility_for_adls: /fully immobile/,
  mobility_stands_from_chair_without_arm_push: /or can't/,
  mobility_walks_independently_or_with_correct_devi: /Can't walk/,
  health_wellness_steady_when_walking: /can't walk/,
  iadl_uses_transportation_safely: /never goes out/,
  health_wellness_no_falls_in_the_past_year: /bed-bound/,
};

const NOW_SAFE: Record<string, RegExp | null> = {
  adl_bathing_independently_or_with_plan: /caregiver helps/,
  adl_dressing_independently_or_with_plan: /caregiver helps/,
  adl_toileting_independently_or_with_plan: /caregiver helps/,
  mobility_transfers_bed_chair_safely: /lifted by caregiver/,
  health_wellness_pain_managed_acceptably: /^No, or well controlled$/,
  health_wellness_rush_to_toilet_urgency_managed: /^No$/,
  health_wellness_foot_sensation_adequate_for_walking: /no numbness/,
  health_wellness_vision_hearing_supports_in_place: /sees and hears well/,
  technology_medication_reminder_tech_if_needed: /manages on their own/,
  financial_benefits_health_insurance_schemes_reviewed: /^Yes, policy checked$/,
};

describe("caregiver answers → rating", () => {
  it("the 7 former N/A answers that were a risk now save as unsafe", () => {
    for (const [id, re] of Object.entries(NOW_RISK)) {
      const w = CAREGIVER_ANSWERS[id];
      expect(w.unsafe, id).toMatch(re);
      expect(w.na, id).toBeUndefined();
    }
  });

  it("the 10 former N/A answers that were the best case now save as excellent", () => {
    for (const [id, re] of Object.entries(NOW_SAFE)) {
      const w = CAREGIVER_ANSWERS[id];
      expect(w.excellent, id).toMatch(re as RegExp);
      expect(w.na, id).toBeUndefined();
    }
  });

  it("keeps every label short enough for a phone button", () => {
    for (const [id, w] of Object.entries(CAREGIVER_ANSWERS)) {
      for (const label of [w.excellent, w.acceptable, w.unsafe, w.na]) {
        if (label) expect(label.length, `${id}: ${label}`).toBeLessThanOrEqual(44);
      }
    }
  });
});
