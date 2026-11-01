"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { canWrite, getStoredAuth } from "@/lib/api";
import { statusTone } from "@/lib/format";
import { useMounted } from "@/lib/useMounted";
import {
  clientName,
  createClient,
  fetchClients,
  type Client,
} from "@/lib/opsApi";

function flowLabel(row: Client) {
  if (row.family_published) {
    return row.independence_score != null
      ? `Family live · ${row.independence_score}`
      : "Family live";
  }
  if (row.latest_assessment_status === "draft") return "Draft assessment";
  if (row.latest_assessment_status === "completed") return "Saved · not on family";
  return "Needs assessment";
}

export default function ClientsPage() {
  const mounted = useMounted();
  const writable = mounted && canWrite(getStoredAuth()?.role || "");
  const [rows, setRows] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [busy, setBusy] = useState(false);

  function load() {
    setLoading(true);
    fetchClients()
      .then(setRows)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load clients"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((row) =>
      `${row.first_name} ${row.last_name} ${row.phone || ""} ${row.address || ""}`
        .toLowerCase()
        .includes(needle),
    );
  }, [q, rows]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await createClient({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        phone: phone.trim() || undefined,
        address: address.trim() || undefined,
      });
      setFirstName("");
      setLastName("");
      setPhone("");
      setAddress("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add client");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Clients</h1>
          <p className="muted">Search a household, see the next step, open their assessments and visits.</p>
        </div>
      </div>
      <div className="toolbar">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search name, phone, or address"
        />
      </div>
      {error && <p className="error">{error}</p>}
      {writable && (
        <form className="panel form-grid" onSubmit={onCreate}>
          <h2 className="span-2">Add client</h2>
          <label>
            First name
            <input value={firstName} onChange={(e) => setFirstName(e.target.value)} required />
          </label>
          <label>
            Last name
            <input value={lastName} onChange={(e) => setLastName(e.target.value)} required />
          </label>
          <label>
            Phone
            <input value={phone} onChange={(e) => setPhone(e.target.value)} />
          </label>
          <label>
            Address
            <input value={address} onChange={(e) => setAddress(e.target.value)} />
          </label>
          <div className="span-2">
            <button type="submit" disabled={busy}>
              {busy ? "Saving…" : "Save client"}
            </button>
          </div>
        </form>
      )}
      <section className="panel">
        {loading ? (
          <p className="empty">Loading…</p>
        ) : filtered.length === 0 ? (
          <p className="empty">No clients match that search.</p>
        ) : (
          filtered.map((row) => (
            <div className="row" key={row.id}>
              <div>
                <Link href={`/clients/${row.id}`}>
                  <strong>{clientName(row)}</strong>
                </Link>
                <div className="muted">{row.address || row.phone || "No address yet"}</div>
              </div>
              <span className={`badge ${statusTone(row.latest_assessment_status || row.status)}`}>
                {flowLabel(row)}
              </span>
            </div>
          ))
        )}
      </section>
    </>
  );
}
