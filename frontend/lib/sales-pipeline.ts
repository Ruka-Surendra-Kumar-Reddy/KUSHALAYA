/**
 * Operations board (leads by stage) and customer plans. API: /api/v1/sales/*
 * (backend/app/livewell/sales_pipeline.py). Plans and prices come from
 * lib/care-plan-catalog.ts; money is integer paise.
 */
import { api } from "@/lib/api";
import { CARE_PLAN_CATALOG, carePlan, inr, planPricePaise, type BillingCycle } from "@/lib/care-plan-catalog";

export const SALES_STAGES = [
  "NEW",
  "ASSESSMENT_SCHEDULED",
  "ASSESSMENT_DONE",
  "FOLLOW_UP_1",
  "FOLLOW_UP_2",
  "WON",
  "LOST",
] as const;
export type SalesStage = (typeof SALES_STAGES)[number];

export const STAGE_LABEL: Record<SalesStage, string> = {
  NEW: "New",
  ASSESSMENT_SCHEDULED: "Assessment booked",
  ASSESSMENT_DONE: "Assessment done",
  FOLLOW_UP_1: "Follow-up 1",
  FOLLOW_UP_2: "Follow-up 2",
  WON: "Won",
  LOST: "Lost",
};

export const LEAD_SOURCES = ["Phone call", "WhatsApp", "Walk-in", "Referral", "Website", "Other"] as const;

export const PAYMENT_MODES = [
  ["cash", "Cash"],
  ["upi", "UPI"],
  ["bank_transfer", "Bank transfer"],
  ["card", "Card"],
  ["cheque", "Cheque"],
  ["online", "Online (Razorpay)"],
  ["razorpay", "Razorpay (website)"],
  ["other", "Other"],
] as const;

export type Lead = {
  id: number;
  name: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  email: string | null;
  source: string | null;
  stage: SalesStage;
  status: string;
  lost_reason: string | null;
  converted_elder_id: number | null;
  customer_id: string | null;
  created_at: string | null;
  updated_at: string | null;
  /** When it entered its current stage (list only). */
  stage_since?: string | null;
  last_comment?: string | null;
  address?: string | null;
  pincode?: string | null;
  care_level?: string | null;
  /** Won leads: the plan (Pending approval until an admin authorizes it). */
  plan?: CustomerPlan | null;
  /** Newest home assessment saved against the lead. */
  assessment?: { assessment_id: string; status: string } | null;
};

export type LeadEvent = {
  id: number;
  type: string;
  from: string | null;
  to: string | null;
  from_label: string | null;
  to_label: string | null;
  comment: string | null;
  body: string;
  by: string | null;
  at: string | null;
};

export type PlanStatus = "pending_approval" | "active" | "expired" | "cancelled";

export type CustomerPlan = {
  id: number;
  elder_id: number;
  customer_id: string;
  prospect_id: number | null;
  plan_id: string;
  plan_name: string;
  billing_cycle: BillingCycle;
  start_date: string;
  end_date: string;
  amount_paise: number;
  /** Coupon given (e.g. PAYNOW3) and what it took off; amount_paise is after it. */
  coupon_code?: string | null;
  discount_paise?: number;
  payment_status: "paid" | "unpaid";
  payment_mode: string | null;
  paid_at: string | null;
  status: PlanStatus;
  authorized_by_name: string | null;
  authorized_at: string | null;
  created_at: string | null;
};

export type CustomerRow = {
  elder_id: number;
  customer_id: string;
  name: string;
  phone: string | null;
  city: string | null;
  /** Where the lead came from (the enquiry's source), when the client came through Operations. */
  referred_by: string | null;
  /** An SOS watch / band is linked. */
  device_linked: boolean;
  care_manager: string | null;
  plan: CustomerPlan | null;
  status: PlanStatus | "none";
};

export type PendingPlan = CustomerPlan & { name: string; care_manager: string | null };

export type PlanTerms = { plan_id: string; billing_cycle: BillingCycle; start_date: string; coupon_code?: string | null };

/** " · PAYNOW5 −₹6,250" after a plan's amount, or "" without a coupon. */
export function couponNote(p: { coupon_code?: string | null; discount_paise?: number }): string {
  return p.coupon_code ? ` · ${p.coupon_code} −${inr(p.discount_paise || 0)}` : "";
}

