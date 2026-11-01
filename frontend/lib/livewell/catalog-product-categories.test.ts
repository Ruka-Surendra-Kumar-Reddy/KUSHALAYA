import { describe, expect, it } from "vitest";

import {
  PRODUCT_CATEGORY_ORDER,
  SERVICE_CATEGORY_PREFIXES,
  categoryLabelFromPrefix,
  defaultCatalogCategoryTypes,
} from "./catalog-product-categories";

describe("catalog category types", () => {
  it("defaults match order and kind", () => {
    const types = defaultCatalogCategoryTypes();
    expect(types.map((t) => t.prefix)).toEqual([...PRODUCT_CATEGORY_ORDER]);
    expect(types.every((t) => t.active)).toBe(true);
    const services = types.filter((t) => t.kind === "service").map((t) => t.prefix);
    expect(new Set(services)).toEqual(SERVICE_CATEGORY_PREFIXES);
  });

  it.each([
    [undefined, "General"],
    ["", "General"],
    ["BTH", "Bathroom Safety"],
    ["SVC", "KushAlaya Services"],
    ["ZZZ", "ZZZ"],
  ] as const)("categoryLabelFromPrefix(%j)", (prefix, label) => {
    expect(categoryLabelFromPrefix(prefix)).toBe(label);
  });
});
