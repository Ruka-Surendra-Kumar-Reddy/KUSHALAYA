import { api } from "./api";

export type Geofence = {
  id: number;
  elder_id: number;
  tenant_id: number;
  latitude: number;
  longitude: number;
  radius_meters: number;
};

export type AttendanceRow = {
  id: number;
  assignment_id: number;
  caregiver_id: number;
  elder_id: number;
  checkin_time: string | null;
  checkout_time: string | null;
  visit_duration_minutes: number | null;
  status: string;
  created_at: string;
};

export type AttendanceSummary = {
  total_visits: number;
  checked_in_now: number;
  completed_today: number;
  no_show_today: number;
  average_duration_minutes: number | null;
  on_time_arrivals: number;
  late_arrivals: number;
};

export async function getElderGeofence(elderId: number): Promise<Geofence | null> {
  try {
    return await api<Geofence>(`/api/v1/geofences/elder/${elderId}`);
  } catch {
    return null;
  }
}

export async function saveGeofence(
  elderId: number,
  payload: { latitude: number; longitude: number; radius_meters: number },
  existingId?: number,
): Promise<Geofence> {
  if (existingId) {
    return api<Geofence>(`/api/v1/geofences/${existingId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  }
  return api<Geofence>("/api/v1/geofences", {
    method: "POST",
    body: JSON.stringify({ elder_id: elderId, ...payload }),
  });
}

export async function fetchAttendance(params?: {
  elder_id?: number;
  caregiver_id?: number;
  status?: string;
}): Promise<AttendanceRow[]> {
  const q = new URLSearchParams();
  if (params?.elder_id != null) q.set("elder_id", String(params.elder_id));
  if (params?.caregiver_id != null) q.set("caregiver_id", String(params.caregiver_id));
  if (params?.status) q.set("status", params.status);
  const suffix = q.toString() ? `?${q}` : "";
  return api<AttendanceRow[]>(`/api/v1/attendance${suffix}`);
}

export async function fetchAttendanceSummary(): Promise<AttendanceSummary> {
  return api<AttendanceSummary>("/api/v1/attendance/summary");
}

export type ReplacementSuggestion = {
  caregiver_id: number;
  caregiver_name: string;
  match_score: number;
  reasons: string[];
};

export type ReplacementSuggestionsResponse = {
  elder_id: number;
  elder_name: string | null;
  exclude_caregiver_id: number | null;
  suggestions: ReplacementSuggestion[];
  bench_available: number;
};

export async function fetchReplacementSuggestions(
  attendanceId: number,
  limit = 5,
): Promise<ReplacementSuggestionsResponse> {
  return api<ReplacementSuggestionsResponse>(
    `/api/v1/attendance/${attendanceId}/replacement-suggestions?limit=${limit}`,
  );
}

export type LocationEventResult = {
  id: number;
  event_type: string;
  distance_meters: number | null;
  within_geofence: boolean;
  attendance_id: number | null;
  attendance_status: string | null;
  message: string;
  notifications_sent: number;
};

export async function registerCaregiverDevice(
  caregiverId: number,
  deviceId: string,
  deviceLabel?: string,
): Promise<{ id: number; caregiver_id: number; device_id: string }> {
  return api(`/api/v1/caregivers/${caregiverId}/devices`, {
    method: "POST",
    body: JSON.stringify({
      device_id: deviceId,
      device_label: deviceLabel ?? "Web simulator",
    }),
  });
}

export async function sendLocationEvent(payload: {
  caregiver_id: number;
  elder_id: number;
  event_type: string;
  latitude: number;
  longitude: number;
  accuracy?: number;
  device_id: string;
  assignment_id?: number;
}): Promise<LocationEventResult> {
  return api<LocationEventResult>("/api/v1/location-events", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
