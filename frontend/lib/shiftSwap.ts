import { api } from "./api";

export type ShiftSwapRequest = {
  id: number;
  tenant_id: number;
  visit_id: number;
  requesting_caregiver_id: number;
  requesting_caregiver_name: string | null;
  replacement_caregiver_id: number | null;
  replacement_caregiver_name: string | null;
  elder_id: number | null;
  elder_name: string | null;
  scheduled_start: string | null;
  scheduled_end: string | null;
  reason: string | null;
  status: string;
  resolved_at: string | null;
  resolution_note: string | null;
  created_at: string | null;
};

export type UpcomingShift = {
  visit_id: number;
  assignment_id: number;
  elder_id: number;
  elder_name: string;
  scheduled_start: string;
  scheduled_end: string;
  status: string;
  pending_swap_id: number | null;
};

export type CoworkerOption = {
  caregiver_id: number;
  name: string;
};

export async function fetchPendingShiftSwaps(): Promise<ShiftSwapRequest[]> {
  return api<ShiftSwapRequest[]>(
    "/api/v1/scheduling/shift-swaps?status=PENDING",
  );
}

export async function approveShiftSwap(
  requestId: number,
  replacementCaregiverId?: number,
): Promise<ShiftSwapRequest> {
  return api<ShiftSwapRequest>(
    `/api/v1/scheduling/shift-swaps/${requestId}/approve`,
    {
      method: "POST",
      body: JSON.stringify({
        replacement_caregiver_id: replacementCaregiverId ?? null,
      }),
    },
  );
}

export async function rejectShiftSwap(
  requestId: number,
  reason?: string,
): Promise<ShiftSwapRequest> {
  return api<ShiftSwapRequest>(
    `/api/v1/scheduling/shift-swaps/${requestId}/reject`,
    {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? null }),
    },
  );
}

export async function fetchUpcomingShifts(days = 14): Promise<UpcomingShift[]> {
  return api<UpcomingShift[]>(
    `/api/v1/caregiver-portal/shifts/upcoming?days=${days}`,
  );
}

export async function fetchCoworkers(): Promise<CoworkerOption[]> {
  return api<CoworkerOption[]>("/api/v1/caregiver-portal/coworkers");
}

export async function requestShiftSwap(payload: {
  visit_id: number;
  replacement_caregiver_id?: number;
  reason?: string;
}): Promise<ShiftSwapRequest> {
  return api<ShiftSwapRequest>("/api/v1/caregiver-portal/shift-swaps", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function cancelShiftSwap(requestId: number): Promise<ShiftSwapRequest> {
  return api<ShiftSwapRequest>(
    `/api/v1/caregiver-portal/shift-swaps/${requestId}/cancel`,
    { method: "POST" },
  );
}
