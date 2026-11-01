/** Same-origin in the browser when unset — avoids mixed-content on HTTPS production. */
import {
  createHttpClient,
  createSessionStore,
  getApiUrl as coreGetApiUrl,
  triggerBlobDownload,
  type AuthSession,
} from "@workforceos/contracts/client";

export type AuthUser = AuthSession & {
  session_id?: string | null;
  /** Sent by the server (session policy); the browser no longer signs people out when idle. */
  idle_minutes?: number | null;
};

export function getApiUrl(): string {
  // The family site proxies /api itself. Calling ops.kushalaya.com from it is
  // cross-origin: every request type paid a CORS preflight and a second TLS
  // connection (~1 s each on mobile networks), which made sign-in slow.
  // Same for the caregiver host (caregiver.kushalaya.com).
  if (
    typeof window !== "undefined" &&
    (window.location.hostname.startsWith("family.") || window.location.hostname.startsWith("caregiver."))
  ) {
    return window.location.origin;
  }
  return coreGetApiUrl("http://127.0.0.1:8010");
}

/** @deprecated Prefer getApiUrl() — may be wrong in client bundles built without NEXT_PUBLIC_API_URL */
export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8010";

import { clearPortalCookie, setPortalCookie } from "./portal-cookie";
import { nativeSignOut } from "./native-app";

const AUTH_KEY = "sho_auth";
const LEGACY_AUTH_KEY = "eco_auth";

const session = createSessionStore(AUTH_KEY);

function migrateLegacyAuth(): void {
  if (typeof window === "undefined") return;
  if (localStorage.getItem(AUTH_KEY)) return;
  const legacy = localStorage.getItem(LEGACY_AUTH_KEY);
  if (!legacy) return;
  localStorage.setItem(AUTH_KEY, legacy);
  localStorage.removeItem(LEGACY_AUTH_KEY);
}

export function getStoredAuth(): AuthUser | null {
  migrateLegacyAuth();
  const auth = session.get() as AuthUser | null;
  // Sessions that predate the routing cookie pick it up on first read, so
  // their next page load is routed on the server like everyone else's.
  if (auth && typeof window !== "undefined") setPortalCookie(auth.role);
  return auth;
}

export function storeAuth(auth: AuthUser) {
  session.set(auth);
  if (typeof window !== "undefined") {
    localStorage.removeItem(LEGACY_AUTH_KEY);
    setPortalCookie(auth.role);
  }
}

export function clearAuth() {
  session.clear();
  nativeSignOut(); // Android app: this phone stops ringing for them
  if (typeof window !== "undefined") {
    localStorage.removeItem(LEGACY_AUTH_KEY);
    clearPortalCookie();
  }
}

const http = createHttpClient({ getApiUrl, getSession: getStoredAuth });

type LoginResponse = {
  access_token: string;
  refresh_token: string;
  email: string;
  role: string;
  tenant_id: number | null;
  elder_id?: number | null;
  customer_id?: number | null;
  caregiver_id?: number | null;
  session_id?: string | null;
  idle_minutes?: number | null;
};

/** Map elder-care login payload to shared AuthSession (customer_id spine). */
export function authFromLoginResponse(data: LoginResponse): AuthUser {
  return {
    access_token: data.access_token,
    refresh_token: data.refresh_token,
    email: data.email,
    role: data.role,
    tenant_id: data.tenant_id,
    customer_id: data.customer_id ?? data.elder_id ?? null,
    caregiver_id: data.caregiver_id ?? null,
    session_id: data.session_id ?? null,
    idle_minutes: data.idle_minutes ?? null,
  };
}

function sessionHeaderRecord(): Record<string, string> {
  const auth = getStoredAuth();
  if (!auth?.session_id) return {};
  return { "X-Session-ID": auth.session_id };
}

function withSessionHeaders(init: RequestInit = {}): RequestInit {
  const extra = sessionHeaderRecord();
  if (!Object.keys(extra).length) return init;
  const base =
    init.headers && typeof init.headers === "object" && !(init.headers instanceof Headers)
      ? (init.headers as Record<string, string>)
      : {};
  return {
    ...init,
    headers: {
      ...base,
      ...extra,
    },
  };
}

function formatApiError(data: Record<string, unknown>, statusText: string): string {
  const detail = data.detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => (item as { msg?: string }).msg).join(", ");
  }
  return (detail as string | undefined) || (data.error as string | undefined) || statusText;
}

let refreshInFlight: Promise<boolean> | null = null;

function isAuthFailureMessage(message: string): boolean {
  const m = message.toLowerCase();
  return (
    m === "invalid token" ||
    m === "user not found" ||
    m.includes("not authenticated") ||
    m.includes("could not validate credentials")
  );
}

