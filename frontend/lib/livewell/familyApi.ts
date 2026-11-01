import { api, postFormData } from "@/lib/api";
import { markPressedHere } from "@/lib/sos-siren";

export type FamilySafetyScore = {
  total: number;
  max_total: number;
  /** Band capped by critical findings: how many urgent fixes (family wording). */
  urgent_fix_count?: number;
  /** The one urgent list: critical findings rated Risk (same as Home's "N critical"). */
  critical_findings?: { id: string; label: string; area: string }[];
  grade: string;
  grade_label: string;
  assessed_at: string | null;
  summary: string | null;
  band_status?: string | null;
  is_demo?: boolean;
  has_published_score?: boolean;
  domain_scores?: FamilyDomainScore[];
  care_pathway?: FamilyCarePathway | null;
};

export type FamilyDomainScore = {
  id: string;
  title: string;
  score: number;
  max_points?: number;
  earned_points?: number;
};

export type FamilyCarePathway = {
  membership_id?: string | null;
  membership_label?: string | null;
  ecm_recommended?: boolean;
  ecm_note?: string | null;
};

export type ScoreHistoryPoint = {
  total: number;
  grade: string;
  assessed_at: string | null;
  assessment_id?: string | null;
};

export type StabilityScorePoint = {
  score: number;
  visited_at: string | null;
  visit_id?: string | null;
  delta_from_baseline?: number | null;
  band?: string | null;
};

export type FamilyPlanItem = {
  id: string;
  title: string;
  priority: string;
  why?: string | null;
  actions: string[];
  score_gain: number;
  status: string;
  domain?: string | null;
  estimated_cost?: string | null;
};

export type FamilyImprovementPlan = {
  assessment_id: string | null;
  current_score: number | null;
  projected_score: number | null;
  finding_count: number;
  published_at: string | null;
  items: FamilyPlanItem[];
  has_plan: boolean;
  estimated_cost_note?: string | null;
};

export type FamilyApprovedVisual = {
  id: string;
  room_type?: string | null;
  package_level?: string | null;
  label: string;
  before_document_id: number;
  after_document_id: number;
  before_url: string;
  after_url: string;
  reviewed_at?: string | null;
  assessment_id?: string | null;
  product_labels?: string[];
  product_codes?: string[];
};

/** Care team phone + WhatsApp families can reach (agency setting). */
export type CareTeamContact = {
  phone: string;
  whatsapp: string;
  phone_tel: string;
  whatsapp_link: string;
  is_default?: boolean;
  emergency: { number: string; label: string }[];
};

export type FamilyDashboard = {
  parent_name: string;
  /** Signed-in family member's first name (greeting); null when unknown. */
  viewer_first_name?: string | null;
  /** The signed-in person is the elder (self account). */
  viewer_is_elder?: boolean;
  senior_name: string;
  senior_address: string | null;
  safety: FamilySafetyScore;
  unread_alerts: number;
  last_visit_at: string | null;
  wellness_count: number;
  visit_count: number;
  has_published_score?: boolean;
  top_priorities?: FamilyPlanItem[];
  plan_item_count?: number;
  projected_score?: number | null;
  stability_score_history?: StabilityScorePoint[];
  stability_score_delta?: number | null;
  latest_stability_score?: number | null;
  approved_visual_count?: number;
  preview_visuals?: FamilyApprovedVisual[];
  domain_scores?: FamilyDomainScore[];
  care_pathway?: FamilyCarePathway | null;
  share_brief?: string | null;
  estimated_cost_note?: string | null;
  next_visit_at?: string | null;
  next_visit_label?: string | null;
  open_incidents?: number;
  unread_messages_hint?: number;
  active_elder_id?: number | null;
  elders?: FamilyLinkedElder[];
  care_status?: FamilyCareStatus | null;
  /** Phase 2E Home. */
  care_team_contact?: CareTeamContact | null;
  last_visit?: {
    id: string;
    visited_at: string;
    visit_type: string;
    staff_name: string | null;
    summary: string | null;
    /** First family-visible photo from that visit, if any. */
    photo?: FamilyVisitPhoto | null;
  } | null;
  needs_you?: { kind: "quote" | "sos" | "alert"; title: string; action: string; href: string }[];
};

export type FamilyCareStatusSnapshot = {
  overall?: string | null;
  mood?: string | null;
  mobility?: string | null;
  eating?: string | null;
  medication?: string | null;
  falls?: string | null;
  home_safety?: string | null;
  open_request?: string | null;
  staff_name?: string | null;
  care_manager_note?: string | null;
  family_message?: string | null;
};

