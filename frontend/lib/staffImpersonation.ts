import {
  api,
  authFromLoginResponse,
  getStoredAuth,
  storeAuth,
  type AuthUser,
} from "./api";
import { isStaffRole } from "./auth";

const STAFF_BACKUP_KEY = "sho_staff_backup";

function backupKey(): string {
  return STAFF_BACKUP_KEY;
}

export function backupStaffSession(): void {
  if (typeof window === "undefined") return;
  const current = getStoredAuth();
  if (current && isStaffRole(current.role)) {
    localStorage.setItem(backupKey(), JSON.stringify(current));
  }
}

export function hasStaffBackup(): boolean {
  if (typeof window === "undefined") return false;
  return Boolean(localStorage.getItem(backupKey()));
}

export function restoreStaffSession(): boolean {
  if (typeof window === "undefined") return false;
  const raw = localStorage.getItem(backupKey());
  if (!raw) return false;
  try {
    const parsed = JSON.parse(raw) as AuthUser;
    if (!parsed?.access_token || !isStaffRole(parsed.role || "")) return false;
    storeAuth(parsed);
    localStorage.removeItem(backupKey());
    return true;
  } catch {
    localStorage.removeItem(backupKey());
    return false;
  }
}

export async function loginAsFamilyClient(elderId: number): Promise<void> {
  backupStaffSession();
  const data = await api<{
    access_token: string;
    refresh_token: string;
    email: string;
    role: string;
    tenant_id: number | null;
    elder_id?: number | null;
    customer_id?: number | null;
    caregiver_id?: number | null;
    session_id?: string | null;
  }>(`/api/v1/elders/${elderId}/login-as-family`, { method: "POST" });
  storeAuth(authFromLoginResponse(data));
  window.location.assign("/kushalaya/family/dashboard");
}
