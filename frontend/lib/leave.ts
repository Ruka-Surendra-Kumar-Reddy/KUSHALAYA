import { api } from "./api";

export type LeaveRequest = {
  id: number;
  tenant_id: number;
  caregiver_id: number;
  caregiver_name: string | null;
  leave_type: string;
  start_date: string;
  end_date: string;
  reason: string | null;
  status: string;
  resolved_at: string | null;
  resolved_by_user_id: number | null;
  resolution_note: string | null;
  created_at: string | null;
};

export async function fetchMyLeaveRequests(): Promise<LeaveRequest[]> {
  return api<LeaveRequest[]>("/api/v1/caregiver-portal/leave-requests");
}

export async function createLeaveRequest(payload: {
  leave_type: string;
  start_date: string;
  end_date: string;
  reason?: string;
}): Promise<LeaveRequest> {
  return api<LeaveRequest>("/api/v1/caregiver-portal/leave-requests", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function cancelLeaveRequest(requestId: number): Promise<LeaveRequest> {
  return api<LeaveRequest>(
    `/api/v1/caregiver-portal/leave-requests/${requestId}/cancel`,
    { method: "POST" },
  );
}

export async function fetchPendingLeaveRequests(): Promise<LeaveRequest[]> {
  return api<LeaveRequest[]>("/api/v1/workforce/leave-requests?status=PENDING");
}

export async function approveLeaveRequest(requestId: number): Promise<LeaveRequest> {
  return api<LeaveRequest>(
    `/api/v1/workforce/leave-requests/${requestId}/approve`,
    { method: "POST" },
  );
}

export async function rejectLeaveRequest(
  requestId: number,
  reason?: string,
): Promise<LeaveRequest> {
  return api<LeaveRequest>(
    `/api/v1/workforce/leave-requests/${requestId}/reject`,
    {
      method: "POST",
      body: JSON.stringify({ reason }),
    },
  );
}
