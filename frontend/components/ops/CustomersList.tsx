"use client";

/** Customers page list: one aligned row per customer (like the Assessments list).
 *  Search · status · care manager · Export CSV; rows open the customer page. */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, getStoredAuth } from "@/lib/api";
import { canManageUsers } from "@/lib/auth";
import { displayPhone } from "@/lib/display-format";
import { formatIST } from "@/lib/ist";
import {
  PLAN_STATUS_LABEL,
  customerMatchesStatus,
  customersCsv,
  downloadCsv,
  filterCustomers,
  isoDay,
  listCustomers,
  type CustomerRow,
} from "@/lib/sales-pipeline";
import { BulkCareTeamDialog, type BulkAction } from "@/components/ops/BulkCareTeam";
import "@/components/ops/sales.css";
import "@/components/ops/customers-list.css";

/** Care details from /team/clients, joined to the plan rows by elder id. */
type Care = {
  id: number;
  status: string;
  mine?: boolean;
  next_visit_at?: string | null;
  reassessment_due?: boolean;
  assessment_overdue?: boolean;
  needs_first_assessment?: boolean;
};

const STATUSES = [
  ["all", "All statuses"],
  ["active", "Active"],
  ["pending_approval", "Pending approval"],
  ["unpaid", "Unpaid"],
  ["ending30", "Ending in 30 days"],
  ["expired", "Expired"],
  ["cancelled", "Cancelled"],
  ["none", "No plan"],
  ["reassessment", "Assessment due"],
] as const;

const STATE_LABEL: Record<string, string> = { ACTIVE: "Active", PAUSED: "Paused", INACTIVE: "Ended", ENDED: "Ended" };

function stateOf(care?: Care) {
  const s = (care?.status || "ACTIVE").toUpperCase();
  return { key: s === "ACTIVE" ? "active" : s === "PAUSED" ? "paused" : "ended", label: STATE_LABEL[s] ?? "Ended" };
}

const dueAssessment = (c?: Care) => !!c && !!(c.reassessment_due ?? (c.assessment_overdue || c.needs_first_assessment));

