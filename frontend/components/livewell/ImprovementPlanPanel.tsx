"use client";

import type { HomeSafetyAssessment, AssessmentCategory } from "@/lib/livewell/assessment";
import {
  buildImprovementPlan,
  formatImprovementPlanText,
  safetyAgeProjection,
  type ImprovementPlan,
} from "@/lib/livewell/improvement-plan";
import type { SolutionLibrary } from "@/lib/livewell/solution-types";
import { SOLUTION_PRIORITY_META, SOLUTION_PRIORITY_ORDER } from "@/lib/livewell/solution-types";

export function ImprovementPlanPanel({
  assessment,
  categories,
  library,
}: {
  assessment: HomeSafetyAssessment;
  categories: AssessmentCategory[];
  library: SolutionLibrary;
}) {
  const plan = buildImprovementPlan(assessment, categories, library);
  const ages = safetyAgeProjection(assessment, plan);

  if (!plan.entries.length) {
    return (
      <section className="card home-safety-section home-safety-improvement-plan">
        <h2>Improvement plan</h2>
        <p className="muted">
          No findings matched the solution library yet. Rate checklist items{" "}
          <strong>Unsafe</strong> or <strong>Acceptable</strong> to generate recommendations.
        </p>
      </section>
    );
  }

  return (
    <section className="card home-safety-section home-safety-improvement-plan">
      <div className="home-safety-improvement-head">
        <h2>Improvement plan</h2>
        <p className="muted home-safety-improvement-score">
          Score {plan.currentScore} → <strong>{plan.projectedScore}</strong>
          <span className="home-safety-improvement-gain"> (+{plan.totalScoreGain} est.)</span>
          {ages.current != null && ages.projected != null && (
            <span className="home-safety-improvement-age">
              {" "}
              · Safety Age™ {ages.current} → {ages.projected}
            </span>
          )}
        </p>
      </div>

      {SOLUTION_PRIORITY_ORDER.map((priority) => (
        <PriorityGroup key={priority} priority={priority} plan={plan} />
      ))}

      <details className="home-safety-improvement-text">
        <summary className="muted">Plain-text plan (for copy / report)</summary>
        <pre>{formatImprovementPlanText(plan)}</pre>
      </details>
    </section>
  );
}

function PriorityGroup({
  priority,
  plan,
}: {
  priority: (typeof SOLUTION_PRIORITY_ORDER)[number];
  plan: ImprovementPlan;
}) {
  const entries = plan.byPriority[priority];
  if (!entries.length) return null;
  const meta = SOLUTION_PRIORITY_META[priority];

  return (
    <div className={`home-safety-improvement-group home-safety-priority-${priority}`}>
      <h3>
        {meta.label}{" "}
        <span className="muted home-safety-improvement-window">({meta.window})</span>
      </h3>
      <ul className="home-safety-improvement-list">
        {entries.map((entry) => (
          <li key={entry.solution.id} className="home-safety-improvement-item">
            <div className="home-safety-improvement-item-head">
              <strong>{entry.solution.name || entry.solution.finding}</strong>
              <span className="home-safety-improvement-id">{entry.solution.id}</span>
              {entry.solution.evidenceLevel ? (
                <span className="home-safety-improvement-id" title="Evidence level">
                  Evidence {entry.solution.evidenceLevel}
                </span>
              ) : null}
              <span className="home-safety-improvement-gain-pill">
                +{entry.solution.scoreImprovement}
              </span>
            </div>
            <p className="muted">{entry.solution.riskDescription}</p>
            <ul className="home-safety-improvement-actions">
              {entry.solution.recommendedSolutions.map((action) => (
                <li key={action}>{action}</li>
              ))}
            </ul>
            <p className="home-safety-improvement-meta muted">
              {[
                entry.solution.contractorType && `Contractor: ${entry.solution.contractorType}`,
                entry.solution.estimatedCost && `Cost: ${entry.solution.estimatedCost}`,
                entry.solution.installationTime && `Time: ${entry.solution.installationTime}`,
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
            <p className="home-safety-improvement-from muted">
              From:{" "}
              {entry.findings.map((f) => `${f.itemLabel} (${f.rating})`).join("; ")}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
