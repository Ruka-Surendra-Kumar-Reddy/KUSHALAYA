import { describe, expect, it } from "vitest";
import {
  addDays,
  addMonths,
  boardColumns,
  dropTarget,
  daysSince,
  filterLeads,
  FUNNEL_STEPS,
  funnelCounts,
  funnelStep,
  isRangeKey,
  rangeQuery,
  leadsCsv,
  splitRequests,
  visitsIncluded,
  visitsUsed,
  type Lead,
  csvCell,
  customerCode,
  customersCsv,
  cyclesFor,
  filterCustomers,
  moveProblem,
  planEndDate,
  sourceLabel,
  type CustomerRow,
} from "./sales-pipeline";

describe("plan dates", () => {
  it("adds a year or a month, clamping month end", () => {
    expect(planEndDate("2026-10-26", "yearly")).toBe("2027-10-26");
    expect(planEndDate("2026-10-26", "monthly")).toBe("2026-11-26");
    expect(addMonths("2026-01-31", 1)).toBe("2026-02-28");
    expect(addMonths("2028-01-31", 1)).toBe("2028-02-29");
    expect(addMonths("2026-12-15", 1)).toBe("2027-01-15");
  });
});

describe("moves", () => {
  it("Lost needs a comment", () => {
    expect(moveProblem("LOST", "  ")).toMatch(/why/);
    expect(moveProblem("LOST", "Too costly")).toBe("");
    expect(moveProblem("FOLLOW_UP_1", "")).toBe("");
  });
  it("Won needs a plan, a cycle and a start date; every plan can be monthly", () => {
    expect(moveProblem("WON", "")).toMatch(/plan/);
    expect(moveProblem("WON", "", { plan_id: "privilege" })).toMatch(/Yearly or Monthly/);
    expect(moveProblem("WON", "", { plan_id: "assurance", billing_cycle: "monthly", start_date: "2026-10-26" })).toBe("");
    expect(moveProblem("WON", "", { plan_id: "assurance", billing_cycle: "yearly", start_date: "" })).toMatch(/start/);
    expect(moveProblem("WON", "", { plan_id: "signature", billing_cycle: "monthly", start_date: "2026-10-26" })).toBe("");
    expect(cyclesFor("assurance")).toEqual(["yearly", "monthly"]);
    expect(cyclesFor("total-care")).toEqual(["yearly", "monthly"]);
  });
});

const row = (over: Partial<CustomerRow>): CustomerRow => ({
  elder_id: 1,
  customer_id: customerCode(1),
  name: "Asha Rao",
  phone: null,
  city: "Hyderabad",
  referred_by: "website:care-check",
  device_linked: true,
  care_manager: "Bharani",
  plan: null,
  status: "none",
  ...over,
});

describe("customers", () => {
  it("codes, labels and filters", () => {
    expect(customerCode(42)).toBe("KC-000042");
    expect(sourceLabel("website:care-check")).toBe("Website");
    expect(sourceLabel("qr:care-check")).toBe("QR / standee");
    expect(sourceLabel("Phone call")).toBe("Phone call");
    const rows = [row({}), row({ elder_id: 2, customer_id: "KC-000002", name: "Ravi", status: "active" })];
    expect(filterCustomers(rows, "active", "")).toHaveLength(1);
    expect(filterCustomers(rows, "all", "kc-000002")[0]?.name).toBe("Ravi");
    expect(filterCustomers(rows, "none", "bharani")).toHaveLength(1);
  });
  it("CSV quotes commas and neutralises formulas", () => {
    expect(csvCell('a,"b"')).toBe('"a,""b"""');
    expect(csvCell("=SUM(A1)")).toBe("'=SUM(A1)");
    const csv = customersCsv([
      row({
        name: "Rao, Asha",
        status: "pending_approval",
        plan: {
          id: 1, elder_id: 1, customer_id: "KC-000001", prospect_id: null, plan_id: "privilege",
          plan_name: "KushAlaya Privilege", billing_cycle: "yearly", start_date: "2026-10-26", end_date: "2027-10-26",
          amount_paise: 12_500_000, payment_status: "unpaid", payment_mode: null, paid_at: null,
          status: "pending_approval", authorized_by_name: null, authorized_at: null, created_at: null,
        },
      }),
    ]);
    const lines = csv.trim().split("\r\n");
    expect(lines[0]).toBe(
      "Customer ID,Name,Phone,City,Package,Billing,Start date,End date,Amount (INR),Payment,Status,Referred by,Device,Care manager",
    );
    expect(lines[1]).toBe(
      'KC-000001,"Rao, Asha",,Hyderabad,KushAlaya Privilege,Yearly,2026-10-26,2027-10-26,125000.00,Unpaid,Pending approval,Website,Yes,Bharani',
    );
  });
});

