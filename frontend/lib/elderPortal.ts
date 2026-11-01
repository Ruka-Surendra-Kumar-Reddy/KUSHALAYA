import {
  api,
  authFromLoginResponse,
  storeAuth,
  type AuthUser,
} from "./api";
import { isElderPortalRole } from "./auth";
import { applyTheme, storeBranding } from "./branding";

export type ElderPortalMe = {
  user_id: number;
  email: string;
  first_name: string;
  last_name: string;
  portal_relationship: string | null;
  elder_id: number;
  tenant_id: number;
  tenant_name: string;
  portal_title: string;
  logo_url: string | null;
  theme: string;
};

export type CareStatus = {
  elder_id: number;
  elder_name: string;
  elder_status: string;
  care_level: string | null;
  mobility_status: string | null;
  assignment_status: string | null;
  caregiver_name: string | null;
  match_score: number | null;
  open_incidents: number;
  unread_notifications: number;
};

export type PortalNotification = {
  id: number;
  title: string;
  body: string;
  read_at: string | null;
  created_at: string;
};

export type PortalMessage = {
  id: number;
  direction: string;
  body: string;
  sender_name: string | null;
  created_at: string;
};

export type ElderActivitySummary = {
  events_last_24h: number;
  open_incidents: number;
  recent_events: {
    id: number;
    event_type: string;
    event_timestamp: string;
    severity: string | null;
    snapshot_url?: string | null;
  }[];
  recent_incidents: {
    id: number;
    incident_type: string;
    severity: string;
    status: string;
    created_at: string;
  }[];
  events_by_type_24h: Record<string, number>;
};

export type TenantOption = { id: number; name: string };

export async function fetchRegisterTenants(): Promise<TenantOption[]> {
  return api<TenantOption[]>("/api/v1/tenants/register-options");
}

export async function registerElderPortal(payload: {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  tenant_id: number;
  phone: string;
  portal_relationship?: string;
}): Promise<AuthUser> {
  const data = await api<
    {
      elder_id?: number | null;
      customer_id?: number | null;
    } & AuthUser
  >("/api/v1/auth/register-elder-portal", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const auth = authFromLoginResponse(data);
  storeAuth(auth);
  const me = await api<{ elder_portal?: ElderPortalMe }>("/api/v1/auth/me");
  if (me.elder_portal) {
    storeBranding({
      id: me.elder_portal.tenant_id,
      name: me.elder_portal.tenant_name,
      portal_title: me.elder_portal.portal_title,
      logo_url: me.elder_portal.logo_url,
      theme: me.elder_portal.theme,
    });
    applyTheme(me.elder_portal.theme);
  }
  return auth;
}

export async function loginElderPortal(
  email: string,
  password: string,
): Promise<AuthUser> {
  const data = await api<{
    access_token: string;
    refresh_token: string;
    email: string;
    role: string;
    tenant_id: number | null;
    elder_id?: number | null;
    customer_id?: number | null;
  }>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (!isElderPortalRole(data.role)) {
    throw new Error("This account is not an elder portal login");
  }
  const auth = authFromLoginResponse(data);
  storeAuth(auth);

  // Branding (tenant name, portal title, logo, theme) is cosmetic and is NOT
  // part of the auth we return, so awaiting it only delays the navigation. On
  // a phone this second round trip was ~0.8s of a ~5s sign-in, spent sitting on
  // "Signing in…". Fire it off and let it land while the dashboard loads; the
  // shell shows its default brand until then.
  void api<{ elder_portal?: ElderPortalMe }>("/api/v1/auth/me")
    .then((me) => {
      if (!me.elder_portal) return;
      storeBranding({
        id: me.elder_portal.tenant_id,
        name: me.elder_portal.tenant_name,
        portal_title: me.elder_portal.portal_title,
        logo_url: me.elder_portal.logo_url,
        theme: me.elder_portal.theme,
      });
      applyTheme(me.elder_portal.theme);
    })
    .catch(() => {
      // A failed branding fetch must never block or fail a valid sign-in.
    });

  return auth;
}

export function elderPortalApi<T>(path: string, options: RequestInit = {}) {
  return api<T>(`/api/v1/elder-portal${path}`, options);
}

export async function fetchElderMe() {
  return elderPortalApi<ElderPortalMe>("/me");
}

export async function fetchCareStatus() {
  return elderPortalApi<CareStatus>("/status");
}

export async function fetchElderActivity() {
  return elderPortalApi<ElderActivitySummary>("/activity");
}

export async function createElderPortalAccount(
  elderId: number,
  payload: {
    email: string;
    password: string;
    first_name?: string;
    last_name?: string;
    portal_relationship?: string;
  },
) {
  return api(`/api/v1/elders/${elderId}/portal-account`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
