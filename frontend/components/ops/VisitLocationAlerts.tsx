"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

type LocationAlert = { id: number; title: string; body: string; path: string };

const POLL_MS = 60_000;

/**
 * Small notices on every ops page when a visit was checked in or finished away from
 * the client's home (backend app/livewell/visit_location.py). The × closes it for this user.
 */
export function VisitLocationAlerts() {
  const [rows, setRows] = useState<LocationAlert[]>([]);

  useEffect(() => {
    let cancelled = false;
    async function tick() {
      try {
        const next = await api<LocationAlert[]>("/api/v1/jobs/location-alerts");
        if (!cancelled) setRows(next);
      } catch {
        /* keep the last list */
      }
    }
    void tick();
    const timer = setInterval(() => void tick(), POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  async function close(id: number) {
    setRows((list) => list.filter((r) => r.id !== id));
    await api(`/api/v1/jobs/location-alerts/${id}/dismiss`, { method: "POST" }).catch(() => undefined);
  }

  if (rows.length === 0) return null;
  return (
    <div className="ks-loc-alerts" role="region" aria-label="Visit location alerts">
      {rows.slice(0, 3).map((r) => (
        <div key={r.id} className="ks-loc-alert">
          <span>
            <strong>{r.title}</strong> {r.body}{" "}
            {r.path ? <Link href={r.path}>Open</Link> : null}
          </span>
          <button type="button" aria-label="Close" onClick={() => void close(r.id)}>
            ×
          </button>
        </div>
      ))}
      {rows.length > 3 ? <p className="ks-loc-more">+{rows.length - 3} more</p> : null}
    </div>
  );
}
