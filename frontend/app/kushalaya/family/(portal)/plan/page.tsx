"use client";

import { withPublicBrand } from "@/lib/public-brand";

import { FamilyLink as Link } from "@/components/livewell/family/FamilyLink";
import { useEffect, useState } from "react";
import { FamilyShell } from "@/components/livewell/family/FamilyShell";
import {
  familyApi,
  fetchFamilyImprovementPlan,
  fetchFamilySafetyScore,
  type FamilyImprovementPlan,
} from "@/lib/livewell/familyApi";
import { fetchFamilyProducts } from "@/lib/family-money";
import { alignSuggestionItems, type SuggestionItem } from "@/lib/family-catalog";
import { plainWords } from "@/lib/livewell/familyWords";
import { planTitle } from "@/lib/livewell/familyFindings";
import { fixesTotal, groupByNeed, projectedScore } from "@/lib/livewell/familyPlan";

type Suggestion = SuggestionItem;

const rupees = (paise: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paise / 100);

/** Plain words for families (not "CRITICAL | OPEN"). */
function priorityWords(priority: string): string {
  const p = priority.toLowerCase();
  // Only critical items are "Urgent", so the count matches Home's "N critical".
  if (p === "critical") return "Urgent";
  if (p === "high") return "Important";
  if (p === "medium") return "Soon";
  return "When you can";
}
function statusWords(status: string): string {
  const s = status.toLowerCase();
  if (s === "done") return "Done";
  if (s === "scheduled") return "Booked";
  return "To do";
}
/** "3. Bathroom" / "D3 Bathroom" → "Bathroom". */
const areaName = (d: string) => d.replace(/^\s*(?:[A-Z]?\d+[.)]?|[A-Z]\d*[.)])\s*/, "");

export default function FamilyPlanPage() {
  const [plan, setPlan] = useState<FamilyImprovementPlan | null>(null);
  const [error, setError] = useState("");
  // Same sources as Home and /safety, so the counts and the total match.
  const [urgentCount, setUrgentCount] = useState<number | null>(null);
  const [total, setTotal] = useState<ReturnType<typeof fixesTotal> | null>(null);

  useEffect(() => {
    fetchFamilyImprovementPlan()
      .then(setPlan)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
    const score = fetchFamilySafetyScore();
    score.then((s) => setUrgentCount(s.urgent_fix_count ?? 0)).catch(() => undefined);
    Promise.all([
      familyApi<{ items: Suggestion[] }>("/suggestions"),
      fetchFamilyProducts().catch(() => []),
      score.catch(() => null),
    ])
      .then(([sug, products, s]) => {
        const price = new Map(products.map((p) => [p.id, p.price_with_gst_paise]));
        // Same pairs and the same sum as Score & plan (urgent findings get their product too).
        const urgent = (s?.critical_findings ?? []).map((c) => c.label);
        const items = alignSuggestionItems(sug.items ?? [], products, urgent);
        setTotal(
          fixesTotal(groupByNeed(items), (i) =>
            price.has(i.product_id) ? price.get(i.product_id) ?? null : i.price_with_gst_paise,
          ),
        );
      })
      .catch(() => undefined);
  }, []);

  return (
    <FamilyShell
      title="Living improvement plan"
      subtitle="Priorities from the latest assessment"
    >
      {error ? <p className="error-text">{error}</p> : null}
      {!plan ? (
        <p>Loading…</p>
      ) : !plan.has_plan ? (
        <section className="card home-safety-section">
          <p className="muted">
            {withPublicBrand("No published plan yet. After a completed LiveWell360 assessment is linked to\r\n            this senior, recommended improvements appear here.")}
          </p>
          <Link href="/kushalaya/family/dashboard" className="home-safety-family-inline-link">
            ← Back to home
          </Link>
        </section>
      ) : (
        <>
          <div className="home-safety-family-kpis">
            <div className="home-safety-family-kpi">
              <span className="muted">Score now</span>
              <strong>{plan.current_score ?? "—"}</strong>
            </div>
            <div className="home-safety-family-kpi">
              <span className="muted">After the fixes</span>
              {projectedScore(plan.current_score, plan.items) != null ? (
                <strong>about {projectedScore(plan.current_score, plan.items)}</strong>
              ) : (
                <span>Score goes up as fixes are done</span>
              )}
            </div>
            <div className="home-safety-family-kpi">
              <span className="muted">Still to do</span>
              <strong>
                {plan.items.filter((i) => i.status !== "done").length}
              </strong>
            </div>
          </div>

          {urgentCount ? (
            <p className="muted home-safety-family-cost-note">
              The assessment found {urgentCount} urgent {urgentCount === 1 ? "fix" : "fixes"} (the same{" "}
              {urgentCount} shown on Home and Score &amp; plan). The plan groups them into{" "}
              {plan.items.filter((i) => i.priority.toLowerCase() === "critical").length} urgent{" "}
              {plan.items.filter((i) => i.priority.toLowerCase() === "critical").length === 1 ? "step" : "steps"} below.
            </p>
          ) : null}

          {total?.priced ? (
            <p className="muted home-safety-family-cost-note">
              Indicative total: from {rupees(total.paise)} for the recommended fixes, incl. GST
              {total.unpriced ? ` · ${total.unpriced} quoted after a visit` : ""}. The same figure is on Score &amp; plan.
            </p>
          ) : plan.estimated_cost_note ? (
            <p className="muted home-safety-family-cost-note">{plan.estimated_cost_note}</p>
          ) : null}

          <ul className="home-safety-family-plan-list">
            {plan.items.map((item) => (
              <li key={item.id} className="card home-safety-section">
                <div className="home-safety-family-plan-item-head">
                  <div className="home-safety-family-plan-badges">
                    <span className={`home-safety-family-priority-badge priority-${item.priority}`}>
                      {priorityWords(item.priority)}
                    </span>
                    <span className={`home-safety-family-status-badge status-${item.status}`}>
                      {statusWords(item.status)}
                    </span>
                  </div>
                  {item.score_gain > 0 ? (
                    <span className="muted">could add {item.score_gain} points</span>
                  ) : null}
                </div>
                <h2>{plainWords(planTitle(item.title))}</h2>
                {item.domain ? <p className="muted">{plainWords(areaName(item.domain))}</p> : null}
                {item.why ? <p>{plainWords(item.why)}</p> : null}
                {item.actions.length > 0 ? (
                  <ul className="home-safety-family-plan-actions">
                    {item.actions.map((action) => (
                      <li key={action}>{plainWords(action)}</li>
                    ))}
                  </ul>
                ) : null}
                {item.status !== "done" ? (
                  <p className="fh-plan-card-actions">
                    <Link href="/kushalaya/family/safety#fixes" className="fh-plan-card-link">
                      See options and prices →
                    </Link>
                    <Link href="/kushalaya/family/services#book" className="fh-plan-card-link">
                      Ask us to arrange it →
                    </Link>
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </>
      )}
    </FamilyShell>
  );
}