export type FamilyCareStatus = {
  level: "ok" | "needs_attention" | "urgent" | "unknown" | string;
  label: string;
  headline: string;
  headline_suffix?: string;
  senior_first_name?: string;
  reasons?: string[];
  confirmed_at?: string | null;
  snapshot?: FamilyCareStatusSnapshot | null;
  change_summary?: string;
  open_service_requests?: number;
  open_incidents?: number;
  disclaimer?: string;
  computed_at?: string | null;
  stability_score?: number | null;
  stability_delta_from_baseline?: number | null;
  stability_band?: string | null;
};

export type FamilyLinkedElder = {
  id: number;
  name: string;
  address?: string | null;
  is_active: boolean;
  has_published_score?: boolean;
  score_total?: number | null;
};

export type FamilyEldersList = {
  active_elder_id: number | null;
  elders: FamilyLinkedElder[];
  senior_name?: string | null;
};

export type WellnessReport = {
  id: string;
  date: string;
  visit_type: string;
  summary: string;
  assessor_name: string | null;
  highlights: string[];
  family_message?: string | null;
};

export type FamilyVisit = {
  id: string;
  visit_type: string;
  visited_at: string;
  staff_name: string | null;
  partner_id?: string | null;
  partner_name?: string | null;
  summary: string;
  wellness_notes: string;
  family_message?: string | null;
  concerns: string[];
  recommendations: string;
  photo_ids: number[];
  photo_urls: string[];
  duration_minutes: number | null;
  status: string;
  experience_rating?: number | null;
  experience_comment?: string | null;
  rated_at?: string | null;
  can_rate?: boolean;
  checkin?: Record<string, unknown> | null;
  /** #100: voice notes the care manager shared with the family. */
  voice_notes?: { id: number; url: string; duration_s: number | null }[];
  /** Photos the caregiver took on this visit (visit detail only; served via the family image endpoint). */
  photos?: FamilyVisitPhoto[];
  /** Care-job visits: caregiver check-in and finish times. */
  checked_in_at?: string | null;
  checked_out_at?: string | null;
};

export type FamilyVisitPhoto = {
  id: number;
  caption: string;
  taken_at: string | null;
  url: string;
};

export type FamilyPhoto = {
  id: number;
  caption: string;
  url: string | null;
  taken_at: string;
  source?: "assessment" | "monitoring" | string;
};

export type FamilyAlert = {
  id: string;
  title: string;
  body: string;
  severity?: string;
  read_at: string | null;
  created_at: string;
};

/** GET /family/status: one status shared by Home, the digest and details. */
export type FamilyStatus = {
  tone: "ok" | "watch" | "alert";
  word: string;
  changes: string[];
  checks_ok: number;
  checks_total: number;
  checks_text: string;
  changes_text: string;
  last_visit_at: string | null;
  mobility: string;
};

export type FamilyMessage = {
  id: string;
  body: string;
  sender_role: string;
  sender_name: string;
  created_at: string;
};

export type FamilyIncident = {
  id: string;
  kind: string;
  note: string;
  status: string;
  created_at: string;
  resolved_at?: string | null;
  resolved_by?: string | null;
};

export type FamilyDigestPrefs = {
  digest_enabled: boolean;
  digest_channel: string;
  digest_cadence: string;
  digest_timezone: string;
};

export type FamilyCareFeedItem = {
  id: string;
  kind: string;
  title: string;
  body: string;
  created_at: string | null;
  href?: string | null;
  /** Visits only: up to 4 family-visible photos, and how many there are in all. */
  photos?: FamilyVisitPhoto[];
  photo_count?: number;
};

export type FamilyCircleMember = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  portal_relationship: string;
  is_you: boolean;
  is_primary?: boolean;
};

export type FamilyReceipt = {
  id: string;
  receipt_number: string;
  date: string | null;
  kind: string;
  kind_label: string;
  description: string;
  amount_minor: number;
  amount_display: string;
  balance_after_minor?: number | null;
  currency: string;
  status: string;
  payment_method?: string | null;
  payment_reference?: string | null;
  service_request_id?: string | null;
};

export type FamilyDevice = {
  id: number;
  label: string;
  device_type: string;
  kind?: "watch" | "sensor" | "gateway";
  battery_level: number | null;
  online: boolean;
  last_seen_at: string | null;
  offline_seconds: number;
  hub_label?: string | null;
  hub_online?: boolean | null;
  hub_last_seen_at?: string | null;
};