async function tryRefreshSession(): Promise<boolean> {
  const auth = getStoredAuth();
  if (!auth?.refresh_token) return false;
  try {
    const res = await fetch(`${getApiUrl()}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: auth.refresh_token }),
    });
    if (!res.ok) return false;
    const data = (await res.json()) as LoginResponse;
    storeAuth(
      authFromLoginResponse({
        ...auth,
        access_token: data.access_token,
        refresh_token: data.refresh_token || auth.refresh_token,
        email: data.email || auth.email,
        role: data.role || auth.role,
        tenant_id: data.tenant_id ?? auth.tenant_id,
        elder_id: data.elder_id,
        customer_id: data.customer_id,
        caregiver_id: data.caregiver_id,
        session_id: data.session_id ?? auth.session_id,
        idle_minutes: data.idle_minutes ?? auth.idle_minutes,
      }),
    );
    return true;
  } catch {
    return false;
  }
}

function redirectToLogin(): void {
  if (typeof window === "undefined") return;
  const path = window.location.pathname;
  if (path.startsWith("/login") || path.startsWith("/kushalaya/family/login") || path.startsWith("/kushalaya/family/login")) {
    return;
  }
  const next = `${path}${window.location.search || ""}`;
  window.location.replace(`/login?next=${encodeURIComponent(next)}`);
}

async function withAuthRetry<T>(
  path: string,
  run: () => Promise<T>,
): Promise<T> {
  try {
    return await run();
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    const skipRefresh =
      path.startsWith("/api/v1/auth/login") ||
      path.startsWith("/api/v1/auth/register") ||
      path.startsWith("/api/v1/auth/refresh");
    if (skipRefresh || !isAuthFailureMessage(message)) {
      throw err;
    }
    if (!refreshInFlight) {
      refreshInFlight = tryRefreshSession().finally(() => {
        refreshInFlight = null;
      });
    }
    const refreshed = await refreshInFlight;
    if (refreshed) {
      return await run();
    }
    clearAuth();
    redirectToLogin();
    throw err;
  }
}

export async function api<T = unknown>(
  path: string,
  requestInit: RequestInit = {},
): Promise<T> {
  return withAuthRetry(path, () => http.api<T>(path, withSessionHeaders(requestInit)));
}

export async function downloadFileBlob(
  path: string,
  options: { method?: string; body?: string } = {},
): Promise<Blob> {
  return withAuthRetry(path, () =>
    http.downloadFileBlob(path, {
      ...options,
      // downloadFileBlob may not accept headers — session still on subsequent api() calls
    }),
  );
}

export async function postFormData<T = unknown>(
  path: string,
  formData: FormData,
): Promise<T> {
  return withAuthRetry(path, async () => {
    const auth = getStoredAuth();
    const headers: Record<string, string> = {
      ...sessionHeaderRecord(),
    };
    if (auth?.access_token) {
      headers.Authorization = `Bearer ${auth.access_token}`;
    }
    const res = await fetch(`${getApiUrl()}${path}`, {
      method: "POST",
      headers,
      body: formData,
    });
    const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
    if (!res.ok) {
      throw new Error(formatApiError(data, res.statusText));
    }
    return data as T;
  });
}

export { triggerBlobDownload };

export async function endSessionRemote(): Promise<void> {
  const auth = getStoredAuth();
  if (!auth?.access_token || !auth.session_id) return;
  try {
    await api("/api/v1/auth/logout", { method: "POST" });
  } catch {
    /* best-effort */
  }
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const data = await api<LoginResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  const auth = authFromLoginResponse(data);
  storeAuth(auth);
  if (data.role === "ELDER_PORTAL") {
    const me = await api<{
      elder_portal?: {
        tenant_id: number;
        tenant_name: string;
        portal_title: string;
        logo_url: string | null;
        theme: string;
      };
    }>("/api/v1/auth/me");
    const { applyTheme, storeBranding } = await import("./branding");
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
  } else if (data.role !== "CAREGIVER") {
    // Same reasoning as the family portal: branding is cosmetic, is not part of
    // `auth`, and awaiting it here just holds the user on the sign-in button.
    void import("./branding")
      .then(({ clearBranding, loadBrandingFromApi }) => {
        clearBranding();
        return loadBrandingFromApi();
      })
      .catch(() => {});
  }
  return auth;
}

export async function registerTenant(payload: Record<string, unknown>) {
  const data = await api<{
    access_token: string;
    refresh_token: string;
    email: string;
    role: string;
    tenant_id: number | null;
  }>("/api/v1/auth/register-tenant", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const auth: AuthUser = { ...data };
  storeAuth(auth);
  const { clearBranding, loadBrandingFromApi } = await import("./branding");
  clearBranding();
  await loadBrandingFromApi();
  return auth;
}

type Me = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  tenant_id: number | null;
};

/** The profile menu, branding and care plan each asked for /auth/me on page load:
 *  three round trips to the server. Callers within a few seconds share one. */
const ME_SHARE_MS = 5000;
let meShared: { token: string | undefined; at: number; p: Promise<Me> } | null = null;

export async function fetchMe(): Promise<Me> {
  const token = getStoredAuth()?.access_token;
  if (meShared && meShared.token === token && Date.now() - meShared.at < ME_SHARE_MS) return meShared.p;
  const p = api<Me>("/api/v1/auth/me");
  const entry = { token, at: Date.now(), p };
  meShared = entry;
  p.catch(() => {
    if (meShared === entry) meShared = null;
  });
  return p;
}

export async function downloadDocumentBlob(documentId: number): Promise<Blob> {
  const auth = getStoredAuth();
  const res = await fetch(
    `${getApiUrl()}/api/v1/documents/${documentId}/download`,
    {
      headers: auth?.access_token
        ? { Authorization: `Bearer ${auth.access_token}` }
        : {},
    },
  );
  if (!res.ok) throw new Error("Download failed");
  return res.blob();
}

export async function uploadDocument(formData: FormData) {
  return postFormData("/api/v1/documents/upload", formData);
}

export function documentDownloadUrl(documentId: number): string {
  return `${getApiUrl()}/api/v1/documents/${documentId}/download`;
}
