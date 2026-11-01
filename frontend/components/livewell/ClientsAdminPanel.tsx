"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, getStoredAuth } from "@/lib/api";
import { canManageUsers, canWrite } from "@/lib/auth";
import { loginAsFamilyClient } from "@/lib/staffImpersonation";
import {
  convertElderProspect,
  createElderProspect,
  listElderProspects,
  permanentlyDeleteElder,
  permanentlyDeleteElderProspect,
  stageLabel,
  type ElderProspect,
} from "@/lib/prospects";
import { startAssessment } from "@/lib/jobs";

export type ClientRow = {
  id: number;
  first_name: string;
  last_name: string;
  status: string;
  phone: string | null;
  address?: string | null;
  family_published?: boolean;
  independence_score?: number | null;
  latest_assessment_id?: string | null;
  latest_assessment_status?: string | null;
  family_email?: string | null;
};

function flowBadge(row: ClientRow): { label: string; className: string } {
  if (row.family_published) {
    return {
      label:
        row.independence_score != null
          ? `Family live · ${row.independence_score}`
          : "Family live",
      className: "customers-flow-badge customers-flow-badge--ok",
    };
  }
  if (row.latest_assessment_status === "draft") {
    return {
      label: "Draft assessment",
      className: "customers-flow-badge customers-flow-badge--warn",
    };
  }
  if (row.latest_assessment_status === "completed") {
    return {
      label: "Saved · not on family",
      className: "customers-flow-badge customers-flow-badge--warn",
    };
  }
  return {
    label: "Needs assessment",
    className: "customers-flow-badge customers-flow-badge--muted",
  };
}

