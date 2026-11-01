"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { VisitForm } from "@/components/VisitForm";
import { formatDate, statusTone } from "@/lib/format";
import { fetchAllVisits, fetchClients, type Client, type VisitWithClient } from "@/lib/opsApi";

export default function VisitsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [visits, setVisits] = useState<VisitWithClient[]>([]);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    fetchClients()
      .then(async (list) => {
        setClients(list);
        setVisits(await fetchAllVisits(list));
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load visits"));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return visits;
    return visits.filter((row) =>
      `${row.client_name} ${row.visit_type} ${row.summary} ${row.status}`.toLowerCase().includes(needle),
    );
  }, [q, visits]);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Visits</h1>
          <p className="muted">Log a wellness visit or mark one complete. Filter by client or type.</p>
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      <VisitForm clients={clients} onSaved={load} />
      <div className="toolbar">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search visits" />
      </div>
      <section className="panel">
        {filtered.length === 0 ? (
          <p className="empty">No visits yet.</p>
        ) : (
          filtered.map((visit) => (
            <div className="row" key={`${visit.elder_id}-${visit.id}`}>
              <div>
                <Link href={`/clients/${visit.elder_id}`}>
                  <strong>{visit.client_name}</strong>
                </Link>
                <div className="muted">
                  {visit.visit_type} · {formatDate(visit.visited_at)}
                  {visit.summary ? ` · ${visit.summary}` : ""}
                </div>
              </div>
              <span className={`badge ${statusTone(visit.status)}`}>{visit.status}</span>
            </div>
          ))
        )}
      </section>
    </>
  );
}
