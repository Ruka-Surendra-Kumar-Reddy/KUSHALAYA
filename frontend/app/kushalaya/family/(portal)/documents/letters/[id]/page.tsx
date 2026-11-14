"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { FamilyLink as Link } from "@/components/livewell/family/FamilyLink";
import { FamilyShell } from "@/components/livewell/family/FamilyShell";
import { FamilyError } from "@/components/livewell/family/FamilyError";
import { familyApi } from "@/lib/livewell/familyApi";
import { openPdf, type MonthlyLetter } from "@/lib/kushlife-quality";
import "@/components/kushlife/vitals-trend.css";

type Goal = { goal: string; status: string; progress: string };

/** #100: the monthly KushLife letter (approved by the Family Partner), with a PDF copy. */
export default function FamilyLetterPage() {
  const id = String(useParams().id ?? "");
  const [letter, setLetter] = useState<MonthlyLetter | null>(null);
  const [error, setError] = useState("");
  const [pdfErr, setPdfErr] = useState("");
  useEffect(() => {
    if (!/^\d+$/.test(id)) return setError("Letter not found");
    familyApi<MonthlyLetter>(`/kushlife/letters/${id}`).then(setLetter).catch((e) => setError(e instanceof Error ? e.message : "Could not load"));
  }, [id]);

  const s = (letter?.stats ?? {}) as Record<string, unknown>;
  const goals = (s.goals as Goal[] | undefined) ?? [];
  return (
    <FamilyShell title="KushLife letter" subtitle={letter ? `${letter.elder_name ?? ""} · ${letter.month_label}` : ""}>
      {error ? <FamilyError message={error} /> : null}
      {letter ? (
        <article className="card home-safety-section kq-letter">
          <h2>{letter.month_label}</h2>
          <div className="kq-tiles">
            <div className="kq-tile"><strong>{String(s.visits_done ?? 0)}</strong><span>Visits done</span></div>
            <div className="kq-tile"><strong>{String(s.visits_missed ?? 0)}</strong><span>Visits missed</span></div>
            <div className="kq-tile"><strong>{String(s.kushlife_visits ?? 0)}</strong><span>KushLife checks</span></div>
          </div>
          <p>{letter.text}</p>
          {goals.length ? (
            <>
              <h3>Care plan goals</h3>
              <ul>
                {goals.map((g) => (
                  <li key={g.goal}>{g.goal} — {g.status === "achieved" ? "achieved" : "in progress"}{g.progress ? `: ${g.progress}` : ""}</li>
                ))}
              </ul>
            </>
          ) : null}
          {letter.manager_note ? (<><h3>From your Family Partner</h3><p>{letter.manager_note}</p></>) : null}
          {letter.next_plan ? (<><h3>Next month</h3><p>{letter.next_plan}</p></>) : null}
          <p className="kq-muted">Care observations by your care team, not a medical diagnosis.</p>
          <div className="kq-actions kq-noprint">
            <button type="button" className="btn btn-primary"
              onClick={() => void openPdf(`/api/v1/home-safety/family/kushlife/letters/${letter.id}/pdf`).catch((e) => setPdfErr(e.message))}>
              Download PDF
            </button>
            <Link href="/kushalaya/family/documents">All letters</Link>
          </div>
          {pdfErr ? <p role="alert">{pdfErr}</p> : null}
        </article>
      ) : !error ? <p className="muted">Loading…</p> : null}
    </FamilyShell>
  );
}
