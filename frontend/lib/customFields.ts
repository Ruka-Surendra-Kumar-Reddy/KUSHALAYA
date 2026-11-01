import { api } from "./api";
import type { TenantBranding } from "./branding";
import { getStoredBranding, storeBranding } from "./branding";

export type CustomFieldDef = {
  key: string;
  label: string;
  type: string;
  required?: boolean;
  section?: string;
  options?: string[];
};

export type FieldSchemas = {
  elder_fields: CustomFieldDef[];
  caregiver_fields: CustomFieldDef[];
  demand_fields?: CustomFieldDef[];
  supply_fields?: CustomFieldDef[];
};

export type ElderMatchingForm = {
  language_preference: string;
  required_experience_years: string;
  latitude: string;
  longitude: string;
  care_type: string;
  schedule_days: string;
};

export type CaregiverMatchingForm = {
  address: string;
  languages: string;
  latitude: string;
  longitude: string;
  availability_days: string;
  availability_care_type: string;
  average_rating: string;
};

export function parseCommaList(value: string): string[] {
  return value
    .split(/[,;]+/)
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
}

export function coerceFieldValue(
  field: CustomFieldDef,
  raw: string,
): unknown {
  if (field.type === "boolean") return raw === "true" || raw === "1";
  if (field.type === "number") {
    const n = parseFloat(raw);
    return Number.isNaN(n) ? null : n;
  }
  return raw.trim() || null;
}

export function pickTenantCustomValues(
  attrs: Record<string, unknown> | null | undefined,
  schema: CustomFieldDef[],
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const f of schema) {
    const v = attrs?.[f.key];
    if (f.type === "boolean") {
      out[f.key] = v ? "true" : "false";
    } else if (v != null) {
      out[f.key] = String(v);
    } else {
      out[f.key] = "";
    }
  }
  return out;
}

export function splitElderMatching(
  attrs: Record<string, unknown> | null | undefined,
): ElderMatchingForm {
  const sched = attrs?.schedule_requirements as { days?: string[] } | undefined;
  return {
    language_preference: String(attrs?.language_preference ?? ""),
    required_experience_years:
      attrs?.required_experience_years != null
        ? String(attrs.required_experience_years)
        : "",
    latitude: attrs?.latitude != null ? String(attrs.latitude) : "",
    longitude: attrs?.longitude != null ? String(attrs.longitude) : "",
    care_type: String(attrs?.care_type ?? "visit_based"),
    schedule_days: Array.isArray(sched?.days) ? sched.days.join(", ") : "",
  };
}

export function splitCaregiverMatching(
  attrs: Record<string, unknown> | null | undefined,
): CaregiverMatchingForm {
  const avail = attrs?.availability as
    | { days?: string[]; care_type?: string }
    | undefined;
  const langs = attrs?.languages;
  return {
    languages: Array.isArray(langs) ? langs.join(", ") : "",
    address: String(attrs?.address ?? ""),
    latitude: attrs?.latitude != null ? String(attrs.latitude) : "",
    longitude: attrs?.longitude != null ? String(attrs.longitude) : "",
    availability_days: Array.isArray(avail?.days) ? avail.days.join(", ") : "",
    availability_care_type: String(avail?.care_type ?? "visit_based"),
    average_rating:
      attrs?.average_rating != null ? String(attrs.average_rating) : "",
  };
}

export function buildElderCustomAttributes(
  matching: ElderMatchingForm,
  custom: Record<string, string>,
  schema: CustomFieldDef[],
): Record<string, unknown> {
  const out: Record<string, unknown> = {};

  if (matching.language_preference.trim()) {
    out.language_preference = matching.language_preference.trim();
  }
  if (matching.required_experience_years.trim()) {
    const n = parseInt(matching.required_experience_years, 10);
    if (!Number.isNaN(n)) out.required_experience_years = n;
  }
  if (matching.care_type) out.care_type = matching.care_type;
  const days = parseCommaList(matching.schedule_days);
  if (days.length) out.schedule_requirements = { days };

  for (const f of schema) {
    const raw = custom[f.key] ?? "";
    if (!raw && !f.required) continue;
    const val = coerceFieldValue(f, raw);
    if (val != null && val !== "") out[f.key] = val;
  }

  return out;
}

export function buildCaregiverCustomAttributes(
  matching: CaregiverMatchingForm,
  custom: Record<string, string>,
  schema: CustomFieldDef[],
): Record<string, unknown> {
  const out: Record<string, unknown> = {};

  const langs = parseCommaList(matching.languages).map(
    (l) => l.charAt(0).toUpperCase() + l.slice(1),
  );
  if (langs.length) out.languages = langs;
  if (matching.address.trim()) out.address = matching.address.trim();
  const days = parseCommaList(matching.availability_days);
  if (days.length || matching.availability_care_type) {
    out.availability = {
      days: days.length ? days : undefined,
      care_type: matching.availability_care_type || "visit_based",
    };
  }
  if (matching.average_rating.trim()) {
    const n = parseFloat(matching.average_rating);
    if (!Number.isNaN(n)) out.average_rating = n;
  }

  for (const f of schema) {
    const raw = custom[f.key] ?? "";
    if (!raw && !f.required) continue;
    const val = coerceFieldValue(f, raw);
    if (val != null && val !== "") out[f.key] = val;
  }

  return out;
}

export async function fetchFieldSchemas(): Promise<FieldSchemas> {
  return api<FieldSchemas>("/api/v1/tenants/me/field-schemas");
}

export async function updateFieldSchemas(
  payload: Partial<FieldSchemas>,
): Promise<FieldSchemas> {
  const result = await api<FieldSchemas>("/api/v1/tenants/me/field-schemas", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  const stored = getStoredBranding();
  if (stored) {
    storeBranding({
      ...stored,
      elder_field_schema: result.elder_fields,
      caregiver_field_schema: result.caregiver_fields,
    });
  }
  return result;
}

export function schemasFromBranding(
  branding: TenantBranding,
): FieldSchemas {
  return {
    elder_fields: (branding.elder_field_schema || []) as CustomFieldDef[],
    caregiver_fields: (branding.caregiver_field_schema ||
      []) as CustomFieldDef[],
  };
}
