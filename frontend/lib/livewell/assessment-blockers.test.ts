import { describe, expect, it } from "vitest";

import { isAnswered, unansweredBySection, unansweredQuestions, unansweredTitle } from "./assessment-blockers";

const steps = [
  { kind: "profile" },
  {
    kind: "section",
    cat: "Bathroom",
    items: [
      { id: "b1", label: "Grab bar", input: "rating", cat: "Bathroom" },
      { id: "b2", label: "Mat", input: "rating", cat: "Bathroom" },
    ],
  },
  {
    kind: "section",
    cat: "Kitchen",
    items: [
      { id: "k1", label: "Gas", input: "yesno", cat: "Kitchen" },
      { id: "k2", label: "Notes", input: "text", cat: "Kitchen" },
    ],
  },
  { kind: "review" },
];

describe("assessment blockers", () => {
  it("counts a text answer only when it has words (same as the server)", () => {
    expect(isAnswered({ id: "k2", input: "text" }, {}, { k2: "   " })).toBe(false);
    expect(isAnswered({ id: "k2", input: "text" }, {}, { k2: "Steep stairs" })).toBe(true);
    // A note on a rating question is not an answer.
    expect(isAnswered({ id: "b1", input: "rating" }, {}, { b1: "note" })).toBe(false);
    expect(isAnswered({ id: "b1", input: "rating" }, { b1: "na" }, {})).toBe(true);
  });

  it("lists what is left with the screen to jump to", () => {
    const left = unansweredQuestions(steps, { b1: "excellent", k1: "unsafe" }, {});
    expect(left.map((u) => [u.id, u.step])).toEqual([
      ["b2", 1],
      ["k2", 2],
    ]);
    expect(unansweredBySection(left)).toEqual([
      { cat: "Bathroom", step: 1, count: 1 },
      { cat: "Kitchen", step: 2, count: 1 },
    ]);
    expect(unansweredTitle(left.length)).toBe("2 questions not answered yet");
    expect(unansweredTitle(1)).toBe("1 question not answered yet");
  });

  it("is empty when everything is answered", () => {
    expect(unansweredQuestions(steps, { b1: "na", b2: "na", k1: "excellent" }, { k2: "ok" })).toEqual([]);
  });
});
