"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getLegacyAppUrl } from "@/lib/api";
import { fetchDashboard, type OpsDashboardSummary } from "@/lib/opsApi";

const EMPTY: OpsDashboardSummary = {
  clients: 0,
  assessments_open: 0,
  assessments_total: 0,
  visits_today: 0,
  visits_total: 0,
  catalog_items: 0,
};

export default function DashboardPage() {
  const [counts, setCounts] = useState<OpsDashboardSummary | null>(null);
  const [error, setError] = useState("");
  const legacy = getLegacyAppUrl();

  useEffect(() => {
    fetchDashboard()
      .then(setCounts)
      .catch((err) => {
        setCounts(EMPTY);
        setError(err instanceof Error ? err.message : "Could not load dashboard");
      });
  }, []);

  const data = counts || EMPTY;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Today’s work</h1>
          <p className="muted">Clients, open assessments, and visits — same data as the current app.</p>
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      <section className="cards">
        <Link className="card" href="/clients">
          <small>Clients</small>
          <p className="count">{data.clients}</p>
          <small>Open directory</small>
        </Link>
        <Link className="card" href="/assessments">
          <small>Open assessments</small>
          <p className="count">{data.assessments_open}</p>
          <small>{data.assessments_total} total</small>
        </Link>
        <Link className="card" href="/visits">
          <small>Visits today</small>
          <p className="count">{data.visits_today}</p>
          <small>{data.visits_total} in range</small>
        </Link>
      </section>
      <section className="panel">
        <h2>Quick access</h2>
        <div className="list">
          <div className="row">
            <div>
              <strong>Clients</strong>
              <div className="muted">Find a household and see next step</div>
            </div>
            <Link href="/clients">Open</Link>
          </div>
          <div className="row">
            <div>
              <strong>Assessments</strong>
              <div className="muted">Drafts and completed checklists</div>
            </div>
            <Link href="/assessments">Open</Link>
          </div>
          <div className="row">
            <div>
              <strong>Visits</strong>
              <div className="muted">Log or complete a visit</div>
            </div>
            <Link href="/visits">Open</Link>
          </div>
        </div>
      </section>
      <section className="panel">
        <h2>Other apps</h2>
        <div className="apps">
          <a className="card" href={`${legacy}/livewell`} target="_blank" rel="noreferrer">
            <strong>Field assessor</strong>
            <p className="muted">Phone PWA for on-site checklists</p>
          </a>
          <a className="card" href={`${legacy}/livewell/family/login`} target="_blank" rel="noreferrer">
            <strong>Family portal</strong>
            <p className="muted">What families see</p>
          </a>
          <a className="card" href={`${legacy}/dashboard`} target="_blank" rel="noreferrer">
            <strong>Current admin</strong>
            <p className="muted">Catalog, pricing, and setup still live here</p>
          </a>
        </div>
      </section>
    </>
  );
}
