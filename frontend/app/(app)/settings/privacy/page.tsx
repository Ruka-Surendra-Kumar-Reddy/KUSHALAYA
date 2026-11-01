"use client";

import { useEffect, useState } from "react";
import { BackLink } from "@/components/ops/PageActions";
import { Flash } from "@/components/Flash";
import { BackupStatusBadge } from "@/components/ops/BackupStatusBadge";
import { fetchDataRequests, reviewDataRequest, type DataRequest } from "@/lib/livewell/privacyApi";
import { formatIST } from "@/lib/ist";
import "@/components/ops/notifications.css";
import { isAdmin as isAdminUser } from "@/lib/roles";

const STATUS_WORDS: Record<DataRequest["status"], string> = {
  PENDING: "Waiting for review",
  REJECTED: "Rejected",
  COMPLETED: "Done",
};

/** The request payload has no client name yet: show it if the API sends one, else "Client #id". */
function clientLabel(r: DataRequest): string {
  if (r.elder_name) return r.elder_name;
  return r.elder_id ? `Client #${r.elder_id}` : "";
}

/** Settings → Privacy & backups: DPDP delete-request queue (#104) and backup status (#105). Admins only. */
export default function PrivacyRequestsPage() {
  const isAdmin = isAdminUser();
  const [rows, setRows] = useState<DataRequest[] | null>(null);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(0);

  function load() {
    fetchDataRequests()
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }

  useEffect(() => {
    if (isAdmin) load();
  }, [isAdmin]);

  async function review(row: DataRequest, action: "approve" | "reject") {
    if (
      action === "approve" &&
      !window.confirm(
        row.scope === "household"
          ? "Erase this family's login AND the client's personal records? Invoices and payments are kept. This cannot be undone."
          : "Anonymise this family member's login? This cannot be undone.",
      )
    )
      return;
    setBusy(row.id);
    setError("");
    try {
      await reviewDataRequest(row.id, action, notes[row.id] || "");
      setMessage(action === "approve" ? `Request #${row.id} done — data erased.` : `Request #${row.id} rejected.`);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(0);
    }
  }

  return (
    <div className="ks-frame">
      <header className="ks-head">
        <BackLink href="/settings" label="Settings" />
        <h1>Privacy &amp; backups</h1>
        <p className="muted">
            Family requests to delete their data (DPDP Act), and the nightly off-server backup. Every export and
            delete is in the Activity log.
          </p>
      </header>
      <Flash error={error} message={message} onClear={() => { setError(""); setMessage(""); }} />
      {!isAdmin ? (
        <p className="muted">Only admins can see this page.</p>
      ) : (
        <>
          <section className="card" style={{ marginBottom: "1rem" }}>
            <h2>Backups</h2>
            <BackupStatusBadge detailed />
          </section>
          <section className="card">
            <h2>Delete requests</h2>
            <p className="muted">
              Approving erases or anonymises personal data. Orders, tax invoices, wallet and payment records are
              kept for 8 years (the law requires it) with names removed.
            </p>
            {!rows ? (
              <p>Loading…</p>
            ) : rows.length === 0 ? (
              <p className="muted">No requests.</p>
            ) : (
              <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: 12 }}>
                {rows.map((r) => (
                  <li key={r.id} className="card" style={{ margin: 0 }}>
                    <strong>
                      #{r.id} · {r.requester} · {r.scope === "household" ? "Login + client records" : "Login only"}
                    </strong>
                    <div className="muted">
                      {STATUS_WORDS[r.status] || r.status} · asked {formatIST(r.created_at) || "—"}
                      {clientLabel(r) ? ` · ${clientLabel(r)}` : ""}
                      {r.reviewed_at ? ` · reviewed ${formatIST(r.reviewed_at)}` : ""}
                    </div>
                    {r.reason ? <p>&ldquo;{r.reason}&rdquo;</p> : null}
                    {r.review_note ? <p className="muted">Note: {r.review_note}</p> : null}
                    {r.status === "PENDING" ? (
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                        <input
                          placeholder="Note (optional)"
                          value={notes[r.id] || ""}
                          onChange={(e) => setNotes({ ...notes, [r.id]: e.target.value })}
                        />
                        <button type="button" className="primary" disabled={busy === r.id} onClick={() => void review(r, "approve")}>
                          Approve &amp; erase
                        </button>
                        <button type="button" className="secondary" disabled={busy === r.id} onClick={() => void review(r, "reject")}>
                          Reject
                        </button>
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
