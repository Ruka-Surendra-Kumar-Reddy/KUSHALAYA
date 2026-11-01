"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { VisitForm } from "@/components/VisitForm";
import { canWrite, getLegacyAppUrl, getStoredAuth } from "@/lib/api";
import { formatDate, statusTone } from "@/lib/format";
import { useMounted } from "@/lib/useMounted";
import {
  clientName,
  createDraftAssessment,
  fetchClient,
  fetchVisits,
  type Client,
  type Visit,
} from "@/lib/opsApi";

export default function ClientDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Number(params.id);
  const writable = useMounted() && canWrite(getStoredAuth()?.role || "");
  const legacy = getLegacyAppUrl();
  const [client, setClient] = useState<Client | null>(null);
  const [visits, setVisits] = useState<Visit[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    if (!id) return;
    Promise.all([fetchClient(id), fetchVisits(id)])
      .then(([c, v]) => {
        setClient(c);
        setVisits(v);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load client"));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function startAssessment() {
    if (!client) return;
    setBusy(true);
    setError("");
    try {
      const created = await createDraftAssessment(client);
      router.push(`/assessments/${created.assessment_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start assessment");
    } finally {
      setBusy(false);
    }
  }

  if (!client && !error) return <p className="muted">Loading…</p>;
  if (!client) return <p className="error">{error}</p>;

  return (
    <>
      <div className="page-head">
        <div>
          <p className="muted">
            <Link href="/clients">Clients</Link>
          </p>
          <h1>{clientName(client)}</h1>
          <p className="muted">{client.address || "No address yet"}</p>
        </div>
        {writable && (
          <button type="button" onClick={startAssessment} disabled={busy}>
            {busy ? "Starting…" : "Start assessment"}
          </button>
        )}
      </div>
      {error && <p className="error">{error}</p>}
      <section className="cards">
        <div className="card">
          <small>Phone</small>
          <p>{client.phone || "—"}</p>
        </div>
        <div className="card">
          <small>Status</small>
          <p>{client.status}</p>
        </div>
        <div className="card">
          <small>Independence score</small>
          <p>{client.independence_score ?? "Not published"}</p>
        </div>
      </section>
      <section className="panel">
        <h2>Next step</h2>
        <p>{client.next_step || "No next step recorded."}</p>
        {client.latest_assessment_id && (
          <p>
            Latest assessment:{" "}
            <Link href={`/assessments/${client.latest_assessment_id}`}>
              {client.latest_assessment_status || "open"}
            </Link>
          </p>
        )}
        <p>
          <a href={`${legacy}/livewell/family/login`} target="_blank" rel="noreferrer">
            Family portal login
          </a>
        </p>
      </section>
      <VisitForm clients={[client]} defaultClientId={client.id} onSaved={load} />
      <section className="panel">
        <h2>Visits</h2>
        {visits.length === 0 ? (
          <p className="empty">No visits yet.</p>
        ) : (
          visits.map((visit) => (
            <div className="row" key={visit.id}>
              <div>
                <strong>{visit.visit_type}</strong>
                <div className="muted">
                  {formatDate(visit.visited_at)}
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
