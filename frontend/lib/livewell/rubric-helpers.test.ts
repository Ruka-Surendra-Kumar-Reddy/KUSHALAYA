import { describe, expect, it } from "vitest";

import { newCategoryId, normalizeRubric, rubricTotalMax } from "./rubric";
import type { AssessmentCategory } from "./assessment";

describe("rubric helpers", () => {
  it("rounds max points up to at least 1 and syncs category totals", () => {
    const cats: AssessmentCategory[] = [
      {
        id: "a",
        title: "A",
        maxPoints: 99,
        items: [
          { id: "1", label: "x", maxPoints: 2.4 },
          { id: "2", label: "y", maxPoints: 0 },
        ],
      },
    ];
    const out = normalizeRubric(cats);
    expect(out[0].items[0].maxPoints).toBe(2);
    expect(out[0].items[1].maxPoints).toBe(1);
    expect(out[0].maxPoints).toBe(3);
    expect(rubricTotalMax(out)).toBe(3);
  });

  it("newCategoryId slugifies title", () => {
    const id = newCategoryId("Bathroom Safety!");
    expect(id.startsWith("bathroom_safety_")).toBe(true);
  });
});
