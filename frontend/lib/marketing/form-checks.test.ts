import { describe, expect, it } from "vitest";

import { apiErrorMessage, emailError, phoneError, pincodeError } from "./form-checks";

describe("enquiry form checks (Batch B)", () => {
  it("accepts Indian mobiles and international E.164", () => {
    for (const ok of ["98765 43210", "+91 98765-43210", "09876543210", "+44 7911 123456", "+1 (415) 555-0100", ""]) {
      expect(phoneError(ok)).toBeNull();
    }
    for (const bad of ["12345", "5876543210", "+91 12345 67890", "call me"]) {
      expect(phoneError(bad)).not.toBeNull();
    }
  });

  it("checks email and PIN", () => {
    expect(emailError("a@b.com")).toBeNull();
    expect(emailError("x@y")).not.toBeNull();
    expect(pincodeError("500 081")).toBeNull();
    expect(pincodeError("900001")).not.toBeNull();
    expect(pincodeError("12345")).not.toBeNull();
  });

  it("turns a pydantic 422 into one sentence", () => {
    expect(apiErrorMessage([{ msg: "Value error, Please check the email." }])).toBe("Please check the email.");
    expect(apiErrorMessage("Plain")).toBe("Plain");
  });
});
