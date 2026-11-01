import { api, postFormData } from "@/lib/api";
import type { SafeHomeVisit } from "@/lib/livewell/visit-types";

/** Mirrors backend/app/livewell/client_profile.py. */

export type ClientPerson = {
  id: number;
  first_name: string;
  last_name: string;
  date_of_birth: string | null;
  gender: string | null;
  phone: string | null;
  address: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  medical_conditions: string | null;
  allergies: string | null;
  mobility_status: string | null;
  care_level: string | null;
  status: string | null;
  created_at: string | null;
};

export type ClientReceipt = {
  id: string;
  receipt_number: string;
  date: string | null;
  kind_label: string;
  description: string;
  amount_minor: number;
  amount_display: string;
  status: string;
  payment_method?: string | null;
  payment_reference?: string | null;
};

export type ClientProfile = {
  person: ClientPerson;
  manager_user_id?: number | null;
  manager_name?: string;
  /** Six-monthly reassessment: due 182 days after the last completed assessment. */
  reassessment?: {
    last_assessed_at: string | null;
    due_at: string | null;
    booked_job_id: number | null;
    booked_at: string | null;
    overdue: boolean;
    needs_first: boolean;
  };
  assessments?: {
    id: string;
    status: string;
    score: number | null;
    assessor: string;
    completed_at: string | null;
    updated_at: string | null;
  }[];
  home_location: HomeLocation | null;
  /** Where the address geocoded when the client was saved (absent if it never did). */
  address_point?: { lat: number; lng: number } | null;
  /** "Good", or "High risk — 2 critical findings" (tenant's own bands). */
  score_band?: string | null;
  safety_score: { total?: number; max_total?: number; grade_label?: string; assessed_at?: string } | null;
  care_pathway: { membership_name?: string; ecm_recommended?: boolean } | null;
  care_status: { level?: string; headline?: string; stability_score?: number | null } | null;
  family: { id: number; name: string; email: string; relationship: string | null; is_primary: boolean }[];
  visits: SafeHomeVisit[];
  feedback: {
    family_average: number | null;
    family_count: number;
    staff_average: number | null;
    staff_count: number;
  };
  wallet: { balance_minor: number; currency: string; status: string };
  receipts: ClientReceipt[];
  service_requests: {
    id: string;
    title?: string;
    service_name?: string;
    status?: string;
    created_at?: string;
    preferred_date?: string;
  }[];
  incidents: {
    id: number;
    kind: string;
    severity: string;
    status: string;
    opened_at: string | null;
    resolved_at: string | null;
    outcome: string | null;
    note: string | null;
  }[];
  devices: {
    id: number;
    label: string;
    device_type: string;
    kind?: string;
    battery_level: number | null;
    online: boolean;
    last_seen_at: string | null;
  }[];
  documents: {
    id: number;
    document_type: string;
    name: string;
    mime_type: string | null;
    uploaded_at: string | null;
    is_photo: boolean;
  }[];
  messages: { count: number; latest: { id: string; body: string; sender_role: string; sender_name: string; created_at: string }[] };
};

export type HomeLocation = { lat: number; lng: number; radius_m: number };

