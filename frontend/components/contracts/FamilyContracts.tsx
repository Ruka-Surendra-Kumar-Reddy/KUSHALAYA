"use client";

import { useEffect, useState } from "react";
import { downloadFamilyContractPdf, listFamilyContracts, type FamilyContract } from "@/lib/contracts";
import { formatIst } from "./format";
import "./contracts.css";

/** Family portal → Documents: this client's contracts signed by both sides (download the PDF). */
export function FamilyContracts() {
  const [rows, setRows] = useState<FamilyContract[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    listFamilyContracts().then(setRows).catch(() => setRows([]));
  }, []);

  if (!rows || rows.length === 0) return null;
  return (
    <section className="card home-safety-section">
      <h2>Signed contracts</h2>
      {error ? <p className="error-text">{error}</p> : null}
      <ul className="ct-family-list">
        {rows.map((c) => (
          <li key={c.id} className="card home-safety-family-doc-card">
            <div>
              <strong>{c.title}</strong>
              <p className="muted">
                {c.ref} · signed {formatIst(c.signed_at, false)}
                {c.signed_name ? ` by ${c.signed_name}` : ""}
              </p>
            </div>
            <button
              type="button"
              className="secondary"
              onClick={() => void downloadFamilyContractPdf(c).catch((e) => setError(e instanceof Error ? e.message : "Could not download"))}
            >
              Download PDF
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
