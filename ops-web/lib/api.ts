const AUTH_KEY = "sho_auth";
const STAFF_ROLES = new Set(["SYSTEM_ADMIN", "TENANT_ADMIN", "CARE_MANAGER", "VIEWER"]);
const WRITE_ROLES = new Set(["SYSTEM_ADMIN", "TENANT_ADMIN", "CARE_MANAGER"]);

export type AuthUser = {
  access_token: string;
  refresh_token: string;
  email: string;
  role: string;
  tenant_id: number | null;
  customer_id?: number | null;
  caregiver_id?: number | null;
  session_id?: string | null;
};

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
};

export function getApiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8010";
}

export function getLegacyAppUrl(): string {
  return process.env.NEXT_PUBLIC_LEGACY_APP_URL || "http://127.0.0.1:3010";
}

export function getStoredAuth(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function storeAuth(auth: AuthUser) {
  localStorage.setItem(AUTH_KEY, JSON.stringify(auth));
}

export function clearAuth() {
  localStorage.removeItem(AUTH_KEY);
}

export function isStaffRole(role: string) {
  return STAFF_ROLES.has(role);
}

export function canWrite(role: string) {
  return WRITE_ROLES.has(role);
}

export function roleLabel(role: string) {
  if (role === "SYSTEM_ADMIN") return "Super admin";
  if (role === "TENANT_ADMIN") return "Admin";
  if (role === "CARE_MANAGER") return "Manager";
  if (role === "VIEWER") return "Viewer";
  return role;
}

function formatApiError(data: Record<string, unknown>, statusText: string): string {
  const detail = data.detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => (item as { msg?: string }).msg).filter(Boolean).join(", ");
  }
  return (detail as string | undefined) || (data.error as string | undefined) || statusText;
}

export async function api<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const auth = getStoredAuth();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  if (auth?.access_token) headers.Authorization = `Bearer ${auth.access_token}`;
  if (auth?.session_id) headers["X-Session-ID"] = auth.session_id;

  const res = await fetch(`${getApiUrl()}${path}`, { ...init, headers });
  const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (!res.ok) {
    throw new Error(formatApiError(data, res.statusText));
  }
  return data as T;
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const data = await api<LoginResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  const auth: AuthUser = {
    access_token: data.access_token,
    refresh_token: data.refresh_token,
    email: data.email,
    role: data.role,
    tenant_id: data.tenant_id,
    customer_id: data.customer_id ?? data.elder_id ?? null,
    caregiver_id: data.caregiver_id ?? null,
    session_id: data.session_id ?? null,
  };
  storeAuth(auth);
  return auth;
}

export async function logout() {
  try {
    await api("/api/v1/auth/logout", { method: "POST" });
  } catch {
    /* ignore */
  }
  clearAuth();
}