describe("follow-ups", () => {
  const plan = {
    id: 1, elder_id: 1, customer_id: "KC-000001", prospect_id: null, plan_id: "privilege",
    plan_name: "KushAlaya Privilege", billing_cycle: "yearly" as const, start_date: "2026-10-01", end_date: "2026-11-10",
    amount_paise: 12_500_000, payment_status: "unpaid" as const, payment_mode: null, paid_at: null,
    status: "active" as const, authorized_by_name: null, authorized_at: null, created_at: null,
  };
  it("status filter knows unpaid and ending in 30 days", () => {
    const rows = [row({ status: "active", plan }), row({ elder_id: 2 })];
    expect(filterCustomers(rows, "unpaid", "", "2026-10-26")).toHaveLength(1);
    expect(filterCustomers(rows, "ending30", "", "2026-10-26")).toHaveLength(1);
    expect(filterCustomers(rows, "ending30", "", "2026-09-01")).toHaveLength(0);
    expect(addDays("2026-12-20", 30)).toBe("2027-01-19");
  });
  it("lead export: stage filter, days in stage, last comment", () => {
    const now = Date.parse("2026-10-26T12:00:00Z");
    const lead: Lead = {
      id: 1, name: "Asha", first_name: "Asha", last_name: "", phone: "+91 98765 43210", email: null,
      source: "website:contact", stage: "FOLLOW_UP_1", status: "OPEN", lost_reason: null, converted_elder_id: null,
      customer_id: null, created_at: "2026-10-01T09:00:00", updated_at: "2026-10-20T09:00:00",
      stage_since: "2026-10-20T09:00:00", last_comment: "Call back, Monday",
    };
    expect(filterLeads([lead], "", "NEW")).toHaveLength(0);
    expect(filterLeads([lead], "asha", "FOLLOW_UP_1")).toHaveLength(1);
    expect(daysSince("2026-10-20T09:00:00", now)).toBe(6);
    const lines = leadsCsv([lead], now).trim().split("\r\n");
    expect(lines[0]).toBe("Name,Source,Phone,Email,Stage,Days in stage,Last comment,Created,Updated");
    expect(lines[1]).toBe('Asha,Website,+91 98765 43210,,Follow-up 1,6,"Call back, Monday",2026-10-01,2026-10-20');
  });
  it("visits included / used and request split", () => {
    expect(visitsIncluded("privilege", "yearly")).toBe(50);
    expect(visitsIncluded("signature", "monthly")).toBe(6);
    const jobs = [
      { id: 1, status: "completed", scheduled_at: "2026-10-05T05:00:00Z", title: "Weekly visit" },
      { id: 2, status: "completed", scheduled_at: "2026-09-05T05:00:00Z", title: "Old" },
      { id: 3, status: "scheduled", scheduled_at: "2026-10-28T05:00:00Z", title: "Next" },
    ];
    expect(visitsUsed(jobs, plan)).toBe(1);
    expect(visitsUsed(jobs, null)).toBe(0);
    const { active, closed } = splitRequests(
      [{ id: "abc12345xyz", service_name: "Plumber", status: "requested", created_at: "2026-10-20T00:00:00Z" }],
      jobs,
    );
    expect(active.map((r) => r.id)).toEqual(["V-3", "R-ABC12345"]);
    expect(closed.map((r) => r.id)).toEqual(["V-1", "V-2"]);
  });
});

