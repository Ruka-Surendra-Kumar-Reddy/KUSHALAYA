"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { CareSheetView } from "@/components/CareSheetView";
import type { ClientSheet } from "@/lib/clientCare";

/** Client sheet (medicines, allergies, doctor, keys and access) — opens on the visit day only. */
export function ClientSheetPanel({ jobId }: { jobId: number }) {
  const [sheet, setSheet] = useState<ClientSheet | null>(null);
  const [error, setError] = useState("");

  function onToggle(e: React.SyntheticEvent<HTMLDetailsElement>) {
    if (!e.currentTarget.open || sheet) return;
    api<ClientSheet>(`/api/v1/caregiver-portal/jobs/${jobId}/client-sheet`)
      .then(setSheet)
      .catch((err: Error) => setError(err.message || "Could not open the client sheet"));
  }

  return (
    <details className="cg-know" onToggle={onToggle}>
      <summary>Client sheet — medicines, allergies, keys</summary>
      {sheet ? <CareSheetView sheet={sheet} /> : error ? <p>{error}</p> : <p>Opening…</p>}
    </details>
  );
}
