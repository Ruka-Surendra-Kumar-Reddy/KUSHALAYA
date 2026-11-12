/**
 * AI room hazard check — API client and small pure helpers.
 * Backend: backend/app/api/v1/home_safety_ai_hazards.py
 */
import { api, postFormData } from "@/lib/api";

export type HazardBand = "high" | "check" | "low";
export type HazardSeverity = "urgent" | "soon" | "watch";
export type HazardDecision = "pending" | "confirmed" | "rejected";
/** Assessment rating written on confirm: "unsafe" = Risk, "acceptable" = Needs attention. */
export type HazardRating = "unsafe" | "acceptable";

export type HazardProduct = {
  product_code: string;
  name: string;
  category: string;
  price_paise: number;
  price_with_gst_paise: number | null;
  price_label: string;
};

export type RoomHazard = {
  n: number;
  code: string;
  label: string;
  confidence: number;
  band: HazardBand;
  /** Normalised [x, y, w, h] (0–1) or null when the model gave no single place. */
  box: [number, number, number, number] | null;
  evidence: string | null;
  room: string | null;
  room_label: string;
  severity: HazardSeverity;
  severity_label: string;
  solution_id: string;
  solution_name: string;
  rubric_item_id: string | null;
  question: string | null;
  decision: HazardDecision;
  rating?: HazardRating | null;
  decided_by?: string;
  decided_at?: string;
  source?: string;
  applied_to?: string;
  products: HazardProduct[];
};

export type HazardCheck = {
  id: string;
  document_id: number;
  elder_id: number | null;
  prospect_id: number | null;
  assessment_id: string | null;
  room_type: string | null;
  room_label: string;
  status: "queued" | "running" | "succeeded" | "failed";
  stage: string | null;
  cache_hit: boolean;
  model: string | null;
  hazards: RoomHazard[];
  notes: string | null;
  error_message: string | null;
  created_at: string | null;
  finished_at: string | null;
  applied_to_assessment?: boolean;
};

export type RoomSummaryRow = { room: string; label: string; hazards: number; urgent: number };
export type HazardSummary = {
  rooms: RoomSummaryRow[];
  total_confirmed: number;
  total_urgent: number;
  pending: number;
};

const BASE = "/api/v1/home-safety/ai/hazard-checks";

export function startHazardCheck(opts: {
  documentId: number;
  roomType?: string | null;
  assessmentId?: string | null;
  force?: boolean;
}): Promise<HazardCheck> {
  return api<HazardCheck>(BASE, {
    method: "POST",
    body: JSON.stringify({
      document_id: opts.documentId,
      room_type: opts.roomType || null,
      assessment_id: opts.assessmentId || null,
      force: Boolean(opts.force),
    }),
  });
}

export function uploadAndCheckRoom(elderId: number, file: File, roomType?: string | null): Promise<HazardCheck> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("elder_id", String(elderId));
  if (roomType) fd.append("room_type", roomType);
  return postFormData<HazardCheck>(`${BASE}/upload`, fd);
}

export function getHazardCheck(id: string): Promise<HazardCheck> {
  return api<HazardCheck>(`${BASE}/${encodeURIComponent(id)}`);
}

export function listHazardChecks(q: {
  assessmentId?: string | null;
  elderId?: number | null;
  documentId?: number | null;
}): Promise<{ checks: HazardCheck[]; summary: HazardSummary }> {
  const p = new URLSearchParams();
  if (q.assessmentId) p.set("assessment_id", q.assessmentId);
  if (q.elderId != null) p.set("elder_id", String(q.elderId));
  if (q.documentId != null) p.set("document_id", String(q.documentId));
  return api(`${BASE}?${p.toString()}`);
}

export function decideHazard(
  checkId: string,
  n: number,
  decision: "confirm" | "reject",
  rating?: HazardRating,
): Promise<HazardCheck> {
  return api<HazardCheck>(`${BASE}/${encodeURIComponent(checkId)}/hazards/${n}`, {
    method: "POST",
    body: JSON.stringify({ decision, rating: rating ?? null }),
  });
}

