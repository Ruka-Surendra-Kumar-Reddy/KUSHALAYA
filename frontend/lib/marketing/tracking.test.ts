import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/** The little of the browser tracking.ts touches (tests run in node). */
function fakeBrowser() {
  const store = new Map<string, string>();
  const scripts: { src: string; async?: boolean }[] = [];
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => store.set(k, v),
  });
  vi.stubGlobal("window", {});
  vi.stubGlobal("document", {
    createElement: () => ({ src: "" }),
    head: { appendChild: (s: { src: string }) => scripts.push(s) },
  });
  return scripts;
}

async function fresh() {
  vi.resetModules();
  return import("./tracking");
}

describe("ads tracking", () => {
  let scripts: { src: string }[];

  beforeEach(() => {
    scripts = fakeBrowser();
    vi.stubEnv("NEXT_PUBLIC_META_PIXEL_ID", "123");
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_TAG_ID", "G-ABC, AW-999");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("loads nothing before Accept", async () => {
    const t = await fresh();
    t.loadTrackers();
    t.track("lead");
    expect(scripts).toEqual([]);
  });

  it("loads nothing after Decline", async () => {
    const t = await fresh();
    t.setConsent("declined");
    t.loadTrackers();
    expect(scripts).toEqual([]);
  });

  it("loads Meta and Google once after Accept", async () => {
    const t = await fresh();
    t.setConsent("accepted");
    t.loadTrackers();
    t.loadTrackers();
    expect(scripts.map((s) => s.src)).toEqual([
      "https://connect.facebook.net/en_US/fbevents.js",
      "https://www.googletagmanager.com/gtag/js?id=G-ABC",
    ]);
    expect(t.googleTagIds()).toEqual(["G-ABC", "AW-999"]);
  });

  it("stays silent without IDs", async () => {
    vi.stubEnv("NEXT_PUBLIC_META_PIXEL_ID", "");
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_TAG_ID", "");
    const t = await fresh();
    t.setConsent("accepted");
    t.loadTrackers();
    expect(t.trackingConfigured()).toBe(false);
    expect(scripts).toEqual([]);
  });
});