export type FamilyDocument = {
  id: number;
  title: string;
  document_type: string;
  created_at: string | null;
  url: string;
  /** True when the family uploaded it, rather than the care team. */
  uploaded_by_family?: boolean;
};

export type FamilyDocumentType = { id: string; label: string };

export type FamilySchedule = {
  upcoming: FamilyVisit[];
  recent: FamilyVisit[];
};

export type FamilyServiceType = { id: string; label: string; group?: "service" | "product" | "assessment" };

export type FamilyServiceRequest = {
  id: string;
  service_type: string;
  service_label: string;
  group?: string;
  product_name?: string;
  /** The catalog item asked for (ops Products), when the family picked one. */
  product_id?: number | null;
  product_code?: string;
  preferred_at: string | null;
  notes: string;
  status: string;
  created_at: string | null;
  created_by?: string | null;
  staff_note?: string | null;
  visit_id?: string | null;
  quoted_amount_minor?: number;
  quoted_amount_display?: string | null;
  /** not_required | awaiting_approval | paid | refunded */
  payment_status?: string;
  updated_at?: string | null;
};

export type EmergencyContact = {
  name: string;
  phone: string | null;
  relationship: string | null;
  is_primary: boolean;
};

export type PlanItemStatus = "open" | "scheduled" | "done";

export function familyApi<T>(path: string, options: RequestInit = {}) {
  return api<T>(`/api/v1/home-safety/family${path}`, options);
}

/** Care-team phone / WhatsApp — public, so it works before consent or sign-in. */
export function fetchPublicCareTeamContact() {
  return familyApi<CareTeamContact>("/public/care-team-contact");
}

/**
 * The shell and the dashboard page both need this payload (the shell for the
 * wallet chip and alert count, the page for its content) and they mount
 * together, so it was fetched twice on every visit — two identical round trips
 * competing on a phone connection. Concurrent callers now share one request.
 *
 * Deliberately only ~2s: long enough to collapse a single render pass, short
 * enough that navigating back to the dashboard still refetches, so nobody sees
 * stale alerts or a stale balance.
 */
const DASHBOARD_DEDUPE_MS = 2000;
let dashboardInFlight: { at: number; promise: Promise<FamilyDashboard> } | null = null;

export function fetchFamilyDashboard(): Promise<FamilyDashboard> {
  const now = Date.now();
  if (dashboardInFlight && now - dashboardInFlight.at < DASHBOARD_DEDUPE_MS) {
    return dashboardInFlight.promise;
  }
  const promise = familyApi<FamilyDashboard>("/dashboard");
  dashboardInFlight = { at: now, promise };
  // A failure must not be cached, or a transient error sticks for the window.
  promise.catch(() => {
    if (dashboardInFlight?.promise === promise) dashboardInFlight = null;
  });
  return promise;
}

export function fetchFamilyElders() {
  return familyApi<FamilyEldersList>("/elders");
}

export function setActiveFamilyElder(elderId: number) {
  return familyApi<FamilyEldersList>("/elders/active", {
    method: "POST",
    body: JSON.stringify({ elder_id: elderId }),
  });
}

export function fetchFamilySafetyScore() {
  return familyApi<FamilySafetyScore>("/safety-score");
}

export function fetchFamilyImprovementPlan() {
  return familyApi<FamilyImprovementPlan>("/improvement-plan");
}

export function fetchFamilyShareBrief() {
  return familyApi<{ text: string; senior_name: string }>("/share-brief");
}

export function fetchFamilyVisualizations() {
  return familyApi<FamilyApprovedVisual[]>("/visualizations");
}

export function fetchWellnessReports() {
  return familyApi<WellnessReport[]>("/wellness-reports");
}

export function fetchFamilyVisits(days = 60) {
  return familyApi<FamilyVisit[]>(`/visits?days=${days}`);
}

export function fetchFamilySchedule() {
  return familyApi<FamilySchedule>("/schedule");
}

export function fetchFamilyServiceCatalog() {
  return familyApi<FamilyServiceType[]>("/service-catalog");
}

export function fetchFamilyServiceRequests() {
  return familyApi<FamilyServiceRequest[]>("/service-requests");
}

