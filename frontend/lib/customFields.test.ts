import { describe, expect, it } from "vitest";

import {
  buildCaregiverCustomAttributes,
  buildElderCustomAttributes,
  coerceFieldValue,
  parseCommaList,
  pickTenantCustomValues,
  schemasFromBranding,
  splitCaregiverMatching,
  splitElderMatching,
  type CustomFieldDef,
} from "./customFields";

const schema: CustomFieldDef[] = [
  { key: "diet", label: "Diet", type: "text" },
  { key: "insulin", label: "Insulin", type: "boolean" },
  { key: "visits", label: "Visits", type: "number" },
];

describe("parseCommaList", () => {
  it.each([
    ["", []],
    ["English", ["english"]],
    ["English, Hindi; Telugu", ["english", "hindi", "telugu"]],
    ["  a, , b ", ["a", "b"]],
  ] as const)("%j", (input, expected) => {
    expect(parseCommaList(input)).toEqual([...expected]);
  });
});

describe("coerceFieldValue", () => {
  it("coerces booleans, numbers, and text", () => {
    expect(coerceFieldValue({ key: "x", label: "x", type: "boolean" }, "true")).toBe(true);
    expect(coerceFieldValue({ key: "x", label: "x", type: "boolean" }, "1")).toBe(true);
    expect(coerceFieldValue({ key: "x", label: "x", type: "boolean" }, "false")).toBe(false);
    expect(coerceFieldValue({ key: "x", label: "x", type: "number" }, "3.5")).toBe(3.5);
    expect(coerceFieldValue({ key: "x", label: "x", type: "number" }, "nope")).toBeNull();
    expect(coerceFieldValue({ key: "x", label: "x", type: "text" }, "  Hi ")).toBe("Hi");
    expect(coerceFieldValue({ key: "x", label: "x", type: "text" }, "   ")).toBeNull();
  });
});

describe("pickTenantCustomValues", () => {
  it("stringifies known schema keys", () => {
    expect(
      pickTenantCustomValues({ diet: "soft", insulin: true, visits: 3 }, schema),
    ).toEqual({ diet: "soft", insulin: "true", visits: "3" });
    expect(pickTenantCustomValues(null, schema)).toEqual({
      diet: "",
      insulin: "false",
      visits: "",
    });
  });
});

describe("splitElderMatching", () => {
  it("uses defaults when attrs missing", () => {
    const form = splitElderMatching(undefined);
    expect(form.care_type).toBe("visit_based");
    expect(form.schedule_days).toBe("");
    expect(form.language_preference).toBe("");
  });

  it("maps nested schedule days", () => {
    const form = splitElderMatching({
      language_preference: "English",
      required_experience_years: 4,
      latitude: 17.4,
      longitude: 78.4,
      care_type: "live_in",
      schedule_requirements: { days: ["mon", "wed"] },
    });
    expect(form.required_experience_years).toBe("4");
    expect(form.schedule_days).toBe("mon, wed");
    expect(form.care_type).toBe("live_in");
  });
});

describe("splitCaregiverMatching", () => {
  it("joins languages and availability", () => {
    const form = splitCaregiverMatching({
      languages: ["English", "Hindi"],
      address: "Hyderabad",
      latitude: 1,
      longitude: 2,
      availability: { days: ["fri"], care_type: "live_in" },
      average_rating: 4.5,
    });
    expect(form.languages).toBe("English, Hindi");
    expect(form.availability_days).toBe("fri");
    expect(form.availability_care_type).toBe("live_in");
    expect(form.average_rating).toBe("4.5");
  });
});

describe("buildElderCustomAttributes", () => {
  it("omits empty optional fields and parses days", () => {
    const out = buildElderCustomAttributes(
      {
        language_preference: " English ",
        required_experience_years: "3",
        latitude: "",
        longitude: "",
        care_type: "visit_based",
        schedule_days: "Mon, Wed",
      },
      { diet: "soft", visits: "" },
      schema,
    );
    expect(out.language_preference).toBe("English");
    expect(out.required_experience_years).toBe(3);
    expect(out.schedule_requirements).toEqual({ days: ["mon", "wed"] });
    expect(out.diet).toBe("soft");
    expect(out.visits).toBeUndefined();
  });
});

describe("buildCaregiverCustomAttributes", () => {
  it("title-cases languages and stores availability", () => {
    const out = buildCaregiverCustomAttributes(
      {
        address: " Banjara Hills ",
        languages: "english, hindi",
        latitude: "",
        longitude: "",
        availability_days: "mon",
        availability_care_type: "visit_based",
        average_rating: "4.2",
      },
      { insulin: "true" },
      schema,
    );
    expect(out.languages).toEqual(["English", "Hindi"]);
    expect(out.address).toBe("Banjara Hills");
    expect(out.availability).toEqual({ days: ["mon"], care_type: "visit_based" });
    expect(out.average_rating).toBe(4.2);
    expect(out.insulin).toBe(true);
  });
});

describe("schemasFromBranding", () => {
  it("falls back to empty arrays", () => {
    expect(schemasFromBranding({} as never)).toEqual({
      elder_fields: [],
      caregiver_fields: [],
    });
  });
});
