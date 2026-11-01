import { describe, expect, it } from "vitest";

import { marketCurrency } from "./terminology";

describe("marketCurrency", () => {
  it("returns INR for India and USD for US", () => {
    expect(marketCurrency("IN")).toBe("INR");
    expect(marketCurrency("US")).toBe("USD");
  });
});
