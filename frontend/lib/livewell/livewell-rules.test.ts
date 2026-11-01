import { describe, expect, it } from "vitest";

import { ecmRecommended, recommendMembership } from "./livewell-rules";

describe("livewell membership / ECM rules", () => {
  it("recommends Independent Living for high scores", () => {
    expect(recommendMembership({ independenceScore: 88 })).toBe("mbr_independent");
  });

  it("recommends Assisted for moderate scores", () => {
    expect(recommendMembership({ independenceScore: 65 })).toBe("mbr_assisted");
  });

  it("recommends Premium for high risk", () => {
    expect(recommendMembership({ independenceScore: 45 })).toBe("mbr_premium");
  });

  it("NRI family abroad overrides score", () => {
    expect(recommendMembership({ independenceScore: 90, familyAbroad: true })).toBe("mbr_nri");
  });

  it("high score alone with cognitive risk is Assisted not Independent", () => {
    expect(
      recommendMembership({
        independenceScore: 88,
        livesAlone: true,
        cognitiveRisk: "mild",
      }),
    ).toBe("mbr_assisted");
  });

  it("flags ECM for low score, alone, abroad, cognitive, or preference", () => {
    expect(ecmRecommended({ independenceScore: 50 })).toBe(true);
    expect(ecmRecommended({ independenceScore: 70, livesAlone: true })).toBe(true);
    expect(ecmRecommended({ independenceScore: 90, familyAbroad: true })).toBe(true);
    expect(ecmRecommended({ independenceScore: 90, familyRequestsEcm: true })).toBe(true);
    expect(ecmRecommended({ independenceScore: 88, cognitiveRisk: "mild" })).toBe(true);
    expect(ecmRecommended({ independenceScore: 85 })).toBe(false);
  });
});
