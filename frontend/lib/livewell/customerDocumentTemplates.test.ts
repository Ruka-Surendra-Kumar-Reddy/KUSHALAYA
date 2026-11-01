import { describe, expect, it } from "vitest";
import type { CustomerDocFillContext } from "./customerDocumentTemplates";
import { emergencyInfoSheetChecklist, fillContextFromAssessment } from "./customerDocumentTemplates";

describe("Emergency Information Sheet fill", () => {
  it("lists missing required fields", () => {
    const ctx = fillContextFromAssessment({
      id: "a1",
      clientFirstName: "",
      clientLastName: "",
      clientAddress: "",
      clientPhone: "",
      familyContactName: "",
      familyContactPhone: "",
      assessorName: "Ada",
      residentProfile: {},
    });
    const check = emergencyInfoSheetChecklist(ctx);
    expect(check.ready).toBe(false);
    expect(check.missing.length).toBeGreaterThan(0);
  });

  it("is ready when core fields are present", () => {
    const ctx: CustomerDocFillContext = fillContextFromAssessment({
      id: "a1",
      clientFirstName: "Rama",
      clientLastName: "Rao",
      clientAddress: "Hyderabad",
      clientPhone: "9000000000",
      familyContactName: "Sita",
      familyContactPhone: "9111111111",
      assessorName: "Ada",
      residentProfile: {
        allergies: "None",
        preferredHospital: "Apollo",
        primaryContact: "Sita",
      },
    });
    const check = emergencyInfoSheetChecklist(ctx);
    expect(check.ready).toBe(true);
    expect(ctx.primaryContactName).toContain("Sita");
    expect(ctx.preferredHospital).toContain("Apollo");
  });
});
