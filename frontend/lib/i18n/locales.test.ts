import { describe, expect, it } from "vitest";

import {
  detectInitialLocale,
  localesForMarket,
  LOCALE_STORAGE_KEY,
  teluguLocaleEnabled,
} from "./index";

describe("localesForMarket", () => {
  it("returns English only for US market", () => {
    expect(localesForMarket("US")).toEqual([
      { id: "en", labelKey: "common.english" },
    ]);
  });

  it("returns English and Telugu for India market", () => {
    expect(localesForMarket("IN")).toHaveLength(2);
    expect(localesForMarket("IN").map((l) => l.id)).toEqual(["en", "te"]);
  });
});

describe("teluguLocaleEnabled", () => {
  it("is disabled for US", () => {
    expect(teluguLocaleEnabled("US")).toBe(false);
  });

  it("is enabled for IN", () => {
    expect(teluguLocaleEnabled("IN")).toBe(true);
  });
});

describe("detectInitialLocale", () => {
  it("forces English for US market even if Telugu stored", () => {
    expect(detectInitialLocale("US", LOCALE_STORAGE_KEY)).toBe("en");
  });
});
