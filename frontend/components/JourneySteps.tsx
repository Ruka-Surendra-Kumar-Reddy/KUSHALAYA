"use client";

import { formatIST } from "@/lib/ist";
import "./kushlife.css";

export type Journey = {
  steps: { key: string; label: string; state: "done" | "current" | "upcoming"; detail: string; owner: string; cta: string | null; date: string | null }[];
  current: string | null;
  next: { label: string; owner: string; cta: string | null } | null;
  score: number | null;
  target_score: number | null;
  spent_paise: number;
  remaining_paise: number;
};

const rupees = (p: number) => `₹${Math.round(p / 100).toLocaleString("en-IN")}`;

/** Assess → fixes → installed → KushLife visits → reassessment, with where we are now. */
/** Family wording for steps that are the family's to do. */
const FAMILY_NEXT: Record<string, string> = {
  "Fixes chosen": "choose which fixes you want",
};

export function JourneySteps({
  journey,
  onCta,
  family = false,
}: {
  journey: Journey;
  onCta?: (key: string) => void;
  /** Family portal: plain "Next: choose which fixes you want" wording. */
  family?: boolean;
}) {
  return (
    <div className="kl-trend">
      <div className="kl-trend-head">
        <h2>Care journey</h2>
        {journey.score != null && journey.target_score && journey.target_score > journey.score ? (
          <span className="kl-status">
            {family
              ? `Score ${journey.score} → about ${journey.target_score} after fixes`
              : `Score ${journey.score} → target ${journey.target_score}`}
          </span>
        ) : null}
      </div>
      <ol className="kl-journey">
        {journey.steps.map((s) => (
          <li key={s.key} className={`is-${s.state}`} aria-current={s.state === "current" ? "step" : undefined}>
            <strong>{s.label}</strong>
            <span>
              {s.detail}
              {s.date && s.key !== "fixes" && s.key !== "installed" ? ` · ${formatIST(s.date, { dateOnly: true })}` : ""}
            </span>
          </li>
        ))}
      </ol>
      {journey.next ? (
        <p className="kl-next">
          <strong>Next:</strong>{" "}
          {family && journey.next.owner === "Family"
            ? (FAMILY_NEXT[journey.next.label] ?? `${journey.next.label} (your turn)`)
            : `${journey.next.label} — ${journey.next.owner}`}
          {journey.next.cta && onCta ? (
            <>
              {" · "}
              <button type="button" className="kl-link" onClick={() => onCta(journey.current || "")}>
                {journey.next.cta}
              </button>
            </>
          ) : null}
        </p>
      ) : null}
      {journey.spent_paise || journey.remaining_paise ? (
        <p className="kl-muted">
          Spent {rupees(journey.spent_paise)} · still to pay {rupees(journey.remaining_paise)} (including GST)
        </p>
      ) : null}
    </div>
  );
}
