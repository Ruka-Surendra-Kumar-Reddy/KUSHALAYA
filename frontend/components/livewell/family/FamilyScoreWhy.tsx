"use client";

import { useEffect, useRef, useState } from "react";
import { familyApi, fetchFamilyImprovementPlan } from "@/lib/livewell/familyApi";
import { familyDate } from "@/lib/livewell/familyTime";
import { findingNeed, plainAreaName } from "@/lib/livewell/familyFindings";
import { plainWords } from "@/lib/livewell/familyWords";
import { projectedScore } from "@/lib/livewell/familyPlan";
import { publicSafetyScoreName } from "@/lib/public-brand";
import "@/components/kushlife.css";

type Explain = {
  has_score: boolean;
  score?: number;
  assessed_at?: string | null;
  assessor?: string | null;
  na_count?: number;
  areas?: { title: string; score: number }[];
  top_drags?: { label: string; area: string; rating: string; critical: boolean }[];
  critical?: { label: string; area: string }[];
  previous?: number | null;
  grade?: string | null;
  grade_label?: string | null;
  how: { steps: string[]; bands: { min: number; grade: string; label: string }[]; sources: string; scale: string };
};

/**
 * Family "Why this score?": the same problem wording as What we found
 * (familyFindings), left-aligned, and one points figure that matches /plan
 * (the projected score) instead of per-answer decimals.
 */
export function FamilyScoreWhyButton({ label = "Why this score?" }: { label?: string }) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  return (
    <>
      <button ref={trigger} type="button" className="kl-link fh-why-btn" onClick={() => setOpen(true)}>
        {label}
      </button>
      {open ? (
        <FamilyScoreWhySheet
          onClose={() => {
            setOpen(false);
            trigger.current?.focus();
          }}
        />
      ) : null}
    </>
  );
}

const areaWords = (a: string) => plainWords(plainAreaName(a));

function FamilyScoreWhySheet({ onClose }: { onClose: () => void }) {
  const [data, setData] = useState<Explain | null>(null);
  const [projected, setProjected] = useState<number | null>(null);
  const [error, setError] = useState("");
  const sheet = useRef<HTMLDivElement>(null);
  const closeBtn = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    familyApi<Explain>("/score-explain")
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load"));
    fetchFamilyImprovementPlan()
      .then((p) => setProjected(projectedScore(p.current_score, p.items)))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    closeBtn.current?.focus();
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key !== "Tab" || !sheet.current) return;
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

  const fallback = data?.has_score ? data.how.bands.find((b) => (data.score ?? 0) >= b.min) : null;
  const grade = data?.grade || fallback?.grade;
  const gradeLabel = data?.grade_label || fallback?.label;
  const criticalLabels = new Set((data?.critical ?? []).map((c) => c.label));
  const drags = (data?.top_drags ?? []).filter((d) => !criticalLabels.has(d.label));
  const gain = projected != null && data?.score != null && projected > data.score ? projected - data.score : null;

  return (
    <div className="kl-sheet-backdrop" onClick={onClose}>
      <div
        ref={sheet}
        className="kl-sheet fh-why-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="fh-why-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="kl-sheet-head">
          <h2 id="fh-why-title">
            {data?.has_score ? `How we got ${data.score}` : `How the ${publicSafetyScoreName()} works`}
          </h2>
          <button ref={closeBtn} type="button" className="kl-x" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </div>
        {error ? <p className="kl-muted">{error}</p> : null}
        {!data && !error ? <p className="kl-muted">Loading…</p> : null}
        {data ? (
          <>
            <p className="kl-muted">
              {data.how.scale}
              {grade ? ` Band: “${grade}”${gradeLabel ? ` — ${gradeLabel.toLowerCase()}` : ""}.` : ""}
            </p>
            {data.has_score ? (
              <p>
                Assessed {data.assessed_at ? familyDate(data.assessed_at) : "recently"}
                {data.assessor ? ` by ${data.assessor}` : ""}
                {data.previous != null ? ` · last time ${data.previous}, now ${data.score}` : ""}
              </p>
            ) : null}
            {gain != null ? (
              <p className="fh-why-gain">
                Doing the fixes in your plan could add about {gain} points ({data.score} → about {projected}).
              </p>
            ) : null}

            {data.critical && data.critical.length ? (
              <>
                <h3>Fix these first</h3>
                <ul>
                  {data.critical.map((c) => (
                    <li key={c.label}>
                      {plainWords(findingNeed(c.label))} <span className="kl-muted">· {areaWords(c.area)}</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}

            {drags.length ? (
              <>
                <h3>Also lowering the score</h3>
                <ul>
                  {drags.map((d) => (
                    <li key={d.label}>
                      {plainWords(findingNeed(d.label))}{" "}
                      <span className="kl-muted">
                        · {areaWords(d.area)} · {d.rating}
                      </span>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}

            <h3>How it works</h3>
            <ol>
              {data.how.steps.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ol>

            {data.areas && data.areas.length ? (
              <>
                <h3>Area by area</h3>
                <ul>
                  {data.areas.map((a) => (
                    <li key={a.title}>
                      {areaWords(a.title)}: {a.score}/100
                    </li>
                  ))}
                </ul>
              </>
            ) : null}

            {data.na_count ? (
              <p className="kl-muted">Not counted: {data.na_count} questions that don’t apply to this home.</p>
            ) : null}
            <p className="kl-muted">{data.how.sources}</p>
          </>
        ) : null}
      </div>
    </div>
  );
}