export type PlanPrice = {
  plan_id: string;
  plan_name: string;
  billing_cycle: BillingCycle;
  list_paise: number;
  discount_paise: number;
  amount_paise: number;
  coupon_code: string | null;
};

export const PLAN_STATUS_LABEL: Record<PlanStatus | "none", string> = {
  pending_approval: "Pending approval",
  active: "Active",
  expired: "Expired",
  cancelled: "Cancelled",
  none: "No plan",
};

export const CYCLE_LABEL: Record<BillingCycle, string> = { yearly: "Yearly", monthly: "Monthly" };

/** "KC-000012": the Customer ID shown in Customers (same as the backend). */
export function customerCode(elderId: number): string {
  return `KC-${String(elderId).padStart(6, "0")}`;
}

/** "website:care-check" → "Website"; staff picks stay as typed. */
export function sourceLabel(source: string | null | undefined): string {
  const raw = (source || "").trim();
  if (!raw) return "Not recorded";
  if (/^website/i.test(raw)) return "Website";
  if (/^qr(:|$)/i.test(raw)) return "QR / standee";
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

/** ISO yyyy-mm-dd for a local date. */
export function isoDay(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** Same day `months` later, clamped to month end (31 Jan + 1 → 28/29 Feb). Matches the backend. */
export function addMonths(iso: string, months: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const idx = (m - 1) + months;
  const year = y + Math.floor(idx / 12);
  const month = ((idx % 12) + 12) % 12;
  const last = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${year}-${p(month + 1)}-${p(Math.min(d, last))}`;
}

export function planEndDate(startIso: string, cycle: BillingCycle): string {
  return addMonths(startIso, cycle === "yearly" ? 12 : 1);
}

/** Cycles a plan can be bought on (every plan: yearly or monthly). */
export function cyclesFor(planId: string): BillingCycle[] {
  const p = carePlan(planId);
  if (!p) return [];
  return p.monthlyPaise == null ? ["yearly"] : ["yearly", "monthly"];
}

/** Why a move can't be saved yet, or "" when it can. */
export function moveProblem(
  to: SalesStage,
  comment: string,
  terms?: { plan_id?: string; billing_cycle?: string; start_date?: string },
): string {
  if (to === "LOST" && !comment.trim()) return "Say why the lead was lost.";
  if (to === "WON") {
    const p = carePlan(terms?.plan_id || "");
    if (!p) return "Choose a plan.";
    if (terms?.billing_cycle !== "yearly" && terms?.billing_cycle !== "monthly") return "Choose Yearly or Monthly.";
    if (planPricePaise(p.id, terms.billing_cycle) == null) return `${p.name} isn't offered on that billing cycle.`;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(terms.start_date || "")) return "Pick a start date.";
  }
  return "";
}

export function planCatalogOptions() {
  return CARE_PLAN_CATALOG.map((p) => ({ id: p.id, name: p.name }));
}

/** Status filter values beyond the plan statuses: unpaid plans and active plans ending within 30 days. */
export function customerMatchesStatus(r: CustomerRow, status: string, today: string): boolean {
  if (!status || status === "all") return true;
  if (status === "unpaid") return !!r.plan && r.plan.payment_status === "unpaid" && r.plan.status !== "cancelled";
  if (status === "ending30") return r.status === "active" && !!r.plan && r.plan.end_date <= addDays(today, 30);
  return r.status === status;
}

export function addDays(iso: string, days: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

/** Filters for the Customers table: status + free text over ID, name, phone, city, plan, manager. */
export function filterCustomers(rows: CustomerRow[], status: string, query: string, today = isoDay(new Date())): CustomerRow[] {
  const q = query.trim().toLowerCase();
  return rows.filter(
    (r) =>
      customerMatchesStatus(r, status, today) &&
      (!q ||
        [r.customer_id, r.name, r.phone, r.city, r.plan?.plan_name, r.care_manager]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(q)),
  );
}

/** Funnel steps: the sales stages, with Won split into "Pending approval" (plan not yet authorized) and Won. */
export const FUNNEL_STEPS = [
  "NEW",
  "ASSESSMENT_SCHEDULED",
  "ASSESSMENT_DONE",
  "FOLLOW_UP_1",
  "FOLLOW_UP_2",
  "PENDING",
  "WON",
  "LOST",
] as const;
export type FunnelStep = (typeof FUNNEL_STEPS)[number];
export const FUNNEL_LABEL: Record<FunnelStep, string> = { ...STAGE_LABEL, PENDING: "Pending approval" };

/** The one funnel step a lead counts in. */
export function funnelStep(l: Lead): FunnelStep {
  return l.stage === "WON" && l.plan?.status === "pending_approval" ? "PENDING" : l.stage;
}

/** Leads per funnel step; `all` is the total (always the sum of the steps). */
export function funnelCounts(rows: Lead[]): Record<FunnelStep, number> & { all: number } {
  const out = Object.fromEntries(FUNNEL_STEPS.map((s) => [s, 0])) as Record<FunnelStep, number>;
  for (const r of rows) out[funnelStep(r)] += 1;
  return { ...out, all: rows.length };
}

/** Board columns in pipeline order; "Pending approval" only when a lead is in it. */
export function boardColumns(rows: Lead[]): { step: FunnelStep; leads: Lead[] }[] {
  return FUNNEL_STEPS.map((step) => ({ step, leads: rows.filter((r) => funnelStep(r) === step) })).filter(
    (c) => c.step !== "PENDING" || c.leads.length > 0,
  );
}

/** The stage a card dropped on a column moves to (Pending approval is reached by Mark won). */
export function dropTarget(l: Lead, step: FunnelStep): SalesStage | null {
  const to: SalesStage = step === "PENDING" ? "WON" : step;
  return l.stage === "WON" || l.stage === to ? null : to;
}

/** Search over name, phone, email, area / address, source, customer ID; `stage` is a funnel step. */
export function filterLeads(rows: Lead[], query: string, stage = ""): Lead[] {
  const q = query.trim().toLowerCase();
  return rows.filter(
    (r) =>
      (!stage || funnelStep(r) === stage) &&
      (!q ||
        [r.name, r.phone, r.email, r.address, r.pincode, r.source, r.source ? sourceLabel(r.source) : "", r.customer_id]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(q)),
  );
}

export const DATE_RANGES = [
  ["24h", "Last 24 hours"],
  ["7d", "Last 7 days"],
  ["30d", "Last 30 days"],
  ["2m", "Last 2 months"],
  ["3m", "Last 3 months"],
  ["6m", "Last 6 months"],
  ["1y", "Last 1 year"],
  ["lastmonth", "Last month"],
  ["all", "All time"],
  ["custom", "Custom"],
] as const;
export type DateRangeKey = (typeof DATE_RANGES)[number][0];
export const DEFAULT_RANGE: DateRangeKey = "30d";

export function isRangeKey(v: string | null | undefined): v is DateRangeKey {
  return DATE_RANGES.some(([k]) => k === v);
}

/**
 * Query for GET /sales/leads: created-time window as ISO times (`to` exclusive), or all=true.
 * Custom days and "Last month" are whole local days (IST in the office).
 */
export function rangeQuery(key: DateRangeKey, now = new Date(), custom: { from?: string; to?: string } = {}): string {
  const day = (iso: string) => {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, m - 1, d);
  };
  const ago = (days: number) => new Date(now.getTime() - days * 86_400_000);
  const monthsAgo = (n: number) => {
    const d = new Date(now);
    d.setMonth(d.getMonth() - n);
    return d;
  };
  let from: Date | null = null;
  let to: Date | null = null;
  switch (key) {
    case "24h": from = ago(1); break;
    case "7d": from = ago(7); break;
    case "30d": from = ago(30); break;
    case "2m": from = monthsAgo(2); break;
    case "3m": from = monthsAgo(3); break;
    case "6m": from = monthsAgo(6); break;
    case "1y": from = monthsAgo(12); break;
    case "lastmonth":
      from = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      to = new Date(now.getFullYear(), now.getMonth(), 1);
      break;
    case "custom":
      if (/^\d{4}-\d{2}-\d{2}$/.test(custom.from || "")) from = day(custom.from!);
      if (/^\d{4}-\d{2}-\d{2}$/.test(custom.to || "")) {
        to = day(custom.to!);
        to.setDate(to.getDate() + 1);
      }
      if (!from && !to) return "all=true";
      break;
    case "all":
      return "all=true";
  }
  const q = new URLSearchParams();
  if (from) q.set("from", from.toISOString());
  if (to) q.set("to", to.toISOString());
  return q.toString();
}

/** Whole days since an ISO time (0 for today / unknown). Backend times without a zone are UTC. */
export function daysSince(iso: string | null | undefined, now = Date.now()): number {
  if (!iso) return 0;
  const t = Date.parse(/(Z|[+-]\d\d:?\d\d)$/i.test(iso) ? iso : `${iso}Z`);
  if (Number.isNaN(t)) return 0;
  return Math.max(0, Math.floor((now - t) / 86_400_000));
}

export function leadsCsv(rows: Lead[], now = Date.now()): string {
  const head = ["Name", "Source", "Phone", "Email", "Stage", "Days in stage", "Last comment", "Created", "Updated"];
  const lines = rows.map((r) =>
    [
      r.name,
      sourceLabel(r.source),
      r.phone ?? "",
      r.email ?? "",
      STAGE_LABEL[r.stage],
      daysSince(r.stage_since || r.created_at, now),
      r.last_comment ?? "",
      (r.created_at ?? "").slice(0, 10),
      (r.updated_at ?? "").slice(0, 10),
    ]
      .map(csvCell)
      .join(","),
  );
  return [head.join(","), ...lines].join("\r\n") + "\r\n";
}

/** One CSV cell: quoted when needed; a leading = + - @ is neutralised so spreadsheets don't run it. */
export function csvCell(value: unknown): string {
  let s = value == null ? "" : String(value);
  // Phone numbers like "+91 98765 43210" are plain numbers, not formulas: keep them as they are.
  if (/^[=+\-@\t\r]/.test(s) && !/^[+-]?[\d\s().-]+$/.test(s)) s = `'${s}`;
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function customersCsv(rows: CustomerRow[]): string {
  const head = [
    "Customer ID", "Name", "Phone", "City", "Package", "Billing", "Start date", "End date",
    "Amount (INR)", "Payment", "Status", "Referred by", "Device", "Care manager",
  ];
  const lines = rows.map((r) =>
    [
      r.customer_id,
      r.name,
      r.phone ?? "",
      r.city ?? "",
      r.plan?.plan_name ?? "No plan",
      r.plan ? CYCLE_LABEL[r.plan.billing_cycle] : "",
      r.plan?.start_date ?? "",
      r.plan?.end_date ?? "",
      r.plan ? (r.plan.amount_paise / 100).toFixed(2) : "",
      r.plan ? (r.plan.payment_status === "paid" ? "Paid" : "Unpaid") : "",
      PLAN_STATUS_LABEL[r.status],
      r.referred_by ? sourceLabel(r.referred_by) : "",
      r.device_linked ? "Yes" : "No",
      r.care_manager ?? "",
    ]
      .map(csvCell)
      .join(","),
  );
  return [head.join(","), ...lines].join("\r\n") + "\r\n";
}

export function downloadCsv(filename: string, csv: string): void {
  // BOM so Excel reads ₹ and Indian names correctly.
  const blob = new Blob(["﻿", csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// --- API ---

export const listLeads = (query = "") => api<Lead[]>(`/api/v1/sales/leads${query ? `?${query}` : ""}`);
export const addLeadComment = (id: number, comment: string) =>
  api<{ ok: boolean }>(`/api/v1/sales/leads/${id}/comment`, { method: "POST", body: JSON.stringify({ comment }) });
export const leadHistory = (id: number) => api<LeadEvent[]>(`/api/v1/sales/leads/${id}/history`);
export const createLead = (body: {
  name: string;
  source: string;
  phone: string | null;
  email: string | null;
  address?: string | null;
  pincode?: string | null;
}) => api<Lead>("/api/v1/sales/leads", { method: "POST", body: JSON.stringify(body) });
export const updateLead = (
  id: number,
  body: { name: string; phone: string | null; email: string | null; address: string | null; pincode: string | null },
) => api<Lead>(`/api/v1/sales/leads/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const moveLead = (
  id: number,
  body: { to: SalesStage; comment?: string | null; elder_id?: number | null } & Partial<PlanTerms>,
) => api<Lead & { customer_plan?: CustomerPlan }>(`/api/v1/sales/leads/${id}/move`, { method: "POST", body: JSON.stringify(body) });

export const listCustomers = () => api<{ customers: CustomerRow[]; pending: PendingPlan[] }>("/api/v1/sales/customers");
export const customerPlans = (elderId: number) =>
  api<{ elder_id: number; customer_id: string; current: CustomerPlan | null; plans: CustomerPlan[]; total_paise: number; paid_paise: number }>(
    `/api/v1/sales/customers/${elderId}/plans`,
  );
export const planPrice = (body: { plan_id: string; billing_cycle: BillingCycle; coupon_code: string }) =>
  api<PlanPrice>("/api/v1/sales/plan-price", { method: "POST", body: JSON.stringify(body) });
export const assignPlan = (elderId: number, terms: PlanTerms) =>
  api<CustomerPlan>(`/api/v1/sales/customers/${elderId}/plans`, { method: "POST", body: JSON.stringify(terms) });
export const authorizePlan = (planId: number, body: { payment_mode: string; paid: boolean }) =>
  api<CustomerPlan>(`/api/v1/sales/plans/${planId}/authorize`, { method: "POST", body: JSON.stringify(body) });
export const markPlanPaid = (planId: number, payment_mode?: string) =>
  api<CustomerPlan>(`/api/v1/sales/plans/${planId}/mark-paid`, { method: "POST", body: JSON.stringify({ payment_mode: payment_mode || null }) });

export type DashboardCounts = {
  active_clients: number;
  leads: Record<"NEW" | "ASSESSMENT_SCHEDULED" | "ASSESSMENT_DONE" | "FOLLOW_UP_1" | "FOLLOW_UP_2", number>;
  won_this_month: number;
  lost_this_month: number;
  pending_approval: number;
  unpaid_plans: number;
  plans_ending_30_days: number;
};
export const dashboardCounts = () => api<DashboardCounts>("/api/v1/sales/dashboard-counts");

// --- Customer overview (client profile) ---

/** Visits a plan period includes: the catalog's visits a year, or a twelfth of it for a monthly plan. */
export function visitsIncluded(planId: string, cycle: BillingCycle): number {
  const p = carePlan(planId);
  if (!p) return 0;
  return cycle === "yearly" ? p.visitsPerYear : Math.round(p.visitsPerYear / 12);
}

type JobLike = { id: number; kind?: string; title?: string; kind_label?: string; status: string; scheduled_at: string | null; status_label?: string };

/** Completed visits inside the plan's dates. */
export function visitsUsed(jobs: JobLike[], plan: { start_date: string; end_date: string } | null): number {
  if (!plan) return 0;
  return jobs.filter((j) => {
    const day = (j.scheduled_at || "").slice(0, 10);
    return j.status === "completed" && day >= plan.start_date && day <= plan.end_date;
  }).length;
}

export type RequestRow = { key: string; id: string; date: string | null; service: string; status: string; open: boolean };

const OPEN_REQUEST = new Set(["requested", "confirmed"]);
const OPEN_JOB = new Set(["requested", "scheduled", "on_the_way", "checked_in"]);

const words = (s: string) => {
  const t = s.replace(/_/g, " ").trim();
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : "";
};

/** Family requests and visits as one list, newest first, split into active and closed. */
export function splitRequests(
  requests: { id: string; title?: string; service_name?: string; status?: string; created_at?: string }[],
  jobs: JobLike[],
  limit = 10,
): { active: RequestRow[]; closed: RequestRow[] } {
  const rows: RequestRow[] = [
    ...requests.map((r) => {
      const st = String(r.status || "requested").toLowerCase();
      return {
        key: `r${r.id}`,
        id: `R-${String(r.id).slice(0, 8).toUpperCase()}`,
        date: r.created_at || null,
        service: r.service_name || r.title || "Request",
        status: words(st),
        open: OPEN_REQUEST.has(st),
      };
    }),
    ...jobs.map((j) => ({
      key: `v${j.id}`,
      id: `V-${j.id}`,
      date: j.scheduled_at,
      service: j.title || j.kind_label || words(j.kind || "visit"),
      status: j.status_label || words(j.status),
      open: OPEN_JOB.has(j.status),
    })),
  ].sort((a, b) => (b.date || "").localeCompare(a.date || ""));
  return { active: rows.filter((r) => r.open).slice(0, limit), closed: rows.filter((r) => !r.open).slice(0, limit) };
}