describe("Operations funnel", () => {
  const mk = (id: number, stage: Lead["stage"], extra: Partial<Lead> = {}): Lead => ({
    id, name: `L${id}`, first_name: "", last_name: "", phone: null, email: null, source: "Phone call", stage,
    status: "OPEN", lost_reason: null, converted_elder_id: null, customer_id: null, created_at: null, updated_at: null,
    ...extra,
  });
  const pending = { status: "pending_approval" } as Lead["plan"];
  const active = { status: "active" } as Lead["plan"];
  const rows = [
    mk(1, "NEW", { address: "Kondapur, Hyderabad" }), mk(2, "NEW"), mk(3, "ASSESSMENT_SCHEDULED"), mk(4, "ASSESSMENT_DONE"),
    mk(5, "FOLLOW_UP_1"), mk(6, "FOLLOW_UP_2"), mk(7, "WON", { plan: pending }), mk(8, "WON", { plan: active }), mk(9, "LOST"),
  ];
  it("each column's count equals its cards, and the columns add up to All", () => {
    const cols = boardColumns(rows);
    const c = funnelCounts(rows);
    for (const col of cols) expect(col.leads.length).toBe(c[col.step]);
    expect(cols.reduce((n, col) => n + col.leads.length, 0)).toBe(rows.length);
    expect(cols.map((col) => col.step)).toEqual([...FUNNEL_STEPS]);
    expect(boardColumns(rows.filter((r) => r.id !== 7)).some((col) => col.step === "PENDING")).toBe(false);
  });
  it("drop target: Pending approval means Mark won; Won leads and same-stage drops do nothing", () => {
    expect(dropTarget(rows[0], "PENDING")).toBe("WON");
    expect(dropTarget(rows[0], "LOST")).toBe("LOST");
    expect(dropTarget(rows[0], "NEW")).toBeNull();
    expect(dropTarget(rows[7], "NEW")).toBeNull();
  });
  it("each chip's count equals the rows the table shows, and the chips add up to All", () => {
    const c = funnelCounts(rows);
    for (const s of FUNNEL_STEPS) expect(c[s]).toBe(filterLeads(rows, "", s).length);
    expect(FUNNEL_STEPS.reduce((n, s) => n + c[s], 0)).toBe(c.all);
    expect(c.all).toBe(filterLeads(rows, "").length);
    expect([c.NEW, c.PENDING, c.WON, c.LOST]).toEqual([2, 1, 1, 1]);
    expect(funnelStep(rows[6])).toBe("PENDING");
  });
  it("search covers area and the source label", () => {
    expect(filterLeads(rows, "kondapur").map((r) => r.id)).toEqual([1]);
    expect(filterLeads([mk(10, "NEW", { source: "website:care-check" })], "website")).toHaveLength(1);
  });
  it("date ranges", () => {
    const now = new Date(2026, 9, 28, 12, 0);
    expect(rangeQuery("all", now)).toBe("all=true");
    const q = new URLSearchParams(rangeQuery("lastmonth", now));
    expect(new Date(q.get("from")!).getTime()).toBe(new Date(2026, 8, 1).getTime());
    expect(new Date(q.get("to")!).getTime()).toBe(new Date(2026, 9, 1).getTime());
    const d7 = new URLSearchParams(rangeQuery("7d", now));
    expect(now.getTime() - new Date(d7.get("from")!).getTime()).toBe(7 * 86_400_000);
    expect(d7.get("to")).toBeNull();
    const c = new URLSearchParams(rangeQuery("custom", now, { from: "2026-10-01", to: "2026-10-05" }));
    expect(new Date(c.get("to")!).getTime()).toBe(new Date(2026, 9, 6).getTime());
    expect(isRangeKey("3m")).toBe(true);
    expect(isRangeKey("x")).toBe(false);
  });
});
