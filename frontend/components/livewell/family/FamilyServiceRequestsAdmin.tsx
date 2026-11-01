"use client";

import { useEffect, useState } from "react";
import { formatIST } from "@/lib/ist";
import {
  fetchStaffServiceRequests,
  updateStaffServiceRequest,
  type FamilyServiceRequest,
} from "@/lib/livewell/familyApi";

export function FamilyServiceRequestsAdmin({ elderId }: { elderId: number }) {
  const [rows, setRows] = useState<FamilyServiceRequest[]>([]);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    setRows(await fetchStaffServiceRequests(elderId));
  }

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, [elderId]);

  async function setStatus(id: string, status: string) {
    setBusyId(id);
    setError("");
    try {
      const note =
        status === "declined"
          ? window.prompt("Optional note for the family?") || undefined
          : undefined;
      await updateStaffServiceRequest(elderId, id, { status, staff_note: note });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    } finally {
      setBusyId(null);
    }
  }

  const open = rows.filter((r) => r.status === "requested");

  return (
    <div className="card" style={{ marginTop: "1.5rem" }}>
      <h2 style={{ marginTop: 0 }}>Service requests</h2>
      {error ? <p className="error">{error}</p> : null}
      {rows.length === 0 ? (
        <p className="muted">No requests yet.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: "0.65rem" }}>
          {rows.map((r) => (
            <li
              key={r.id}
              style={{
                border: "1px solid var(--border, #dde3ea)",
                borderRadius: 8,
                padding: "0.75rem 0.85rem",
                background: r.status === "requested" ? "#fffaf3" : undefined,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem" }}>
                <strong>
                  {r.service_label}
                  {r.product_code ? <span className="muted"> · {r.product_code}</span> : null}
                </strong>
                <span className="muted">{r.status}</span>
              </div>
              <p className="muted" style={{ margin: "0.25rem 0", fontSize: "0.85rem" }}>
                Preferred{" "}
                {r.preferred_at ? formatIST(r.preferred_at) : "Any time"}
                {r.created_by ? ` · ${r.created_by}` : ""}
              </p>
              {r.notes ? <p style={{ margin: "0.25rem 0" }}>{r.notes}</p> : null}
              {r.status === "requested" ? (
                <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                  <button
                    type="button"
                    className="primary"
                    disabled={busyId === r.id}
                    onClick={() => void setStatus(r.id, "confirmed")}
                  >
                    Confirm
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    disabled={busyId === r.id}
                    onClick={() => void setStatus(r.id, "declined")}
                  >
                    Decline
                  </button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {open.length > 0 ? (
        <p className="muted" style={{ marginTop: "0.75rem", fontSize: "0.85rem" }}>
          {open.length} awaiting confirmation
        </p>
      ) : null}
    </div>
  );
}
