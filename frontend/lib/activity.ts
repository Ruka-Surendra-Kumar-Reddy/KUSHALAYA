import { api } from "@/lib/api";

export type ActorType = "family" | "assessor" | "staff" | "system";

export type SessionSummary = {
  id: string;
  tenant_id: number | null;
  user_id: number;
  actor_type: ActorType;
  user_email: string;
  user_name: string;
  user_role: string;
  started_at: string;
  last_seen_at: string;
  ended_at: string | null;
  user_agent: string | null;
  ip_address: string | null;
  event_count: number;
  /** Latest plain actions in this session. */
  recent_actions?: string[];
};

export type SessionEvent = {
  id: number;
  session_id: string;
  occurred_at: string;
  event_kind: string;
  action: string;
  method: string | null;
  path: string | null;
  status_code: number | null;
  duration_ms: number | null;
  request_id: string | null;
  entity_type: string | null;
  entity_id: string | null;
  summary: string | null;
  meta: Record<string, unknown> | null;
};

export type SessionDetail = SessionSummary & {
  events: SessionEvent[];
};

export function fetchActivitySessions(params?: {
  actor_type?: ActorType | "";
  limit?: number;
  offset?: number;
}): Promise<SessionSummary[]> {
  const q = new URLSearchParams();
  if (params?.actor_type) q.set("actor_type", params.actor_type);
  if (params?.limit) q.set("limit", String(params.limit));
  if (params?.offset) q.set("offset", String(params.offset));
  const qs = q.toString();
  return api<SessionSummary[]>(`/api/v1/activity/sessions${qs ? `?${qs}` : ""}`);
}

export function fetchActivitySession(sessionId: string): Promise<SessionDetail> {
  return api<SessionDetail>(`/api/v1/activity/sessions/${encodeURIComponent(sessionId)}`);
}
