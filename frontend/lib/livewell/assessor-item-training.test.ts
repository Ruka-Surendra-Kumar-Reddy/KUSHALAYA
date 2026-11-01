import { describe, expect, it } from "vitest";

import { ASSESSOR_ITEM_TRAINING, trainingForItem } from "./assessor-item-training";
import { LWA_CATEGORIES } from "./lwa-rubric";
import { helpForRubricItem } from "./rubric-item-help";
import { normalizeRubricWithSources } from "./rubric";

describe("assessor item training", () => {
  it("covers every KAA checklist item", () => {
    const items = LWA_CATEGORIES.flatMap((c) => c.items);
    expect(ASSESSOR_ITEM_TRAINING.length).toBe(items.length);
    const missing = items.filter((i) => !trainingForItem(i.id));
    expect(missing.map((m) => m.id)).toEqual([]);
  });

  it("distinguishes ADL transfer from bed/chair transfer", () => {
    const adl = trainingForItem("adl_transfer_mobility_for_adls");
    const bed = trainingForItem("mobility_transfers_bed_chair_safely");
    expect(adl?.lookFor).toMatch(/bath|toilet|dressing|ADL/i);
    expect(bed?.lookFor).toMatch(/bed|chair/i);
    expect(adl?.excellent).not.toEqual(bed?.excellent);
  });

  it("attaches training help when normalizing rubric", () => {
    const normalized = normalizeRubricWithSources(LWA_CATEGORIES);
    const item = normalized
      .flatMap((c) => c.items)
      .find((i) => i.label === "Transfer / mobility for ADLs");
    expect(helpForRubricItem(item!)).toMatch(/Excellent/i);
  });
});
