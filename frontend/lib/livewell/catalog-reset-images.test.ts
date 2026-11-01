import { describe, expect, it } from "vitest";

import { resetCatalogPreserveImages, type CatalogProduct, type SafetyCatalog } from "./catalog";
import { DEFAULT_SAFETY_CATALOG } from "./catalog-defaults";

describe("resetCatalogPreserveImages", () => {
  it("keeps product photos when resetting to factory defaults", () => {
    const first = DEFAULT_SAFETY_CATALOG.products[0];
    expect(first).toBeTruthy();
    const previous: SafetyCatalog = {
      products: DEFAULT_SAFETY_CATALOG.products.map((p) =>
        p.id === first!.id
          ? ({
              ...p,
              image_ids: [42, 43],
              image_urls: ["/a", "/b"],
              name: "Old name should be replaced",
            } as CatalogProduct)
          : p,
      ),
      packages: DEFAULT_SAFETY_CATALOG.packages,
    };

    const next = resetCatalogPreserveImages(previous);
    const restored = next.products.find((p) => p.id === first!.id);
    expect(restored?.image_ids).toEqual([42, 43]);
    expect(restored?.name).toBe(first!.name);
  });
});
