import { describe, expect, it } from "vitest";

import { SITE_FALLBACK, leadFromUrl, whatsAppHref, withCompanyFallback } from "./site-config";

describe("lead capture (FIX 107)", () => {
  it("captures UTM, landing page and an outside referrer", () => {
    const t = leadFromUrl(
      "https://www.kushalaya.com/kushcare-discovery?utm_source=google&utm_medium=cpc&utm_campaign=nri",
      "https://www.google.com/",
    );
    expect(t).toEqual({
      utm_source: "google",
      utm_medium: "cpc",
      utm_campaign: "nri",
      referrer: "https://www.google.com/",
      landing_page: "/kushcare-discovery?utm_source=google&utm_medium=cpc&utm_campaign=nri",
    });
  });

  it("ignores our own site as referrer and keeps a valid referral code", () => {
    const t = leadFromUrl("https://www.kushalaya.com/kushcare-discovery?ref=k1abcd", "https://www.kushalaya.com/");
    expect(t.referrer).toBeUndefined();
    expect(t.ref).toBe("K1ABCD");
  });

  it("keeps an allow-listed ?src= and drops anything else", () => {
    expect(leadFromUrl("https://www.kushalaya.com/kushcare-discovery?src=QR", "").src).toBe("qr");
    expect(leadFromUrl("https://www.kushalaya.com/kushcare-discovery?src=evil", "").src).toBeUndefined();
  });

  it("drops a malformed referral code", () => {
    expect(leadFromUrl("https://www.kushalaya.com/?ref=<script>", "").ref).toBeUndefined();
  });
});

describe("site fallback", () => {
  it("shows a free home assessment until Ops sets a price, and has no testimonials", () => {
    expect(SITE_FALLBACK.assessment_price_paise).toBeNull();
    expect(SITE_FALLBACK.assessment_price_label).toBe("Free");
    expect(SITE_FALLBACK.assessment_is_paid).toBe(false);
    expect(SITE_FALLBACK.testimonials).toEqual([]);
    expect(SITE_FALLBACK.trial.enabled).toBe(false);
  });

  it("falls back to the registered company name and address, with no GSTIN", () => {
    const c = withCompanyFallback({ legal_name: "", address: "  ", gstin: "" });
    expect(c.legal_name).toBe("KushAlaya Private Limited");
    expect(c.address).toMatch(/Uppal.*500039, Telangana/);
    expect(c.gstin).toBe("");
    expect(withCompanyFallback({ address: "Somewhere else" }).address).toBe("Somewhere else");
  });

  it("builds a wa.me link with prefilled text", () => {
    expect(whatsAppHref(SITE_FALLBACK, "Hi there")).toBe("https://wa.me/919059051085?text=Hi%20there");
  });
});

describe("site config retry (Batch B)", () => {
  it("does not cache the fallback after a failed fetch, and retries", async () => {
    const { loadSiteConfig, resetSiteConfigCache } = await import("./site-config");
    const { vi } = await import("vitest");
    resetSiteConfigCache();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, json: async () => null })
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ ok: true, json: async () => ({ whatsapp_link: "https://wa.me/911", city: "Pune" }) });
    vi.stubGlobal("fetch", fetchMock);
    try {
      expect((await loadSiteConfig()).city).toBe(SITE_FALLBACK.city);
      expect((await loadSiteConfig()).city).toBe(SITE_FALLBACK.city);
      expect((await loadSiteConfig()).city).toBe("Pune");
      expect((await loadSiteConfig()).city).toBe("Pune");
      expect(fetchMock).toHaveBeenCalledTimes(3);
    } finally {
      vi.unstubAllGlobals();
      resetSiteConfigCache();
    }
  });
});
