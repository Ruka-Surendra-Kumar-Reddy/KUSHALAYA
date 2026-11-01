import { describe, expect, it } from "vitest";
import { displayName, displayPhone } from "./display-format";

describe("displayName", () => {
  it("title-cases all-lower names only", () => {
    expect(displayName("surendra", "ruka")).toBe("Surendra Ruka");
    expect(displayName("Lakshmi", "Reddy")).toBe("Lakshmi Reddy");
    expect(displayName("krish", "")).toBe("Krish");
  });
});

describe("displayPhone", () => {
  it("shows Indian mobiles one way", () => {
    expect(displayPhone("6304480702")).toBe("+91 63044 80702");
    expect(displayPhone("+91-9000000001")).toBe("+91 90000 00001");
    expect(displayPhone("+916304480702")).toBe("+91 63044 80702");
  });
  it("leaves other numbers as typed", () => {
    expect(displayPhone("040 2345 6789")).toBe("040 2345 6789");
    expect(displayPhone("")).toBe("");
  });
});
