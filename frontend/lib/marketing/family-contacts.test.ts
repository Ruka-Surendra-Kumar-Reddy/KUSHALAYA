import { describe, expect, it } from "vitest";

import {
  familyContactsConfigured,
  familyPhoneDisplay,
  familyPhoneTelHref,
  familyWhatsAppDigits,
  isExternalFamilyContactHref,
  PARENT_CARE_CHECK_HREF,
} from "./family-contacts";

describe("family contact helpers", () => {
  it("treats http(s) as external", () => {
    expect(isExternalFamilyContactHref("https://wa.me/1")).toBe(true);
    expect(isExternalFamilyContactHref("http://example.com")).toBe(true);
    expect(isExternalFamilyContactHref("/parent-care-check")).toBe(false);
    expect(isExternalFamilyContactHref("tel:+1")).toBe(false);
  });

  it("returns empty digits/display when env unset", () => {
    expect(familyWhatsAppDigits()).toBe("");
    expect(familyPhoneDisplay()).toBe("");
    expect(familyContactsConfigured()).toBe(false);
    expect(familyPhoneTelHref()).toBe(PARENT_CARE_CHECK_HREF);
  });
});
