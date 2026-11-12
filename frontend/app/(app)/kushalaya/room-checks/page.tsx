"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { ClientRoomCheck } from "@/components/ops/ClientRoomCheck";
import { api } from "@/lib/api";
import { can } from "@/lib/roles";
import { parseApiTime } from "@/lib/ist";
import { type HazardCheck } from "@/lib/livewell/aiHazardCheck";
import "@/components/ops/room-checks.css";

type Client = { id: number; first_name: string; last_name: string | null };
type Row = HazardCheck & { elder_name?: string | null; shared_with_family_at?: string | null };

function day(iso: string | null): string {
  if (!iso) return "";
  return parseApiTime(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/** Customers → Room checks: our team's AI room hazard checks. Shared with a family only on purpose. */
export default function RoomChecksPage() {
  const canEdit = can("edit");
  const [tab, setTab] = useState<"new" | "history">("new");
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState("");
  const [rows, setRows] = useState<Row[] | null>(null);
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api<Client[]>("/api/v1/elders")
      .then((c) => setClients([...c].sort((a, b) => a.first_name.localeCompare(b.first_name))))
      .catch(() => undefined);
  }, []);

  const loadHistory = useCallback(() => {
    api<{ checks: Row[] }>("/api/v1/home-safety/ai/hazard-checks?recent=true")
      .then((r) => {
        setRows(r.checks.filter((c) => c.elder_id != null));
        setError("");
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load checks"));
  }, []);

  useEffect(() => {
    if (tab === "history") loadHistory();
  }, [tab, loadHistory]);

  async function share(row: Row, shared: boolean) {
    if (shared && !window.confirm(`Show the confirmed hazards from this ${row.room_label.toLowerCase()} check to ${row.elder_name || "the client"}'s family?`)) return;
    setBusyId(row.id);
    try {
      const out = await api<Row>(`/api/v1/home-safety/ai/hazard-checks/${row.id}/share`, {
        method: "POST",
        body: JSON.stringify({ shared }),
      });
      setRows((cur) => (cur ? cur.map((r) => (r.id === row.id ? { ...r, shared_with_family_at: out.shared_with_family_at } : r)) : cur));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update sharing");
    } finally {
      setBusyId("");
    }
  }

  return (
    <>
      <PageHeader title="Room checks" subtitle="AI photo hazard checks for our team. Families see one only if you share it." />
      <div className="rc-tabs" role="tablist" aria-label="Room checks">
        <button type="button" role="tab" aria-selected={tab === "new"} className={tab === "new" ? "is-on" : ""} onClick={() => setTab("new")}>
          New check
        </button>
        <button type="button" role="tab" aria-selected={tab === "history"} className={tab === "history" ? "is-on" : ""} onClick={() => setTab("history")}>
          History
        </button>
      </div>

      {tab === "new" ? (
        <section className="rc-new">
          <label className="rc-client">
            Client
            <select value={clientId} onChange={(e) => setClientId(e.target.value)}>
              <option value="">Choose a client…</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {`${c.first_name} ${c.last_name || ""}`.trim()}
                </option>
              ))}
            </select>
          </label>
          {clientId ? <ClientRoomCheck key={clientId} elderId={Number(clientId)} /> : <p className="muted">Choose a client to check a room.</p>}
        </section>
      ) : (
        <section className="card rc-history">
          {error ? (
            <p className="error" role="alert">
              {error}
            </p>
          ) : null}
          {rows === null ? (
            <p className="muted">Loading…</p>
          ) : rows.length === 0 ? (
            <p className="muted">No room checks yet.</p>
          ) : (
            <ul className="rc-list">
              {rows.map((r) => {
                const confirmed = r.hazards.filter((h) => h.decision === "confirmed").length;
                const open = r.hazards.filter((h) => !h.decision || h.decision === "pending").length;
                return (
                  <li key={r.id} className="rc-row">
                    <div className="rc-info">
                      <strong>{r.elder_name || "Client"}</strong>
                      <span className="muted">
                        {r.room_label} · {day(r.finished_at || r.created_at)}
                      </span>
                      <span>
                        {r.status !== "succeeded"
                          ? r.status === "failed"
                            ? "Check failed"
                            : "Checking…"
                          : `${confirmed} confirmed${open ? ` · ${open} to review` : ""}`}
                      </span>
                    </div>
                    <div className="rc-acts">
                      <span className={`rc-pill ${r.shared_with_family_at ? "is-shared" : ""}`}>
                        {r.shared_with_family_at ? "Shared with family" : "Team only"}
                      </span>
                      <Link className="secondary rc-btn" href={`/kushalaya/customers/${r.elder_id}`}>
                        Open
                      </Link>
                      {canEdit && r.status === "succeeded" ? (
                        <button
                          type="button"
                          className="secondary rc-btn"
                          disabled={busyId === r.id}
                          onClick={() => void share(r, !r.shared_with_family_at)}
                        >
                          {r.shared_with_family_at ? "Stop sharing" : "Share with family"}
                        </button>
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}
    </>
  );
}