export function ClientsAdminPanel({
  isAdmin,
  demandLabel,
  onMessage,
  onError,
}: {
  isAdmin: boolean;
  demandLabel: string;
  onMessage: (msg: string) => void;
  onError: (msg: string) => void;
}) {
  const router = useRouter();
  const writable = canWrite(getStoredAuth()?.role || "");
  const [admin, setAdmin] = useState(isAdmin);
  const [canImpersonate, setCanImpersonate] = useState(false);
  const [rows, setRows] = useState<ClientRow[]>([]);
  const [leads, setLeads] = useState<ElderProspect[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [showNewLead, setShowNewLead] = useState(false);
  const [listTab, setListTab] = useState<"clients" | "leads">("clients");
  const [query, setQuery] = useState("");
  const [newLead, setNewLead] = useState({
    first_name: "",
    last_name: "",
    phone: "",
  });

  useEffect(() => {
    const role = getStoredAuth()?.role || "";
    setAdmin(canManageUsers(role) || isAdmin);
    setCanImpersonate(canManageUsers(role) || role === "CARE_MANAGER");
  }, [isAdmin]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [clients, openLeads] = await Promise.all([
        api<ClientRow[]>("/api/v1/elders"),
        listElderProspects({ status: "OPEN" }),
      ]);
      setRows(clients);
      setLeads(openLeads);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Could not load clients");
      setRows([]);
      setLeads([]);
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    void load();
  }, [load]);

  const q = query.trim().toLowerCase();
  const visibleClients = useMemo(
    () =>
      rows.filter((row) =>
        `${row.first_name} ${row.last_name} ${row.phone || ""} ${row.address || ""}`
          .toLowerCase()
          .includes(q),
      ),
    [q, rows],
  );
  const visibleLeads = useMemo(
    () =>
      leads.filter((lead) =>
        `${lead.first_name} ${lead.last_name} ${lead.phone || ""}`.toLowerCase().includes(q),
      ),
    [leads, q],
  );

  async function deleteClient(client: ClientRow) {
    if (!admin) return;
    const label = `${client.first_name} ${client.last_name}`.trim();
    if (
      !window.confirm(
        `Delete client #${client.id} (${label})? Family users will be unlinked. This cannot be undone.`,
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      const result = await permanentlyDeleteElder(client.id);
      if (result?.id !== client.id && result?.deleted !== "elder") {
        throw new Error("Delete did not confirm — client may still exist. Refresh and try again.");
      }
      onMessage(`Deleted client #${client.id}`);
      setRows((prev) => prev.filter((r) => r.id !== client.id));
      await load();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Delete failed");
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function deleteLead(lead: ElderProspect) {
    if (!admin) return;
    if (
      !window.confirm(
        `Delete lead #${lead.id} (${lead.first_name} ${lead.last_name})? This cannot be undone.`,
      )
    ) {
      return;
    }
    try {
      await permanentlyDeleteElderProspect(lead.id);
      onMessage(`Deleted lead #${lead.id}`);
      await load();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  // The one assessment flow: client info → checklist → review (/caregiver/assess).
  async function startAssessmentForClient(client: ClientRow) {
    const res = await startAssessment({ elder_id: client.id });
    router.push(`/caregiver/assess/${res.job_id}?from=assessments`);
  }

  async function startAssessmentForLead(lead: ElderProspect) {
    const res = await startAssessment({ lead_id: lead.id });
    router.push(`/caregiver/assess/${res.job_id}?from=leads`);
  }

  async function convertLead(lead: ElderProspect) {
    if (!writable) return;
    const label = `${lead.first_name} ${lead.last_name}`;
    if (!window.confirm(`Convert ${label} to a ${demandLabel.toLowerCase()}?`)) return;
    setBusy(true);
    try {
      const res = await convertElderProspect(lead.id);
      onMessage(`Converted to client #${res.elder_id}`);
      setListTab("clients");
      await load();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Convert failed");
    } finally {
      setBusy(false);
    }
  }

  async function viewAsFamily(client: ClientRow) {
    if (!canImpersonate) return;
    setBusy(true);
    try {
      await loginAsFamilyClient(client.id);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Could not open family portal");
      setBusy(false);
    }
  }

  async function createLead(e: React.FormEvent) {
    e.preventDefault();
    if (!writable) return;
    setBusy(true);
    try {
      const created = await createElderProspect({
        first_name: newLead.first_name.trim(),
        last_name: newLead.last_name.trim(),
        phone: newLead.phone.trim() || null,
      });
      onMessage(`Created lead #${created.id}`);
      setShowNewLead(false);
      setNewLead({ first_name: "", last_name: "", phone: "" });
      setListTab("leads");
      await load();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Could not create lead");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="customers-hub">
      <div className="card" style={{ overflowX: "auto" }}>
        <div className="customers-tabs">
          <button
            type="button"
            className={listTab === "clients" ? "active" : undefined}
            onClick={() => {
              setListTab("clients");
              setShowNewLead(false);
            }}
          >
            Clients ({rows.length})
          </button>
          <button
            type="button"
            className={listTab === "leads" ? "active" : undefined}
            onClick={() => setListTab("leads")}
          >
            Leads ({leads.length})
          </button>
        </div>

        <div className="customers-hub-list-head">
          <input aria-label={listTab === "leads" ? "Search leads" : "Search clients"}
            className="customers-hub-search"
            type="search"
            placeholder={listTab === "leads" ? "Search leads" : "Search clients"}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {writable && listTab === "leads" ? (
            <button
              type="button"
              className="secondary"
              onClick={() => setShowNewLead((v) => !v)}
            >
              {showNewLead ? "Cancel" : "+ New lead"}
            </button>
          ) : null}
        </div>

        {showNewLead && writable && listTab === "leads" ? (
          <form onSubmit={(ev) => void createLead(ev)} className="customers-hub-new-lead">
            <input
              placeholder="First name"
              value={newLead.first_name}
              onChange={(e) => setNewLead((f) => ({ ...f, first_name: e.target.value }))}
              required
            />
            <input
              placeholder="Last name"
              value={newLead.last_name}
              onChange={(e) => setNewLead((f) => ({ ...f, last_name: e.target.value }))}
              required
            />
            <input
              placeholder="Phone"
              value={newLead.phone}
              onChange={(e) => setNewLead((f) => ({ ...f, phone: e.target.value }))}
            />
            <button type="submit" disabled={busy}>
              Create
            </button>
          </form>
        ) : null}

        {loading ? (
          <p className="muted">Loading…</p>
        ) : listTab === "leads" ? (
          visibleLeads.length === 0 ? (
            <p className="muted">{q ? "No matching leads." : "No open leads."}</p>
          ) : (
            <div className="customers-person-list">
              {visibleLeads.map((lead) => (
                <div key={lead.id} className="customers-person-row">
                  <div>
                    <div className="customers-person-name">
                      {lead.first_name} {lead.last_name}
                    </div>
                    <div className="customers-person-meta">
                      <span>{lead.phone || "No mobile"}</span>
                      <span>{stageLabel(lead.stage)}</span>
                    </div>
                  </div>
                  <div className="customers-row-actions">
                    {writable ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void convertLead(lead)}
                      >
                        Convert
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="secondary"
                      disabled={busy}
                      onClick={() => startAssessmentForLead(lead)}
                    >
                      Assessment
                    </button>
                    {admin ? (
                      <button
                        type="button"
                        className="danger"
                        disabled={busy}
                        onClick={() => void deleteLead(lead)}
                      >
                        Delete
                      </button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )
        ) : visibleClients.length === 0 ? (
          <p className="muted">{q ? "No matching clients." : "No clients yet."}</p>
        ) : (
          <div className="customers-person-list">
            {visibleClients.map((row) => {
              const badge = flowBadge(row);
              return (
                <div key={row.id} className="customers-person-row">
                  <div>
                    <div className="customers-person-name">
                      <Link href={`/kushalaya/customers/${row.id}`}>
                        {row.first_name} {row.last_name}
                      </Link>
                    </div>
                    <div className="customers-person-meta">
                      <span>{row.phone || "No mobile"}</span>
                      <span className={badge.className}>{badge.label}</span>
                    </div>
                  </div>
                  <div className="customers-row-actions">
                    {row.latest_assessment_id ? (
                      <Link href={`/kushalaya/assessments/${row.latest_assessment_id}`}>
                        Assessment
                      </Link>
                    ) : (
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy}
                        onClick={() => startAssessmentForClient(row)}
                      >
                        Assessment
                      </button>
                    )}
                    <Link href={`/kushalaya/customers/${row.id}`}>Profile</Link>
                    <Link href={`/kushalaya/visits?elder=${row.id}`}>Visits</Link>
                    {canImpersonate ? (
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy}
                        onClick={() => void viewAsFamily(row)}
                      >
                        View as family
                      </button>
                    ) : null}
                    {admin ? (
                      <button
                        type="button"
                        className="danger"
                        disabled={busy}
                        onClick={() => void deleteClient(row)}
                      >
                        Delete
                      </button>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
