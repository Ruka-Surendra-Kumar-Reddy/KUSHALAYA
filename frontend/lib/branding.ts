import { publicBrandName, resolvePortalBrandTitle } from "@/lib/public-brand";
import type { AuthUser } from "./api";
import { api, fetchMe, getStoredAuth } from "./api";

import type { CustomFieldDef } from "./customFields";
import { PLATFORM_NAME } from "./platform";
import {
  applyTheme,
  createBrandingStore,
  getStoredBrandingForAuth as coreGetStoredBrandingForAuth,
  normalizeTheme,
  THEME_CATALOG,
  type TenantBrandingBase,
  type ThemeOption,
} from "@workforceos/contracts/branding";

export type TenantBranding = TenantBrandingBase & {
  bench_cost_per_caregiver_month_inr?: number;
  elder_field_schema?: CustomFieldDef[];
  caregiver_field_schema?: CustomFieldDef[];
};

export type { ThemeOption };

const brandingStore = createBrandingStore<TenantBranding>("sho_branding");
const LEGACY_BRANDING_KEY = "eco_branding";

function migrateLegacyBranding(): void {
  if (typeof window === "undefined") return;
  if (localStorage.getItem("sho_branding")) return;
  const legacy = localStorage.getItem(LEGACY_BRANDING_KEY);
  if (!legacy) return;
  localStorage.setItem("sho_branding", legacy);
  localStorage.removeItem(LEGACY_BRANDING_KEY);
}

export const DEFAULT_BRANDING: TenantBranding = {
  id: null,
  name: PLATFORM_NAME,
  portal_title: publicBrandName(),
  logo_url: null,
  theme: "classic",
  platform_name: PLATFORM_NAME,
  vertical: "LIVEWELL360",
  vertical_label: publicBrandName(),
  market: "IN",
  market_label: "India",
  currency: "INR",
  bench_cost_per_caregiver_month_inr: 15_000,
};

export { THEME_CATALOG, applyTheme };

export function getStoredBranding(): TenantBranding | null {
  migrateLegacyBranding();
  return brandingStore.get();
}

export function getStoredBrandingForAuth(
  auth: AuthUser | null | undefined,
): TenantBranding | null {
  return coreGetStoredBrandingForAuth(auth, brandingStore.get);
}

export function storeBranding(branding: TenantBranding) {
  brandingStore.set(coerceSafeHomeBranding(branding));
}

export function clearBranding() {
  brandingStore.clear();
}

/** SafeHomeOps is single-vertical — never keep Elder Care nav from cached branding. */
function coerceSafeHomeBranding(branding: TenantBranding): TenantBranding {
  const brand = publicBrandName();
  return {
    ...branding,
    vertical: "LIVEWELL360",
    vertical_label: brand,
    portal_title: resolvePortalBrandTitle(branding.portal_title, branding.name),
  };
}

type MeResponse = {
  tenant_id: number | null;
  tenant?: TenantBranding;
};

export async function loadBrandingFromApi(): Promise<TenantBranding> {
  try {
    const me = (await fetchMe()) as MeResponse;
    const branding = coerceSafeHomeBranding(me.tenant || DEFAULT_BRANDING);
    storeBranding(branding);
    applyTheme(normalizeTheme(branding.theme));
    return branding;
  } catch {
    const cached = coerceSafeHomeBranding(
      getStoredBrandingForAuth(getStoredAuth()) || DEFAULT_BRANDING,
    );
    applyTheme(normalizeTheme(cached.theme));
    return cached;
  }
}

export function applyStoredBranding(auth?: AuthUser | null) {
  const b = coerceSafeHomeBranding(
    getStoredBrandingForAuth(auth ?? getStoredAuth()) || DEFAULT_BRANDING,
  );
  applyTheme(normalizeTheme(b.theme));
  return b;
}

export async function fetchThemes(): Promise<ThemeOption[]> {
  return api<ThemeOption[]>("/api/v1/tenants/themes");
}

export async function updateBranding(payload: {
  theme?: string;
  logo_url?: string | null;
  portal_title?: string | null;
  bench_cost_per_caregiver_month_inr?: number;
}): Promise<TenantBranding> {
  const result = await api<TenantBranding>("/api/v1/tenants/me/branding", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  storeBranding(result);
  applyTheme(normalizeTheme(result.theme));
  return result;
}