export function createFamilyServiceRequest(payload: {
  service_type: string;
  preferred_at?: string | null;
  notes?: string;
  product_name?: string;
  product_id?: number;
}) {
  return familyApi<FamilyServiceRequest>("/service-requests", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function cancelFamilyServiceRequest(requestId: string) {
  return familyApi<FamilyServiceRequest>(
    `/service-requests/${encodeURIComponent(requestId)}/cancel`,
    { method: "POST" },
  );
}

/** Approve the staff-quoted price — debits the wallet upfront. */
export function payFamilyServiceRequest(requestId: string) {
  return familyApi<FamilyServiceRequest>(
    `/service-requests/${encodeURIComponent(requestId)}/pay`,
    { method: "POST" },
  );
}

export type FamilyWalletBalance = {
  elder_id: number;
  balance_minor: number;
  balance_display: string;
  currency: string;
  status: string;
  min_recharge_minor: number;
  max_recharge_minor: number;
};

export type FamilyWalletTransaction = {
  id: string;
  /** recharge | debit | refund | adjustment */
  kind: string;
  amount_minor: number;
  amount_display: string;
  balance_after_minor?: number | null;
  currency: string;
  /** pending | success | failed */
  status: string;
  reference_type?: string | null;
  reference_id?: string | null;
  note?: string | null;
  created_at?: string | null;
};

export type FamilyWalletRecharge = {
  transaction_id: string;
  order_id: string;
  amount_minor: number;
  currency: string;
  /** razorpay | stub */
  provider: string;
  public_key: string;
  status: string;
};

export function fetchFamilyWallet() {
  return familyApi<FamilyWalletBalance>("/wallet");
}

export function fetchFamilyWalletTransactions(limit = 50) {
  return familyApi<FamilyWalletTransaction[]>(`/wallet/transactions?limit=${limit}`);
}

export function startFamilyWalletRecharge(amountMinor: number) {
  return familyApi<FamilyWalletRecharge>("/wallet/recharge", {
    method: "POST",
    body: JSON.stringify({ amount_minor: amountMinor }),
  });
}

/** Stub-gateway settlement — only available when no real gateway is configured. */
export function settleFamilyWalletRecharge(transactionId: string) {
  return familyApi<FamilyWalletBalance>("/wallet/recharge/settle", {
    method: "POST",
    body: JSON.stringify({ transaction_id: transactionId }),
  });
}

/**
 * Hand the Razorpay Checkout result back for signature verification.
 * The wallet is only credited if the signature matches.
 */
export function verifyFamilyWalletRecharge(payload: {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}) {
  return familyApi<FamilyWalletBalance>("/wallet/recharge/verify", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchStaffServiceRequests(elderId: number) {
  return api<FamilyServiceRequest[]>(
    `/api/v1/home-safety/care/elders/${elderId}/service-requests`,
  );
}

export function updateStaffServiceRequest(
  elderId: number,
  requestId: string,
  payload: { status: string; staff_note?: string },
) {
  return api<FamilyServiceRequest>(
    `/api/v1/home-safety/care/elders/${elderId}/service-requests/${encodeURIComponent(requestId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  );
}

export function fetchFamilyCareFeed() {
  return familyApi<FamilyCareFeedItem[]>("/care-feed");
}

export function fetchFamilyMessages() {
  return familyApi<FamilyMessage[]>("/messages");
}

export function sendFamilyMessage(body: string) {
  return familyApi<FamilyMessage>("/messages", {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}

export function fetchFamilyIncidents() {
  return familyApi<FamilyIncident[]>("/incidents");
}

export function sendFamilySos(note?: string) {
  markPressedHere(); // this device stays quiet for its own SOS; the family's other devices ring
  return familyApi<FamilyIncident>("/sos", {
    method: "POST",
    body: JSON.stringify({ note: note ?? "" }),
  });
}

export function resolveFamilyIncident(incidentId: string, status: "resolved" | "closed" = "resolved") {
  return familyApi<FamilyIncident>(`/incidents/${encodeURIComponent(incidentId)}/resolve`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });
}

export function fetchFamilyDigestPrefs() {
  return familyApi<FamilyDigestPrefs>("/digest-prefs");
}

export function updateFamilyDigestPrefs(payload: Partial<FamilyDigestPrefs>) {
  return familyApi<FamilyDigestPrefs>("/digest-prefs", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function fetchFamilyDigestPreview() {
  return familyApi<{ text: string; prefs: FamilyDigestPrefs; senior_name: string }>(
    "/digest-preview",
  );
}

export function fetchFamilyReceipts() {
  return familyApi<FamilyReceipt[]>("/receipts");
}

export function fetchFamilyReceipt(receiptId: string) {
  return familyApi<FamilyReceipt>(`/receipts/${encodeURIComponent(receiptId)}`);
}

export function fetchFamilyDevices() {
  return familyApi<FamilyDevice[]>("/devices");
}

export function removeFamilyCircleMember(memberId: number) {
  return familyApi<{ id: number; email: string; removed: boolean }>(`/circle/${memberId}`, {
    method: "DELETE",
  });
}

export function fetchFamilyCircle() {
  return familyApi<FamilyCircleMember[]>("/circle");
}

export function inviteFamilyCircleMember(payload: {
  email: string;
  password?: string;
  phone?: string;
  first_name: string;
  last_name: string;
  portal_relationship: string;
  /** The senior selected in the app; the invite is for them only. */
  elder_id?: number | null;
}) {
  return familyApi<FamilyCircleMember>("/circle/invite", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchFamilyDocumentTypes() {
  return familyApi<FamilyDocumentType[]>("/document-types");
}

/** Share a document with the care team — it lands on the client record in ops. */
export function uploadFamilyDocument(payload: {
  file: File;
  documentType: string;
  note?: string;
}) {
  const form = new FormData();
  form.append("file", payload.file);
  form.append("document_type", payload.documentType);
  if (payload.note) form.append("note", payload.note);
  return postFormData<FamilyDocument>(
    "/api/v1/home-safety/family/documents",
    form,
  );
}

export function fetchFamilyDocuments() {
  return familyApi<FamilyDocument[]>("/documents");
}

export function fetchFamilyVisit(visitId: string) {
  return familyApi<FamilyVisit>(`/visits/${encodeURIComponent(visitId)}`);
}

export function submitFamilyVisitExperienceRating(
  visitId: string,
  payload: { rating: number; comment?: string },
) {
  return familyApi<FamilyVisit>(
    `/visits/${encodeURIComponent(visitId)}/experience-rating`,
    {
      method: "POST",
      body: JSON.stringify({
        rating: payload.rating,
        comment: payload.comment ?? "",
      }),
    },
  );
}

export function fetchFamilyPhotos() {
  return familyApi<FamilyPhoto[]>("/photos");
}

export function fetchFamilyAlerts() {
  return familyApi<FamilyAlert[]>("/alerts");
}

export function markFamilyAlertRead(alertId: string) {
  return familyApi<FamilyAlert>(`/alerts/${encodeURIComponent(alertId)}/read`, {
    method: "POST",
  });
}

export function fetchEmergencyContacts() {
  return familyApi<EmergencyContact[]>("/emergency-contacts");
}

/** The family's own referral link (www…/r/<code>), FIX 108. */
export function fetchFamilyReferral() {
  // Both null when the server has no referral secret configured.
  return familyApi<{ code: string | null; link: string | null }>("/referral");
}

export function fetchStaffElderImprovementPlan(elderId: number) {
  return api<FamilyImprovementPlan>(
    `/api/v1/home-safety/care/elders/${elderId}/improvement-plan`,
  );
}

export function updateStaffPlanItemStatus(
  elderId: number,
  itemId: string,
  status: PlanItemStatus,
) {
  return api<FamilyPlanItem>(
    `/api/v1/home-safety/care/elders/${elderId}/plan-items/${encodeURIComponent(itemId)}`,
    {
      method: "PATCH",
      body: JSON.stringify({ status }),
    },
  );
}

/** Maps Independence Score™ band / legacy letter grades to CSS status keys. */
export function gradeStatus(grade: string, bandStatus?: string | null): string {
  const band = (bandStatus || "").toLowerCase();
  if (band === "excellent") return "excellent";
  if (band === "good") return "good";
  if (band === "moderate") return "moderate";
  if (band === "high") return "high";
  if (band === "critical") return "critical";

  const g = grade.toLowerCase();
  if (g.includes("excellent") || g === "platinum" || g === "a") return "excellent";
  if (g === "good" || g === "gold" || g === "b") return "good";
  if (g.includes("moderate") || g === "silver" || g === "c") return "moderate";
  if (g.includes("high") || g === "bronze" || g === "d") return "high";
  if (g.includes("critical") || g === "red" || g === "f") return "critical";
  return "moderate";
}

export function priorityLabel(priority: string): string {
  const p = priority.toLowerCase();
  if (p === "critical") return "Critical";
  if (p === "high") return "High";
  if (p === "medium") return "Medium";
  if (p === "low") return "Low";
  return priority;
}

export function planStatusLabel(status: string): string {
  const s = status.toLowerCase();
  if (s === "done") return "Done";
  if (s === "scheduled") return "Scheduled";
  return "Open";
}
