import { api } from "./api";

export { isCaregiverRole } from "./auth";

export type CaregiverPortalMe = {
  user_id: number;
  email: string;
  first_name: string;
  last_name: string;
  caregiver_id: number;
  tenant_id: number;
  tenant_name: string;
  portal_title: string;
};

export type CaregiverShift = {
  assignment_id: number;
  elder_id: number;
  elder_name: string;
  elder_address: string | null;
  visit_id: number | null;
  visit_status: string | null;
  scheduled_start: string | null;
  scheduled_end: string | null;
  attendance_id: number | null;
  attendance_status: string | null;
  geofence: {
    latitude: number;
    longitude: number;
    radius_meters: number;
    configured: boolean;
  } | null;
};

export type CaregiverLocationResult = {
  id: number;
  event_type: string;
  distance_meters: number | null;
  within_geofence: boolean;
  attendance_id: number | null;
  attendance_status: string | null;
  message: string;
  notifications_sent: number;
};

const DEVICE_KEY = "eco_caregiver_device_id";

export function getOrCreateDeviceId(): string {
  if (typeof window === "undefined") return "web-device-unknown";
  let id = localStorage.getItem(DEVICE_KEY);
  if (!id || id.length < 8) {
    id = `web-${crypto.randomUUID().replace(/-/g, "").slice(0, 20)}`;
    localStorage.setItem(DEVICE_KEY, id);
  }
  return id;
}

export async function fetchCaregiverMe(): Promise<CaregiverPortalMe> {
  return api<CaregiverPortalMe>("/api/v1/caregiver-portal/me");
}

export async function fetchShiftsToday(): Promise<CaregiverShift[]> {
  return api<CaregiverShift[]>("/api/v1/caregiver-portal/shifts/today");
}

export async function registerCaregiverPortalDevice(
  deviceId: string,
  deviceLabel?: string,
): Promise<void> {
  await api("/api/v1/caregiver-portal/device", {
    method: "POST",
    body: JSON.stringify({
      device_id: deviceId,
      device_label: deviceLabel ?? "Caregiver PWA",
    }),
  });
}

export async function sendCaregiverLocationEvent(payload: {
  elder_id: number;
  event_type: string;
  latitude: number;
  longitude: number;
  accuracy?: number;
  device_id: string;
  assignment_id?: number;
}): Promise<CaregiverLocationResult> {
  return api<CaregiverLocationResult>("/api/v1/caregiver-portal/location-events", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createCaregiverPortalAccount(
  caregiverId: number,
  payload: { email: string; password: string; first_name?: string; last_name?: string },
) {
  return api(`/api/v1/caregivers/${caregiverId}/portal-account`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getCurrentPosition(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Geolocation is not supported on this device"));
      return;
    }
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true,
      timeout: 20000,
      maximumAge: 0,
    });
  });
}

/** Wait for the best GPS fix (up to ~15s) — helps mobile browsers before check-in. */
export async function getBestPosition(
  maxWaitMs = 15000,
): Promise<GeolocationPosition> {
  if (!navigator.geolocation) {
    throw new Error("Geolocation is not supported on this device");
  }

  return new Promise((resolve, reject) => {
    let best: GeolocationPosition | null = null;
    let settled = false;

    const finish = (pos: GeolocationPosition) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timer);
      navigator.geolocation.clearWatch(watchId);
      resolve(pos);
    };

    const fail = (err: GeolocationPositionError) => {
      if (settled) return;
      if (best) {
        finish(best);
        return;
      }
      settled = true;
      window.clearTimeout(timer);
      navigator.geolocation.clearWatch(watchId);
      reject(new Error(err.message || "Could not get location"));
    };

    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        if (!best || pos.coords.accuracy < best.coords.accuracy) {
          best = pos;
        }
        if (pos.coords.accuracy <= 35) {
          finish(pos);
        }
      },
      fail,
      { enableHighAccuracy: true, maximumAge: 0, timeout: maxWaitMs },
    );

    const timer = window.setTimeout(() => {
      if (best) {
        finish(best);
      } else {
        navigator.geolocation.getCurrentPosition(
          finish,
          fail,
          { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 },
        );
      }
    }, maxWaitMs);
  });
}
