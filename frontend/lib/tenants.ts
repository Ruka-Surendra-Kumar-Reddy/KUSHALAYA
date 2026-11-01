import { api } from "./api";
import type { TenantBranding } from "./branding";
import type { CustomFieldDef, FieldSchemas } from "./customFields";
import { normalizeVertical, type VerticalId } from "./platform";
import type { MarketInfo } from "./markets";
import type { Tenant, VerticalInfo } from "./types";

/** API may return any string — always normalize before form state or nav gating. */
export function tenantVerticalId(
  tenant: Pick<Tenant, "vertical">,
): VerticalId {
  return normalizeVertical(tenant.vertical);
}

export type TenantWritePayload = Partial<
  Omit<Tenant, "vertical"> & { vertical?: VerticalId }
>;

export async function fetchVerticals(): Promise<VerticalInfo[]> {
  return api<VerticalInfo[]>("/api/v1/tenants/verticals");
}

export async function fetchMarkets(): Promise<MarketInfo[]> {
  return api<MarketInfo[]>("/api/v1/tenants/markets");
}

export async function fetchTenant(id: number): Promise<Tenant> {
  return api<Tenant>(`/api/v1/tenants/${id}`);
}

export async function fetchTenantBranding(id: number): Promise<TenantBranding> {
  return api<TenantBranding>(`/api/v1/tenants/${id}/branding`);
}

export async function updateTenant(
  id: number,
  payload: TenantWritePayload,
): Promise<Tenant> {
  return api<Tenant>(`/api/v1/tenants/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function updateTenantBranding(
  id: number,
  payload: {
    theme?: string;
    logo_url?: string | null;
    portal_title?: string | null;
    bench_cost_per_caregiver_month_inr?: number;
  },
): Promise<TenantBranding> {
  return api<TenantBranding>(`/api/v1/tenants/${id}/branding`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function fetchTenantFieldSchemas(id: number): Promise<FieldSchemas> {
  return api<FieldSchemas>(`/api/v1/tenants/${id}/field-schemas`);
}

export async function updateTenantFieldSchemas(
  id: number,
  payload: Partial<{
    elder_fields: CustomFieldDef[];
    caregiver_fields: CustomFieldDef[];
    demand_fields: CustomFieldDef[];
    supply_fields: CustomFieldDef[];
  }>,
): Promise<FieldSchemas> {
  return api<FieldSchemas>(`/api/v1/tenants/${id}/field-schemas`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export type TenantDeleteResult = {
  tenant_id: number;
  tenant_name: string;
  deleted_counts: Record<string, number>;
};

export async function deleteTenant(
  id: number,
  confirmName: string,
): Promise<TenantDeleteResult> {
  return api<TenantDeleteResult>(`/api/v1/tenants/${id}`, {
    method: "DELETE",
    body: JSON.stringify({ confirm_name: confirmName }),
  });
}
