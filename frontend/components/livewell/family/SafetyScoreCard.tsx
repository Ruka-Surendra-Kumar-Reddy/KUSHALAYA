import { withPublicBrand } from "@/lib/public-brand";
import type { FamilySafetyScore } from "@/lib/livewell/familyApi";
import { gradeStatus } from "@/lib/livewell/familyApi";
import { familyDate } from "@/lib/livewell/familyTime";
import { safetyGradeFromScore } from "@/lib/livewell/assessment";
import { focusAreas, topPriorities, urgentFindings } from "@/lib/livewell/familyFindings";
import { plainWords } from "@/lib/livewell/familyWords";

export function SafetyScoreCard({
  score,
  compact = false,
  openFixes = 0,
}: {
  score: FamilySafetyScore;
  compact?: boolean;
  /** Fixes listed on the page; hides a stored summary that says there are none. */
  openFixes?: number;
}) {
  const published = score.has_published_score !== false && score.total > 0;
  // Capped by critical findings: say what it means instead of the band name.
  const urgent = published && (score.urgent_fix_count ?? 0) > 0 ? score.urgent_fix_count! : 0;
  // Higher is safer: without urgent fixes the band follows the score (shared
  // LWA_INDEPENDENCE_BANDS), so a stale stored "High Risk" never sits beside 91.
  const derived = published && !urgent ? safetyGradeFromScore(score.total) : null;
  const stale = derived != null && derived.status !== gradeStatus(score.grade, score.band_status);
  const status = derived ? derived.status : gradeStatus(score.grade, score.band_status);
  const grade = derived ? derived.grade : score.grade;
  const gradeLabel = derived ? derived.label : score.grade_label;
  const summary =
    score.summary && !stale && !(openFixes > 0 && /no open improvement items/i.test(score.summary))
      ? score.summary
      : null;
  // Lowest areas as chips (plain names, no section numbers). The stored summary
  // sentence was clamped and cut mid-word ("Top priorities: Unsaf…"); the ring
  // and chips already say the rest, so only its top priorities are listed.
  const areas = !compact && published ? focusAreas(summary, score.domain_scores) : [];
  // "Fix first" is the one urgent list (the critical findings), the same items as
  // "What we found", the sheet and /plan; the summary's plan titles only when there is none.
  const urgentList = urgentFindings(score.critical_findings);
  const priorities = !compact && published ? (urgentList.length ? urgentList : topPriorities(summary)) : [];
  return (
    <div
      className={`home-safety-score-card home-safety-grade-${status}${compact ? " compact" : ""}`}
    >
      <div className="home-safety-score-ring" aria-hidden>
        <span className="home-safety-score-value">{published ? score.total : "—"}</span>
        <span className="home-safety-score-max">/ {score.max_total}</span>
      </div>
      <div className="home-safety-score-meta">
        <span className="home-safety-grade-letter">
          {urgent ? `Some urgent fixes needed (${urgent})` : published ? grade : "Not published"}
        </span>
        <span className="home-safety-grade-label">
          {urgent
            ? "Fixing these first makes the biggest difference."
            : published
              ? gradeLabel
              : withPublicBrand("Waiting for LiveWell360 assessment")}
        </span>
        {score.assessed_at && (
          <span className="home-safety-completion">
            Assessed {familyDate(score.assessed_at)}
          </span>
        )}
      </div>
      {!compact && (priorities.length > 0 || areas.length > 0) ? (
        <div className="home-safety-score-foot">
          {priorities.length ? (
            <div className="home-safety-score-summary fh-score-priorities">
              <span>Fix first:</span>
              <ul>
                {priorities.map((p) => (
                  <li key={p}>{plainWords(p)}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {areas.length > 0 ? (
            <ul className="home-safety-focus-chips" aria-label="Areas to focus on">
              {areas.map((a) => (
                <li key={a.name}>
                  {a.name} · {a.score}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
