import { describe, expect, it } from "vitest";
import { createAutosaveGate, suggestedAssessor } from "./draftAutosave";

describe("draft autosave gate", () => {
  it("does not save on open or after load-time fills", () => {
    const gate = createAutosaveGate();
    expect(gate.shouldSave("draft")).toBe(false);
  });

  it("saves a draft only after a real edit", () => {
    const gate = createAutosaveGate();
    gate.markUserEdit();
    expect(gate.shouldSave("draft")).toBe(true);
    expect(gate.shouldSave("completed")).toBe(false);
  });

  it("treats a change as user-made only right after input", () => {
    const gate = createAutosaveGate();
    expect(gate.recentInteraction(1000)).toBe(false);
    gate.markInteraction(1000);
    expect(gate.recentInteraction(2000)).toBe(true);
    expect(gate.recentInteraction(5000)).toBe(false);
  });
});

describe("suggestedAssessor", () => {
  const team = [{ email: "Krish@x.in", first_name: "Krish", last_name: "Posa" }];
  it("suggests the signed-in user's name", () => {
    expect(suggestedAssessor(team, "krish@x.in")).toBe("Krish Posa");
  });
  it("returns blank for unknown users", () => {
    expect(suggestedAssessor(team, "other@x.in")).toBe("");
    expect(suggestedAssessor(team, null)).toBe("");
  });
});
