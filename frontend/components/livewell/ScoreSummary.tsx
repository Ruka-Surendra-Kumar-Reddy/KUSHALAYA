"use client";

import {
  assessmentBand,
  completionPercent,
  safetyAge,
  projectedSafetyAge,
  type AssessmentBand,
  type AssessmentCategory,
  type HomeSafetyAssessment,
} from "@/lib/livewell/assessment";
import { EMPTY_RESIDENT_PROFILE, parseResidentAge } from "@/lib/livewell/resident-profile";
import { dateTimeIST } from "@/lib/ist";
import { categoriesForAssessment } from "@/lib/livewell/conditional";
import { draftScoreText, isScoreFinal } from "@/lib/livewell/assessmentDisplay";

export type ScoreSummaryData = {
  band: AssessmentBand;
  complete: number;
  age: number | null;
  currentSafetyAge: number | null;
  projected: number | null;
};

/** One place for the score-card math — the wizard chip and the report reuse it. */
export function computeScoreSummary(
  assessment: HomeSafetyAssessment,
  categories: AssessmentCategory[],
): ScoreSummaryData {
  categories = categoriesForAssessment(categories, assessment);
  const profile = assessment.residentProfile ?? EMPTY_RESIDENT_PROFILE;
  const band = assessmentBand(categories, assessment.ratings, profile);
  const complete = completionPercent(categories, assessment.ratings, profile);
  const age = parseResidentAge(profile);
  const currentSafetyAge = age != null ? safetyAge(age, band.score) : null;
  const projected = age != null ? projectedSafetyAge(age, band.score) : null;
  return { band, complete, age, currentSafetyAge, projected };
}

export function ScoreSummary({
  assessment,
  categories,
}: {
  assessment: HomeSafetyAssessment;
  categories: AssessmentCategory[];
}) {
  const { band, complete, currentSafetyAge, projected } = computeScoreSummary(
    assessment,
    categories,
  );

  // A partly rated draft scores 0/100 "Critical" — misleading. Show progress until completed.
  if (!isScoreFinal(assessment.status)) {
    return (
      <div className="home-safety-score-card home-safety-score-card-draft">
        <div className="home-safety-score-meta">
          <span className="home-safety-grade-label">{draftScoreText(complete)}</span>
          <span className="home-safety-completion">Score shows once the assessment is completed.</span>
          <span className="home-safety-draft-badge">Draft — not saved yet</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`home-safety-score-card home-safety-grade-${band.status}`}>
      <div className="home-safety-score-ring" aria-hidden>
        <span className="home-safety-score-value">{band.score}</span>
        <span className="home-safety-score-max">/ 100</span>
      </div>
      <div className="home-safety-score-meta">
        <span className="home-safety-grade-letter">{band.grade}</span>
        <span className="home-safety-grade-label">{band.label}</span>
        {band.capped && (
          <span className="home-safety-critical-cap">
            Band capped at {band.grade}: {band.criticalFindings.length} critical item
            {band.criticalFindings.length === 1 ? "" : "s"} unsafe —{" "}
            {band.criticalFindings.map((f) => f.label).join("; ")}
          </span>
        )}
        {currentSafetyAge != null && (
          <span className="home-safety-safety-age">
            Safety Age™ {currentSafetyAge}
            {projected != null && projected < currentSafetyAge
              ? ` → ${projected} after improvements`
              : ""}
          </span>
        )}
        <span className="home-safety-completion">{complete}% complete</span>
        {assessment.status === "draft" ? (
          <span className="home-safety-draft-badge">Draft — not saved yet</span>
        ) : (
          <span className="home-safety-saved-badge">
            Saved {assessment.completedAt ? dateTimeIST(assessment.completedAt) : ""}
          </span>
        )}
      </div>
    </div>
  );
}

/** Compact live score for the wizard header — same math as the card, every step. */
export function LiveScoreChip({
  assessment,
  categories,
}: {
  assessment: HomeSafetyAssessment;
  categories: AssessmentCategory[];
}) {
  const { band, complete } = computeScoreSummary(assessment, categories);
  if (!isScoreFinal(assessment.status)) {
    return (
      <div className="home-safety-live-score home-safety-live-score-draft" role="status" aria-live="polite">
        <span className="home-safety-live-score-pct">{draftScoreText(complete)}</span>
      </div>
    );
  }
  return (
    <div
      className={`home-safety-live-score home-safety-grade-${band.status}`}
      role="status"
      aria-live="polite"
      title={band.capped ? `Band capped: ${band.criticalFindings.map((f) => f.label).join("; ")}` : undefined}
    >
      <span className="home-safety-live-score-value">
        {band.score}
        <small>/100</small>
      </span>
      <span className="home-safety-live-score-band">
        {band.grade}
        {band.capped ? " · capped" : ""}
      </span>
      <span className="home-safety-live-score-pct">{complete}% rated</span>
    </div>
  );
}