export function CustomersList({ reloadKey = 0 }: { reloadKey?: number }) {
  const router = useRouter();
  const admin = canManageUsers(getStoredAuth()?.role || "");
  const [rows, setRows] = useState<CustomerRow[] | null>(null);
  const [care, setCare] = useState<Map<number, Care>>(new Map());
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatusState] = useState("all");
  const [manager, setManager] = useState("");
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [bulk, setBulk] = useState<BulkAction | null>(null);

  // ?status=… (Dashboard tiles) and the older ?filter=reassessment pick the status.
  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    const st = sp.get("filter") === "reassessment" ? "reassessment" : sp.get("status");
    if (st && STATUSES.some(([k]) => k === st)) setStatusState(st);
  }, []);
  const setStatus = useCallback((st: string) => {
    setStatusState(st);
    const url = new URL(window.location.href);
    url.searchParams.delete("filter");
    if (st === "all") url.searchParams.delete("status");
    else url.searchParams.set("status", st);
    window.history.replaceState(window.history.state, "", url.toString());
  }, []);

  const load = useCallback(() => {
    listCustomers()
      .then((d) => setRows(d.customers))
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load customers"));
    api<Care[]>("/api/v1/team/clients")
      .then((list) => setCare(new Map(list.map((c) => [c.id, c]))))
      .catch(() => undefined);
  }, []);
  useEffect(() => load(), [load, reloadKey]);

  const today = isoDay(new Date());
  const matchStatus = useCallback(
    (r: CustomerRow, st: string) => (st === "reassessment" ? dueAssessment(care.get(r.elder_id)) : customerMatchesStatus(r, st, today)),
    [care, today],
  );
  const managers = useMemo(
    () => [...new Set((rows ?? []).map((r) => r.care_manager).filter((m): m is string => !!m))].sort((a, b) => a.localeCompare(b)),
    [rows],
  );
  const hasMine = useMemo(() => [...care.values()].some((c) => c.mine), [care]);
  const shown = useMemo(
    () =>
      filterCustomers(rows ?? [], "all", query)
        .filter((r) => matchStatus(r, status))
        .filter((r) =>
          !manager
            ? true
            : manager === "__mine"
              ? !!care.get(r.elder_id)?.mine
              : manager === "__none"
                ? !r.care_manager
                : r.care_manager === manager,
        )
        .sort((a, b) => a.name.localeCompare(b.name)),
    [rows, query, status, manager, care, matchStatus],
  );
  const filtered = !!query.trim() || status !== "all" || !!manager;
  const open = (r: CustomerRow) => router.push(`/kushalaya/customers/${r.elder_id}`);
  const toggle = (id: number, on: boolean) => {
    const next = new Set(picked);
    if (on) next.add(id);
    else next.delete(id);
    setPicked(next);
  };

  return (
    <section className={`cu card${admin ? " has-check" : ""}`}>
      {error ? <p className="error-text">{error}</p> : null}
      <div className="cu-bar">
        <input
          className="cu-search"
          type="search"
          aria-label="Search name, phone, ID or area"
          placeholder="Search name, phone, ID or area"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
          {STATUSES.map(([k, label]) => (
            <option key={k} value={k}>
              {label}
              {rows && k !== "all" ? ` (${rows.filter((r) => matchStatus(r, k)).length})` : ""}
            </option>
          ))}
        </select>
        <select aria-label="Care manager" value={manager} onChange={(e) => setManager(e.target.value)}>
          <option value="">All care managers</option>
          {hasMine ? <option value="__mine">My customers</option> : null}
          <option value="__none">No care manager</option>
          {managers.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <span className="cu-count" aria-live="polite">
          {rows ? `${shown.length} customer${shown.length === 1 ? "" : "s"}` : ""}
        </span>
        <button
          type="button"
          className="secondary cu-export"
          disabled={!shown.length}
          onClick={() => downloadCsv(`kushalaya-customers-${today}.csv`, customersCsv(shown))}
        >
          Export CSV
        </button>
      </div>

      {rows === null ? (
        <p className="cu-empty">Loading…</p>
      ) : shown.length === 0 ? (
        <p className="cu-empty">
          {filtered ? "No customers match." : "No customers yet."}
          {filtered ? (
            <button
              type="button"
              className="cu-clear"
              onClick={() => {
                setQuery("");
                setManager("");
                setStatus("all");
              }}
            >
              Clear filters
            </button>
          ) : null}
        </p>
      ) : (
        <div className="cu-list" role="list" aria-label="Customers">
          <div className="cu-row cu-head" aria-hidden="true">
            {admin ? (
              <span className="cu-check">
                <input
                  type="checkbox"
                  tabIndex={-1}
                  checked={shown.every((r) => picked.has(r.elder_id))}
                  onChange={(e) => setPicked(e.target.checked ? new Set(shown.map((r) => r.elder_id)) : new Set())}
                />
              </span>
            ) : null}
            <span>Customer</span>
            <span>Phone</span>
            <span>Area</span>
            <span>Plan</span>
            <span>Care manager</span>
            <span>Next visit</span>
            <span>Status</span>
            <span />
          </div>
          {shown.map((r) => {
            const c = care.get(r.elder_id);
            const st = stateOf(c);
            const next = formatIST(c?.next_visit_at, { dateOnly: true });
            return (
              <div
                key={r.elder_id}
                role="listitem"
                className="cu-row"
                tabIndex={0}
                aria-label={`Open ${r.name}`}
                onClick={() => open(r)}
                onKeyDown={(e) => {
                  if ((e.key === "Enter" || e.key === " ") && e.target === e.currentTarget) {
                    e.preventDefault();
                    open(r);
                  }
                }}
              >
                {admin ? (
                  <span className="cu-check" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      aria-label={`Select ${r.name}`}
                      checked={picked.has(r.elder_id)}
                      onChange={(e) => toggle(r.elder_id, e.target.checked)}
                    />
                  </span>
                ) : null}
                <span className="cu-who">
                  <strong className="cu-name">{r.name}</strong>
                  <small>
                    {r.customer_id}
                    {r.device_linked ? <em className="cu-tag">SOS watch</em> : null}
                  </small>
                </span>
                <span className="cu-phone">{displayPhone(r.phone) || <span className="cu-dim">—</span>}</span>
                <span className="cu-area">{r.city || <span className="cu-dim">—</span>}</span>
                <span className="cu-plan">
                  {r.plan ? (
                    <>
                      <span className="cu-plan-name">{r.plan.plan_name.replace(/^KushAlaya /, "")}</span>
                      <span className={`sp-pill is-${r.status}`}>{PLAN_STATUS_LABEL[r.status]}</span>
                    </>
                  ) : (
                    <span className="cu-dim">No plan</span>
                  )}
                </span>
                <span className="cu-mgr" data-label="Care manager">
                  {r.care_manager || <span className="cu-dim">Not assigned</span>}
                </span>
                <span className="cu-next" data-label="Next visit">
                  {next || <span className="cu-dim">—</span>}
                </span>
                <span className="cu-state">
                  <span className={`cu-pill is-${st.key}`}>{st.label}</span>
                </span>
                <span className="cu-act">
                  <Link href={`/kushalaya/customers/${r.elder_id}`} tabIndex={-1} onClick={(e) => e.stopPropagation()}>
                    Open
                  </Link>
                </span>
              </div>
            );
          })}
        </div>
      )}

      {admin && picked.size ? (
        <div className="ct-bulk" role="region" aria-label="Selected customers">
          <strong>{picked.size} selected</strong>
          <button type="button" className="ct-btn" onClick={() => setBulk("manager")}>
            Change care manager
          </button>
          <button type="button" className="ct-btn" onClick={() => setBulk("caregiver")}>
            Assign caregiver
          </button>
          <button type="button" className="secondary ct-btn" onClick={() => setPicked(new Set())}>
            Clear
          </button>
        </div>
      ) : null}
      {bulk ? (
        <BulkCareTeamDialog
          action={bulk}
          clients={(rows ?? []).filter((r) => picked.has(r.elder_id)).map((r) => ({ id: r.elder_id, name: r.name }))}
          onClose={() => setBulk(null)}
          onDone={() => {
            setPicked(new Set());
            load();
          }}
        />
      ) : null}
    </section>
  );
}