export function saveHomeLocation(elderId: number, payload: HomeLocation) {
  return api<HomeLocation>(`/api/v1/home-safety/clients/${elderId}/home-location`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

/** Best-effort street address for a point (OpenStreetMap Nominatim). Never throws. */
export async function reverseGeocode(lat: number, lng: number): Promise<string> {
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=17&lat=${lat}&lon=${lng}`,
      { headers: { Accept: "application/json" } },
    );
    if (!res.ok) return "";
    const data = (await res.json()) as { display_name?: string };
    return (data.display_name || "").split(",").slice(0, 4).join(",").trim();
  } catch {
    return "";
  }
}

export function fetchClientProfile(elderId: number) {
  return api<ClientProfile>(`/api/v1/home-safety/clients/${elderId}/profile`);
}

export function addVisitStaffFeedback(
  elderId: number,
  visitId: string,
  payload: { rating: number; comment: string },
) {
  return api<SafeHomeVisit>(
    `/api/v1/home-safety/visits/${elderId}/${encodeURIComponent(visitId)}/staff-feedback`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function attachVisitPhotos(elderId: number, visitId: string, photoIds: number[]) {
  return api<SafeHomeVisit>(
    `/api/v1/home-safety/visits/${elderId}/${encodeURIComponent(visitId)}/photos`,
    { method: "POST", body: JSON.stringify({ photo_ids: photoIds }) },
  );
}

/** Upload one visit photo against the client; returns the document id. */
export async function uploadVisitPhoto(elderId: number, file: File): Promise<number> {
  const form = new FormData();
  form.append("file", file);
  form.append("elder_id", String(elderId));
  form.append("caption", "Visit photo");
  const doc = await postFormData<{ id: number }>("/api/v1/home-safety/photos", form);
  return doc.id;
}

export type CapturedLocation = { lat: number; lng: number; accuracy_m?: number; captured_at: string };

/** One GPS fix from the browser. Rejects with a readable reason. */
export function captureLocation(timeoutMs = 12000): Promise<CapturedLocation> {
  return new Promise((resolve, reject) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      reject(new Error("This device cannot share its location."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        resolve({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          accuracy_m: Math.round(pos.coords.accuracy),
          captured_at: new Date(pos.timestamp).toISOString(),
        }),
      (err) =>
        reject(
          new Error(
            err.code === err.PERMISSION_DENIED
              ? "Location permission was denied. Allow it in the browser to record where the visit happened."
              : "Could not get a location fix. Move near a window and try again.",
          ),
        ),
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 60000 },
    );
  });
}

export function mapsLink(lat: number, lng: number): string {
  return `https://www.google.com/maps?q=${lat},${lng}`;
}

export function formatPaise(minor: number): string {
  return `₹${(minor / 100).toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

/** Fields staff can change from "Edit details" (PUT /api/v1/elders/{id}, team-scoped). */
export type ClientDetails = Partial<
  Pick<
    ClientPerson,
    | "phone"
    | "address"
    | "date_of_birth"
    | "gender"
    | "emergency_contact_name"
    | "emergency_contact_phone"
    | "medical_conditions"
    | "allergies"
    | "mobility_status"
  >
>;

export function updateClientDetails(elderId: number, payload: ClientDetails) {
  return api<ClientPerson>(`/api/v1/elders/${elderId}`, { method: "PUT", body: JSON.stringify(payload) });
}

/** Mirrors backend client_profile.client_assessments. */
export type ClientAssessmentRow = {
  id: string;
  status: "completed" | "in_progress";
  status_label: string;
  date: string | null;
  score: number | null;
  band: string | null;
  assessor: string;
  job_id: number | null;
  change: number | null;
};
export type ClientAssessments = {
  assessments: ClientAssessmentRow[];
  booked: { job_id: number; scheduled_at: string | null; status: string; title: string; started: boolean }[];
  compare: {
    now: { id: string; score: number | null; date: string | null };
    before: { id: string; score: number | null; date: string | null };
    areas: { area: string; before: number; now: number; change: number }[];
  } | null;
};

export function fetchClientAssessments(elderId: number) {
  return api<ClientAssessments>(`/api/v1/home-safety/clients/${elderId}/assessments`);
}

export type FamilyLogin = {
  id: number;
  email: string;
  name: string;
  relationship: string;
  active: boolean;
  last_seen_at?: string | null;
  sign_ins_30d?: number;
};

export function fetchFamilyLogins(elderId: number) {
  return api<FamilyLogin[]>(`/api/v1/team/clients/${elderId}/family-logins`);
}

export function addFamilyLogin(
  elderId: number,
  payload: { name: string; relationship: string; email: string; password: string },
) {
  return api(`/api/v1/team/clients/${elderId}/family-logins`, { method: "POST", body: JSON.stringify(payload) });
}

export function resetFamilyPassword(elderId: number, userId: number, password: string) {
  return api(`/api/v1/team/clients/${elderId}/family-logins/${userId}/password`, {
    method: "PUT",
    body: JSON.stringify({ password }),
  });
}

export function setFamilyLoginActive(elderId: number, userId: number, active: boolean) {
  return api<{ id: number; active: boolean }>(`/api/v1/team/clients/${elderId}/family-logins/${userId}/status`, {
    method: "PUT",
    body: JSON.stringify({ active }),
  });
}

/** A readable 10-character password (no look-alike characters), without modulo bias. */
export function generatePassword(length = 10): string {
  const chars = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789";
  const limit = 256 - (256 % chars.length); // reject bytes that would favour early characters
  let out = "";
  while (out.length < length) {
    const buf = new Uint8Array(32);
    crypto.getRandomValues(buf);
    for (const b of buf) if (b < limit && out.length < length) out += chars[b % chars.length];
  }
  return out;
}
