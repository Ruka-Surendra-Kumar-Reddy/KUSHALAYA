import { describe, expect, it } from "vitest";

import { hostname, isFamilyHost, isMarketingHost, isOpsHost } from "./hosts";

describe("host routing helpers", () => {
  it("strips the port and lower-cases", () => {
    expect(hostname("Family.Kushalaya.com:443")).toBe("family.kushalaya.com");
    expect(hostname("localhost:3010")).toBe("localhost");
  });

  it("routes the production hosts", () => {
    expect(isFamilyHost("family.kushalaya.com")).toBe(true);
    expect(isMarketingHost("www.kushalaya.com")).toBe(true);
    expect(isMarketingHost("kushalaya.com")).toBe(true);
    expect(isOpsHost("ops.kushalaya.com")).toBe(true);
    expect(isFamilyHost("ops.kushalaya.com")).toBe(false);
    expect(isMarketingHost("ops.kushalaya.com")).toBe(false);
  });

  it("routes the staging hosts exactly like production", () => {
    expect(isFamilyHost("staging-family.kushalaya.com")).toBe(true);
    expect(isMarketingHost("staging-www.kushalaya.com")).toBe(true);
    expect(isOpsHost("staging-ops.kushalaya.com")).toBe(true);
    expect(isMarketingHost("staging-family.kushalaya.com")).toBe(false);
    expect(isFamilyHost("staging-ops.kushalaya.com")).toBe(false);
  });

  it("routes the local dev hostnames", () => {
    expect(isFamilyHost("family.localhost:3010")).toBe(true);
    expect(isMarketingHost("kushalaya.localhost:3010")).toBe(true);
    expect(isOpsHost("localhost:3010")).toBe(true);
    expect(isOpsHost("127.0.0.1:3010")).toBe(true);
  });

  it("never treats the family host as marketing", () => {
    // A previous `h.startsWith("family.")` rule served the marketing site on
    // the family subdomain; the exact-match sets and the early return in
    // isMarketingHost are what prevent that.
    for (const h of ["family.kushalaya.com", "staging-family.kushalaya.com", "family.localhost"]) {
      expect(isMarketingHost(h)).toBe(false);
    }
  });

  it("does not match lookalike or legacy hostnames", () => {
    expect(isFamilyHost("family.kushalaya.com.evil.example")).toBe(false);
    expect(isFamilyHost("notfamily.kushalaya.com")).toBe(false);
    expect(isMarketingHost("livewell.tekmatrix.ai")).toBe(false);
    expect(isMarketingHost("")).toBe(false);
  });
});

describe("caregiver host", () => {
  it("is recognised and treated as an ops host", async () => {
    const { isCaregiverHost } = await import("./hosts");
    expect(isCaregiverHost("caregiver.kushalaya.com")).toBe(true);
    expect(isCaregiverHost("CAREGIVER.kushalaya.com:443")).toBe(true);
    expect(isCaregiverHost("ops.kushalaya.com")).toBe(false);
    expect(isOpsHost("caregiver.kushalaya.com")).toBe(true);
    expect(isFamilyHost("caregiver.kushalaya.com")).toBe(false);
  });
});
