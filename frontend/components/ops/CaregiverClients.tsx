"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatIST } from "@/lib/ist";

type Row = { assignment_id: number; elder_id: number; name: string; since: string | null };

/** "Their clients" on a caregiver's detail: clients they are a regular caregiver for. */
export function CaregiverClients({ caregiverId }: { caregiverId: number }) {
  const [rows, setRows] = useState<Row[] | null>(null);
  useEffect(() => {
    api<Row[]>(`/api/v1/team/caregivers/${caregiverId}/clients`)
      .then(setRows)
      .catch(() => setRows([]));
  }, [caregiverId]);
  return (
    <div className="ct-their">
      <strong>Their clients</strong>
      {rows === null ? (
        <p className="muted">Loading…</p>
      ) : rows.length ? (
        <ul className="ct-list">
          {rows.map((r) => (
            <li key={r.assignment_id}>
              <Link className="ct-link" href={`/kushalaya/customers/${r.elder_id}`}>
                {r.name}
              </Link>
              {r.since ? <small className="muted">Since {formatIST(r.since, { dateOnly: true })}</small> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">Not a regular caregiver for any client yet.</p>
      )}
    </div>
  );
}
