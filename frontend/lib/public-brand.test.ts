import { describe, expect, it } from "vitest";
import {
  DEFAULT_PUBLIC_BRAND_NAME,
  publicBrandLogoParts,
  publicBrandMark,
  publicBrandName,
  resolvePortalBrandTitle,
  withPublicBrand,
} from "./public-brand";

describe("public-brand", () => {
  it("defaults to KushAlaya and rewrites LiveWell360 copy", () => {
    expect(publicBrandName()).toBe(DEFAULT_PUBLIC_BRAND_NAME);
    expect(DEFAULT_PUBLIC_BRAND_NAME).toBe("KushAlaya");
    expect(withPublicBrand("Hello LiveWell360")).toBe("Hello KushAlaya");
  });

  it("derives logo mark and accent for default name", () => {
    expect(publicBrandMark()).toBe("KU");
    expect(publicBrandLogoParts()).toEqual({ lead: "KushAlaya", accent: "" });
  });

  it("maps seeded LiveWell360™ portal titles to the public brand", () => {
    expect(resolvePortalBrandTitle("LiveWell360™")).toBe(DEFAULT_PUBLIC_BRAND_NAME);
    expect(resolvePortalBrandTitle("SafeHome 360™")).toBe(DEFAULT_PUBLIC_BRAND_NAME);
    expect(resolvePortalBrandTitle("Acme Home Care")).toBe("Acme Home Care");
  });
});
