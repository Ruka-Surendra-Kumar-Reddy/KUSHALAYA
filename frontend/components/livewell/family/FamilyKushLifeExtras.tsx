"use client";

import { useEffect, useState } from "react";
import { FamilyLink as Link } from "@/components/livewell/family/FamilyLink";
import { VitalsTrend } from "@/components/kushlife/VitalsTrend";
import { familyApi } from "@/lib/livewell/familyApi";
import type { VitalsSeries } from "@/lib/kushlife-quality";
import "@/components/kushlife/vitals-trend.css";

type LetterItem = { id: number; month_label: string };

/** "How likely are you to recommend KushAlaya?" — asked every 90 days (#106). */
export function NpsPrompt() {
  const [due, setDue] = useState(false);
  const [score, setScore] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [done, setDone] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    familyApi<{ due: boolean }>("/feedback/nps").then((r) => setDue(r.due)).catch(() => undefined);
  }, []);
  if (done) return <section className="card home-safety-section"><p className="muted">{done}</p></section>;
  if (!due) return null;
  async function send(value: number | null) {
    setBusy(true);
    try {
      await familyApi("/feedback/nps", { method: "POST", body: JSON.stringify({ score: value, reason }) });
      setDone(value == null ? "No problem — we'll ask another time." : "Thank you. Your care manager reads every answer.");
    } catch (e) {
      setDone(e instanceof Error ? e.message : "Could not send");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="card home-safety-section kq-nps" aria-labelledby="kq-nps-h">
      <h2 id="kq-nps-h">How likely are you to recommend KushAlaya to a friend?</h2>
      <div className="kq-nps-scale" role="group" aria-label="0 is not at all likely, 10 is extremely likely">
        {Array.from({ length: 11 }, (_, i) => (
          <button key={i} type="button" aria-pressed={score === i} onClick={() => setScore(i)}>{i}</button>
        ))}
      </div>
      <div className="kq-nps-ends"><span>Not likely</span><span>Very likely</span></div>
      {score != null ? (
        <label>
          What is the main reason for your score? (optional)
          <textarea rows={2} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>
      ) : null}
      <div className="kq-actions">
        <button type="button" className="btn btn-primary" disabled={busy || score == null} onClick={() => void send(score)}>Send</button>
        <button type="button" className="secondary" disabled={busy} onClick={() => void send(null)}>Not now</button>
      </div>
    </section>
  );
}

/** Family Home: NPS question (when due), vitals trend and the latest monthly letter. */
export function FamilyKushLifeExtras({ nps = true }: { nps?: boolean } = {}) {
  const [vitals, setVitals] = useState<VitalsSeries | null>(null);
  const [letters, setLetters] = useState<LetterItem[]>([]);
  useEffect(() => {
    familyApi<VitalsSeries>("/kushlife/vitals").then(setVitals).catch(() => undefined);
    familyApi<LetterItem[]>("/kushlife/letters").then(setLetters).catch(() => undefined);
  }, []);
  return (
    <>
      {nps ? <NpsPrompt /> : null}
      {letters.length ? (
        <section className="card home-safety-section" aria-labelledby="kq-letter-h">
          <h2 id="kq-letter-h">Monthly KushLife letter</h2>
          <nav className="fh-actions" aria-label="KushLife letters">
            <Link className="fh-action is-primary" href={`/kushalaya/family/documents/letters/${letters[0].id}`}>
              Read {letters[0].month_label}
            </Link>
            {letters.length > 1 ? (
              <Link className="fh-action" href="/kushalaya/family/documents">
                Earlier letters
              </Link>
            ) : null}
          </nav>
        </section>
      ) : null}
      {vitals?.points.length ? (
        <section className="card home-safety-section">
          <VitalsTrend data={vitals} />
        </section>
      ) : null}
    </>
  );
}

/** Documents page: every approved monthly letter. */
export function FamilyLetterList() {
  const [letters, setLetters] = useState<LetterItem[]>([]);
  useEffect(() => {
    familyApi<LetterItem[]>("/kushlife/letters").then(setLetters).catch(() => undefined);
  }, []);
  if (!letters.length) return null;
  return (
    <section className="card home-safety-section" aria-labelledby="kq-letters-h">
      <h2 id="kq-letters-h">Monthly KushLife letters</h2>
      <ul>
        {letters.map((l) => (
          <li key={l.id}><Link href={`/kushalaya/family/documents/letters/${l.id}`}>{l.month_label}</Link></li>
        ))}
      </ul>
    </section>
  );
}
