import { describe, expect, it } from "vitest";

import { SEO_CITIES } from "./seo-cities";
import { SEO_FAQ_ALL, SEO_FAQ_GROUPS } from "./seo-faq";
import { SEO_SERVICES } from "./seo-services";

const nonEmpty = (s: string | undefined) => typeof s === "string" && s.trim().length > 0;

describe("SEO city pages", () => {
  it("has unique, url-safe slugs", () => {
    const slugs = SEO_CITIES.map((c) => c.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
    for (const s of slugs) expect(s).toMatch(/^[a-z0-9-]{1,40}$/);
  });

  it("fills every field and keeps meta within limits", () => {
    for (const c of SEO_CITIES) {
      for (const v of [c.name, c.state, c.lede, c.homes.intro, c.climate.intro, c.family]) expect(nonEmpty(v)).toBe(true);
      expect(c.homes.points.length).toBeGreaterThan(1);
      expect(c.climate.points.length).toBeGreaterThan(1);
      expect(c.firstChecks.length).toBeGreaterThan(1);
      expect(c.metaTitle.length).toBeLessThanOrEqual(60);
      expect(c.metaDescription.length).toBeLessThanOrEqual(155);
      expect(Boolean(c.blogSlug)).toBe(Boolean(c.blogTitle));
    }
  });

  it("has genuinely different copy per city", () => {
    for (const key of ["lede", "family"] as const) {
      const vals = SEO_CITIES.map((c) => c[key]);
      expect(new Set(vals).size).toBe(vals.length);
    }
    const intros = SEO_CITIES.map((c) => c.homes.intro + c.climate.intro);
    expect(new Set(intros).size).toBe(intros.length);
  });

  it("never claims a local office, address or response time", () => {
    const text = JSON.stringify(SEO_CITIES).toLowerCase();
    for (const banned of ["our office", "branch", "address", "within 30", "minutes", "hospital partner"]) {
      expect(text).not.toContain(banned);
    }
  });
});

describe("SEO service pages and FAQ", () => {
  it("services have unique slugs and meta within limits", () => {
    expect(new Set(SEO_SERVICES.map((s) => s.slug)).size).toBe(SEO_SERVICES.length);
    for (const s of SEO_SERVICES) {
      expect(s.metaTitle.length).toBeLessThanOrEqual(60);
      expect(s.metaDescription.length).toBeLessThanOrEqual(155);
      expect(s.sections.length).toBeGreaterThanOrEqual(4);
    }
  });

  it("FAQ has 20-25 unique questions in six groups", () => {
    expect(SEO_FAQ_GROUPS).toHaveLength(6);
    expect(SEO_FAQ_ALL.length).toBeGreaterThanOrEqual(20);
    expect(SEO_FAQ_ALL.length).toBeLessThanOrEqual(25);
    expect(new Set(SEO_FAQ_ALL.map((f) => f.q)).size).toBe(SEO_FAQ_ALL.length);
  });
});
