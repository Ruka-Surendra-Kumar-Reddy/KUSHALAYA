"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { formatIST } from "@/lib/ist";
import "./kushlife.css";
import { publicSafetyScoreName } from "@/lib/public-brand";

type Explain = {
  has_score: boolean;
  score?: number;
  assessed_at?: string | null;
  assessor?: string | null;
  questions_total?: number;
  na_count?: number;
  areas?: { title: string; score: number }[];
  top_drags?: { label: string; area: string; rating: string; lost: number; critical: boolean }[];
  critical?: { label: string; area: string }[];
  previous?: number | null;
  grade?: string | null;
  grade_label?: string | null;
  capped?: boolean;
  answers?: { label: string; area: string; rating: string; lost: number }[] | null;
  how: { steps: string[]; bands: { min: number; grade: string; label: string }[]; sources: string; scale: string };
};

/** "Why this score?" — a sheet explaining the Independence Score™ in plain words. */
export function ScoreWhyButton({ url, label = "Why this score?" }: { url: string; label?: string }) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  return (
    <>
      <button ref={trigger} type="button" className="kl-link" onClick={() => setOpen(true)}>
        {label}
      </button>
      {open ? (
        <ScoreWhySheet
          url={url}
          onClose={() => {
            setOpen(false);
            trigger.current?.focus();
          }}
        />
      ) : null}
    </>
  );
}

function ScoreWhySheet({ url, onClose }: { url: string; onClose: () => void }) {
  const [data, setData] = useState<Explain | null>(null);
  const [error, setError] = useState("");
  const [all, setAll] = useState(false);
  const sheet = useRef<HTMLDivElement>(null);
  const closeBtn = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    api<Explain>(url).then(setData).catch((e) => setError(e instanceof Error ? e.message : "Could not load"));
  }, [url]);

  useEffect(() => {
    closeBtn.current?.focus();
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key !== "Tab" || !sheet.current) return;
      // Keep Tab inside the sheet.
      const items = sheet.current.querySelectorAll<HTMLElement>("button, a[href]");
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  // The published band: a critical item marked Risk caps it, whatever the number.
  const fallback = data?.has_score ? data.how.bands.find((b) => (data.score ?? 0) >= b.min) : null;
  const grade = data?.grade || fallback?.grade;
  const gradeLabel = data?.grade_label || fallback?.label;

  return (
    <div className="kl-sheet-backdrop" onClick={onClose}>
      <div
        ref={sheet}
        className="kl-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="kl-why-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="kl-sheet-head">
          <h2 id="kl-why-title">{data?.has_score ? `How we got ${data.score}` : `How the ${publicSafetyScoreName()} works`}</h2>
          <button ref={closeBtn} type="button" className="kl-x" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </div>
        {error ? <p className="kl-muted">{error}</p> : null}
        {!data ? <p className="kl-muted">Loading…</p> : null}
        {data ? (
          <>
            <p className="kl-muted">
              {data.how.scale}
              {grade ? ` Band: “${grade}”${gradeLabel ? ` — ${gradeLabel.toLowerCase()}` : ""}.` : ""}
            </p>
            {data.capped && data.critical?.length ? (
              <p className="kl-capped">
                The number is {data.score}, but {data.critical.length} critical item
                {data.critical.length === 1 ? " is" : "s are"} marked Risk, so the band stays {grade} until
                {data.critical.length === 1 ? " it is" : " they are"} fixed.
              </p>
            ) : null}
            {data.has_score ? (
              <p>
                Assessed {formatIST(data.assessed_at, { dateOnly: true })}
                {data.assessor ? ` by ${data.assessor}` : ""}
                {data.previous != null ? ` · last time ${data.previous} → now ${data.score} (${(data.score ?? 0) - data.previous >= 0 ? "+" : ""}${(data.score ?? 0) - data.previous})` : ""}
              </p>
            ) : null}

            <h3>How it works</h3>
            <ol>
              {data.how.steps.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ol>

            {data.critical && data.critical.length ? (
              <>
                <h3>Critical items to fix first</h3>
                <ul>
                  {data.critical.map((c) => (
                    <li key={c.label}>
                      {c.label} <span className="kl-muted">({c.area})</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}

            {data.top_drags && data.top_drags.length ? (
              <>
                <h3>What’s pulling it down</h3>
                <ol>
                  {data.top_drags.map((d) => (
                    <li key={d.label}>
                      <span className="kl-drag">
                        <span>
                          {d.label} <span className="kl-muted">· {d.area} · {d.rating}</span>
                        </span>
                        <b>−{d.lost} pts</b>
                      </span>
                    </li>
                  ))}
                </ol>
              </>
            ) : null}

            {data.areas && data.areas.length ? (
              <>
                <h3>Area by area</h3>
                <ul>
                  {data.areas.map((a) => (
                    <li key={a.title}>
                      {a.title}: {a.score}/100
                    </li>
                  ))}
                </ul>
              </>
            ) : null}

            {data.na_count ? <p className="kl-muted">Not counted: {data.na_count} questions that don’t apply to this home.</p> : null}

            {data.answers && data.answers.length ? (
              <>
                <button type="button" className="kl-link" onClick={() => setAll((v) => !v)}>
                  {all ? "Hide all answers" : `Show all ${data.answers.length} answers`}
                </button>
                {all ? (
                  <ul>
                    {data.answers.map((a) => (
                      <li key={`${a.area}${a.label}`}>
                        {a.label} — {a.rating}
                        {a.lost ? <span className="kl-muted"> (−{a.lost})</span> : null}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </>
            ) : null}
            <p className="kl-muted">{data.how.sources}</p>
          </>
        ) : null}
      </div>
    </div>
  );
}