export type PendingCarryOver = {
  check_id: string;
  n: number;
  label: string;
  room_label: string;
  severity_label: string;
};

export function pendingCarryOver(elderId: number, assessmentId?: string | null): Promise<{ hazards: PendingCarryOver[] }> {
  const p = new URLSearchParams({ elder_id: String(elderId) });
  if (assessmentId) p.set("assessment_id", assessmentId);
  return api(`${BASE}/pending?${p.toString()}`);
}

export type CarriedHazard = { rubric_item_id: string; rating: HazardRating; note: string; label: string; room_label: string };

export function carryOverHazards(assessmentId: string): Promise<{ applied: CarriedHazard[] }> {
  return api(`${BASE}/carry-over`, { method: "POST", body: JSON.stringify({ assessment_id: assessmentId }) });
}

export type FamilyRoomHazard = { room_label: string; label: string; severity_label: string; suggestion: string };

export function familyRoomHazards(): Promise<{ hazards: FamilyRoomHazard[]; total: number }> {
  return api("/api/v1/home-safety/family/room-hazards");
}

// --- pure helpers ---------------------------------------------------------------

export function isRunning(check: Pick<HazardCheck, "status"> | null | undefined): boolean {
  return check?.status === "queued" || check?.status === "running";
}

/** Shown hazards (high + check) and the hidden low-confidence ones. */
export function splitByBand(hazards: RoomHazard[]): { shown: RoomHazard[]; low: RoomHazard[] } {
  return {
    shown: hazards.filter((h) => h.band !== "low"),
    low: hazards.filter((h) => h.band === "low"),
  };
}

export function bandText(band: HazardBand): string {
  if (band === "high") return "Likely";
  if (band === "check") return "Please check";
  return "Low confidence";
}

/** Default rating on confirm: Watch items are "Needs attention", the rest "Risk". */
export function defaultRating(h: Pick<RoomHazard, "severity">): HazardRating {
  return h.severity === "watch" ? "acceptable" : "unsafe";
}

export function rupeesInclGst(p: HazardProduct): string {
  if (p.price_with_gst_paise == null) return p.price_label || "Quote";
  return `₹${Math.round(p.price_with_gst_paise / 100).toLocaleString("en-IN")} incl. GST`;
}

/** "Bathroom: 3 hazards · 2 urgent" */
export function roomChipText(r: RoomSummaryRow): string {
  const base = `${r.label}: ${r.hazards} hazard${r.hazards === 1 ? "" : "s"}`;
  return r.urgent ? `${base} · ${r.urgent} urgent` : base;
}

/** Link to the AI room preview ("Show it fixed"), built by the preview page. */
export function showItFixedHref(opts: {
  assessmentId?: string | null;
  documentId: number;
  productCodes: string[];
}): string {
  const p = new URLSearchParams();
  if (opts.assessmentId) p.set("assessment", opts.assessmentId);
  p.set("photo", String(opts.documentId));
  const codes = Array.from(new Set(opts.productCodes.filter(Boolean)));
  if (codes.length) p.set("products", codes.join(","));
  // Opened from Room checks: the preview's Back link returns there, not to the client page.
  if (typeof window !== "undefined" && window.location.pathname.startsWith("/kushalaya/room-checks")) p.set("from", "room-checks");
  return `/kushalaya/ai-preview?${p.toString().replace(/%2C/g, ",")}`;
}

/** Product codes worth previewing: physical items first (services can't be "seen"). */
export function previewProductCodes(products: HazardProduct[], max = 3): string[] {
  const isService = (code: string) => /^(SVC|HM|WEL|NUR|PHY|DX|TRN)-/i.test(code);
  const things = products.filter((p) => !isService(p.product_code));
  return (things.length ? things : products).slice(0, max).map((p) => p.product_code);
}
