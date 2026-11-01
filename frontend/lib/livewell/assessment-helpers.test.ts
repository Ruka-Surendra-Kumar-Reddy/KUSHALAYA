import { describe, expect, it } from "vitest";

import { splitClientName, clientDisplayName, safetyGradeFromScore } from "./assessment";

describe("assessment name helpers", () => {
  it("splits full names", () => {
    expect(splitClientName("Lakshmi Rao")).toEqual({ first: "Lakshmi", last: "Rao" });
    expect(splitClientName("Lakshmi")).toEqual({ first: "Lakshmi", last: "" });
    expect(splitClientName("  A   B   C ")).toEqual({ first: "A", last: "B   C" });
  });

  it("display name joins parts", () => {
    expect(clientDisplayName({ clientFirstName: "Lakshmi", clientLastName: "Rao" } as never)).toContain(
      "Lakshmi",
    );
  });
});

describe("safety grade and risk", () => {
  it("returns independence bands for high and low scores", () => {
    expect(safetyGradeFromScore(95).status).toBeTruthy();
    expect(safetyGradeFromScore(10).status).toBe("critical");
  });

});
