import { describe, expect, it } from "vitest";

import {
  platformAdminGateFeatureLabel,
  platformAdminNeedsTenantForPath,
} from "./platformAdminRoutes";

describe("platformAdminNeedsTenantForPath", () => {
  it.each([
    ["/executive", true],
    ["/executive/x", true],
    ["/prospects", true],
    ["/matching/run", true],
    ["/elders/1", true],
    ["/assignments", true],
    ["/monitoring/alerts", true],
    ["/billing", true],
    ["/communications/requests", true],
    ["/settings/workflows", true],
    ["/settings/subscription", true],
    ["/kushalaya/activity", true],
    ["/copilot", true],
    ["/cleaning/quotes", true],
    ["/dashboard", false],
    ["/settings", false],
    ["/kushalaya/catalog", false],
    ["/users", false],
  ] as const)("%s -> %s", (path, expected) => {
    expect(platformAdminNeedsTenantForPath(path)).toBe(expected);
  });

  it("workforce marketplace tab does not require tenant", () => {
    expect(platformAdminNeedsTenantForPath("/workforce", "tab=marketplace")).toBe(false);
    expect(platformAdminNeedsTenantForPath("/workforce", "?tab=marketplace")).toBe(false);
    expect(platformAdminNeedsTenantForPath("/workforce", "tab=bench")).toBe(true);
    expect(platformAdminNeedsTenantForPath("/workforce")).toBe(true);
    expect(platformAdminNeedsTenantForPath("/workforce/x")).toBe(true);
  });
});

describe("platformAdminGateFeatureLabel", () => {
  it.each([
    ["/executive", "Executive center"],
    ["/prospects", "Recruitment pipeline"],
    ["/matching", "Matching"],
    ["/elders", "Elders"],
    ["/assignments", "Assignments"],
    ["/monitoring", "Monitoring"],
    ["/billing", "Billing"],
    ["/communications", "Service requests"],
    ["/settings/workflows", "Workflow automation"],
    ["/kushalaya/activity", "Session activity"],
    ["/workforce", "Command center"],
    ["/cleaning", "Cleaning operations"],
    ["/unknown", "this view"],
  ] as const)("%s", (path, label) => {
    expect(platformAdminGateFeatureLabel(path)).toBe(label);
  });
});
