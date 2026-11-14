"use client";

import { withPublicBrand } from "@/lib/public-brand";

import { useEffect, useState } from "react";
import { FamilyShell } from "@/components/livewell/family/FamilyShell";
import { FamilyLink as Link } from "@/components/livewell/family/FamilyLink";
import { SafetyScoreCard } from "@/components/livewell/family/SafetyScoreCard";
import { FamilyError } from "@/components/livewell/family/FamilyError";
import { FamilyPhotosSection } from "@/components/livewell/family/FamilyPhotosSection";
import { FamilyRoomHazards } from "@/components/livewell/family/FamilyRoomHazards";
import { dayMonth } from "@/lib/ist";
import { familyDate } from "@/lib/livewell/familyTime";
import { findingNeed, findingProblem, urgentFindings } from "@/lib/livewell/familyFindings";
import { plainWords } from "@/lib/livewell/familyWords";
import { fixesTotal, groupByNeed, projectedScore } from "@/lib/livewell/familyPlan";
import {
  createFamilyServiceRequest,
  familyApi,
  fetchFamilyImprovementPlan,
  fetchFamilySafetyScore,
  type FamilyImprovementPlan,
  type FamilySafetyScore,
} from "@/lib/livewell/familyApi";
import { fetchFamilyProducts, type FamilyProduct } from "@/lib/family-money";
import { FamilyProductCard, FamilyProductSheet } from "@/components/livewell/family/FamilyProductCard";
import { alignSuggestionItems } from "@/lib/family-catalog";

/** Subset of /score-explain the family page uses. */
type ScoreExplain = {
  has_score: boolean;
  questions_total?: number;
  top_drags?: { label: string; area: string; rating: string; critical: boolean }[];
  critical?: { label: string; area: string }[];
  history?: { total: number; at: string | null }[];
};

type Recommended = {
  score: number | null;
  items: {
    product_id: number;
    name: string;
    priority: "high" | "medium";
    price_with_gst_paise: number | null;
    reasons: string[];
  }[];
};

type TierKey = "urgent" | "soon" | "later";
const TIERS: { key: TierKey; title: string; sub: string }[] = [
  { key: "urgent", title: "Urgent — fix first", sub: "A serious risk of a fall or injury." },
  { key: "soon", title: "Fix soon", sub: "A risk found at the assessment." },
  { key: "later", title: "Can wait", sub: "Worth doing when convenient." },
];

const rupees = (paise: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paise / 100);

export default function FamilySafetyPage() {
  const [score, setScore] = useState<FamilySafetyScore | null>(null);
  const [error, setError] = useState("");
  const [recommended, setRecommended] = useState<Recommended | null>(null);
  const [asked, setAsked] = useState<Record<string, boolean>>({});
  // Catalog rows (picture, plain words, price) so fixes look the same as on Requests.
  const [catalog, setCatalog] = useState<Map<number, FamilyProduct>>(new Map());
  const [viewing, setViewing] = useState<FamilyProduct | null>(null);
  const [explain, setExplain] = useState<ScoreExplain | null>(null);
  const [plan, setPlan] = useState<FamilyImprovementPlan | null>(null);
  const [hazards, setHazards] = useState<
    { id: string; note: string; product_name: string; status: string; spotted_at: string; fixed_at: string | null }[]
  >([]);
  // Reviewed incident reports only, in plain words (#97).
  const [incidents, setIncidents] = useState<
    { id: number; kind_label: string; occurred_at: string | null; summary: string; status: string; serious?: boolean }[]
  >([]);

  function load() {
    setError("");
    fetchFamilySafetyScore()
      .then(setScore)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }

  useEffect(() => {
    load();
    familyApi<Recommended>("/suggestions").then(setRecommended).catch(() => undefined);
    familyApi<typeof hazards>("/hazards").then(setHazards).catch(() => undefined);
    familyApi<typeof incidents>("/incident-reports").then(setIncidents).catch(() => undefined);
    familyApi<ScoreExplain>("/score-explain").then(setExplain).catch(() => undefined);
    fetchFamilyImprovementPlan().then(setPlan).catch(() => undefined);
    fetchFamilyProducts()
      .then((rows) => setCatalog(new Map(rows.map((r) => [r.id, r]))))
      .catch(() => undefined);
  }, []);

  async function ask(name: string, productId?: number) {
    setViewing(null);
    await createFamilyServiceRequest({
      service_type: "product",
      product_name: name,
      product_id: productId,
      notes: "From the assessment recommendations",
    });
    setAsked((a) => ({ ...a, [name]: true }));
  }

  const domains = [...(score?.domain_scores ?? [])].sort((a, b) => a.score - b.score);
  // Risks in plain words: urgent (critical) ones first, then what costs the most points.
  // One urgent list: the published score's critical findings (Home's "N critical",
  // the hero's "Fix first" and /plan read the same), else the explain endpoint's.
  const critical = score?.critical_findings?.length ? score.critical_findings : explain?.critical ?? [];
  const urgentLabels = new Set(critical.map((c) => c.label));
  const urgentNeeds = new Set(urgentFindings(critical));
  const findings = [
    ...critical.map((c) => ({ label: c.label, area: c.area, rating: "Risk", urgent: true })),
    ...(explain?.top_drags ?? [])
      // A question nobody answered is not a finding.
      .filter((d) => !urgentLabels.has(d.label) && (d.rating === "Risk" || d.rating === "Needs attention"))
      .map((d) => ({ label: d.label, area: d.area, rating: d.rating, urgent: false })),
  ].slice(0, 6);
  /** The same three words on findings and on fixes. */
  const tierWord = (urgent: boolean, rating: string) =>
    urgent ? TIERS[0].title : rating === "Risk" ? TIERS[1].title : TIERS[2].title;
  // A finding only reads as done when its plan item is marked done.
  const doneTitles = new Set(
    (plan?.items ?? []).filter((i) => i.status === "done").map((i) => i.title.trim().toLowerCase()),
  );
  // Products for the same need are alternatives, so they are never added up:
  // each need shows "from ₹x" (the cheapest option). Money stays in paise.
  // Product ↔ finding pairs re-checked against the catalog map (night light for a
  // dark bedroom, not a bed rail), the same as on Requests.
  // Every urgent finding gets its product when the catalog has one (smoke alarm → smoke detector).
  const recItems = recommended
    ? alignSuggestionItems(recommended.items, [...catalog.values()], [...urgentLabels])
    : [];
  const needs = groupByNeed(recItems);
  // Each need sits under one heading: urgent (critical finding), fix soon (a Risk), or can wait.
  const tierOf = (need: string, items: typeof recItems): TierKey =>
    urgentNeeds.has(need) || items.some((i) => i.reasons.some((r) => urgentNeeds.has(findingNeed(r))))
      ? "urgent"
      : items.some((i) => i.priority === "high")
        ? "soon"
        : "later";
  const tiers = TIERS.map((t) => ({ ...t, needs: [...needs.entries()].filter(([need, items]) => tierOf(need, items) === t.key) })).filter(
    (t) => t.needs.length > 0,
  );
  // Same figure as /plan: the cheapest priced option per need, added up.
  const total = fixesTotal(needs, (i) =>
    catalog.has(i.product_id) ? catalog.get(i.product_id)!.price_with_gst_paise : i.price_with_gst_paise,
  );
  const fromPrice = (items: NonNullable<typeof recommended>["items"]) => {
    // Use the price each card shows (catalog first), so a need whose options all
    // say "We'll quote after a visit" never gets a "from ₹x".
    const prices = items
      .map((i) => (catalog.has(i.product_id) ? catalog.get(i.product_id)!.price_with_gst_paise : i.price_with_gst_paise))
      .filter((p): p is number => !!p);
    return prices.length ? Math.min(...prices) : null;
  };
  // Some options under a need have no price (quoted after a visit).
  const someUnpriced = (items: NonNullable<typeof recommended>["items"]) =>
    items.some((i) => !(catalog.has(i.product_id) ? catalog.get(i.product_id)!.price_with_gst_paise : i.price_with_gst_paise));
  const history = explain?.history ?? [];
  const current = plan?.current_score ?? score?.total ?? null;
  // Worked out from the open plan items' points (never a flat "100").
  const projected = projectedScore(current, plan?.items);

  return (
    <FamilyShell
      title="Score & plan"
      subtitle={withPublicBrand("LiveWell360 Safety Score, what we found, fixes and photos")}
    >
      <FamilyError message={error} onRetry={load} what="the score" />
      {!score ? (
        error ? null : <p>Loading…</p>
      ) : (
        <>
          <SafetyScoreCard score={score} openFixes={recItems.length} />
          <p className="muted" style={{ fontSize: "0.85rem", margin: "0.5rem 0 1rem", lineHeight: 1.5 }}>
            Out of 100, higher is safer. We checked {explain?.questions_total || "about 60"} things in the home.
            Safe gets full points, Needs attention gets half, and Risk gets none.
            {projected != null && current != null && projected > current ? (
              <>
                {" "}
                <strong>
                  After fixes: {current} → about {projected}
                </strong>
              </>
            ) : plan?.items.length ? (
              <> Score goes up as fixes are done.</>
            ) : null}
          </p>

          {history.length > 1 ? (
            <section className="card home-safety-section">
              <h2>Score over time</h2>
              <ul className="home-safety-family-domain-list">
                {history.map((h, i) => (
                  <li key={`${h.at ?? ""}-${i}`}>
                    <div className="home-safety-family-domain-row">
                      <span>{h.at ? familyDate(h.at) : "Earlier"}</span>
                      <strong>{h.total}</strong>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <FamilyRoomHazards />

          {findings.length ? (
            <section className="card home-safety-section">
              <h2>What we found</h2>
              <p className="muted" style={{ fontSize: "0.85rem", marginBottom: "0.75rem" }}>
                The things that lower the score most, from the last assessment.
              </p>
              <ul className="fh-rec">
                {findings.map((f) => {
                  const fixed = doneTitles.has(f.label.trim().toLowerCase());
                  return (
                  <li
                    key={f.label}
                    className={fixed ? "is-fixed" : f.urgent || f.rating === "Risk" ? "is-high" : ""}
                  >
                    <div>
                      <strong>{plainWords(fixed ? `${f.label} — fixed` : findingProblem(f.label))}</strong>
                      <span>
                        {plainWords(f.area.replace(/^\s*\d+[.)]\s*/, ""))} ·{" "}
                        {fixed ? "Done" : tierWord(f.urgent, f.rating)}
                      </span>
                    </div>
                  </li>
                  );
                })}
              </ul>
            </section>
          ) : null}

          {hazards.length ? (
            <section className="card home-safety-section">
              <h2>Spotted on visits</h2>
              <p className="muted" style={{ fontSize: "0.85rem", marginBottom: "0.75rem" }}>
                Hazards your caregiver noticed on visits, and what has been done about them.
              </p>
              <ul className="fh-rec">
                {hazards.map((h) => (
                  <li key={h.id} className={h.status === "fixed" ? "is-fixed" : "is-high"}>
                    <div>
                      <strong>{h.note || h.product_name || "Home safety hazard"}</strong>
                      <span>
                        Spotted {familyDate(h.spotted_at)}
                        {h.product_name ? ` · fix: ${h.product_name}` : ""}
                      </span>
                    </div>
                    <span className="fh-rec-done">
                      {h.status === "fixed"
                        ? `Fixed ${h.fixed_at ? familyDate(h.fixed_at) : ""} ✓`
                        : h.status === "ordered"
                          ? "Being fixed"
                          : "Your care team is on it"}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {incidents.length ? (
            <section className="card home-safety-section">
              <h2>Incident reports</h2>
              <p className="muted" style={{ fontSize: "0.85rem", marginBottom: "0.75rem" }}>
                Falls and other incidents, once your Family Partner has reviewed them.
              </p>
              <ul className="fh-rec">
                {incidents.map((r) => (
                  <li key={r.id} className={`fh-inc${r.status !== "Closed" && r.serious ? " is-high" : ""}`}>
                    <div>
                      <strong>
                        {r.kind_label}
                        {r.occurred_at ? ` · ${dayMonth(new Date(r.occurred_at))}` : ""}
                      </strong>
                      <span>{r.summary}</span>
                    </div>
                    <span className={`fh-inc-status${r.status === "Closed" ? " is-closed" : ""}`}>
                      {r.status === "Closed" ? "Closed" : "Checked by your Family Partner"}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {recItems.length ? (
            <section id="fixes" className="card home-safety-section fh-anchor">
              <h2>What to fix and the cost</h2>
              <p className="muted" style={{ fontSize: "0.85rem", marginBottom: "0.75rem" }}>
                From the last assessment, most urgent first. Options under one need are alternatives — you
                usually need just one. Prices include GST. Your care team arranges the fitting.
              </p>
              {total.priced ? (
                <p className="fh-fix-total">
                  Indicative total: from {rupees(total.paise)}
                  {total.unpriced ? ` · ${total.unpriced} quoted after a visit` : ""}
                </p>
              ) : null}
              {tiers.map((t) => (
                <div key={t.key} className={`fh-tier is-${t.key}`}>
                  <h3 className="fh-tier-title">{t.title}</h3>
                  <p className="fh-tier-sub">{t.sub}</p>
              {t.needs.map(([need, items]) => {
                const from = fromPrice(items);
                return (
                  <div key={need} className="fh-need">
                    <h4 className="fh-need-title">
                      {plainWords(need)}
                      {from ? (
                        <span className="fh-need-from">
                          {" "}
                          · from {rupees(from)}
                          {someUnpriced(items) ? " (some options quoted after a visit)" : ""}
                        </span>
                      ) : (
                        <span className="fh-need-from"> · free quote at the next visit</span>
                      )}
                    </h4>
                    <ul className="fh-prod-list">
                      {items.map((i) => {
                        // Same card as Requests; fall back to the suggestion itself if the catalog didn't load.
                        const p: FamilyProduct = catalog.get(i.product_id) ?? {
                          id: i.product_id,
                          product_code: "",
                          name: i.name,
                          category: "",
                          description: "",
                          kind: "product",
                          unit: "",
                          included: "",
                          image_url: null,
                          price_paise: 0,
                          price_with_gst_paise: i.price_with_gst_paise ?? 0,
                          recommended: true,
                          reasons: i.reasons,
                        };
                        return (
                          <FamilyProductCard
                            key={i.product_id}
                            p={p}
                            onOpen={setViewing}
                            onRequest={(x) => void ask(x.name, x.id)}
                            requested={!!asked[i.name]}
                            note={
                              i.reasons.length > 1
                                ? `Also helps: ${i.reasons.slice(1, 3).map(findingNeed).join(" · ")}`
                                : undefined
                            }
                          />
                        );
                      })}
                    </ul>
                  </div>
                );
              })}
                </div>
              ))}
              <Link href="/kushalaya/family/services" className="home-safety-family-inline-link">
                See your requests →
              </Link>
            </section>
          ) : null}



          {domains.length > 0 ? (
            <section className="card home-safety-section">
              <h2>Area by area</h2>
              <p className="muted" style={{ fontSize: "0.85rem", marginBottom: "0.75rem" }}>
                Lower numbers need more attention. Weakest first.
              </p>
              <ul className="home-safety-family-domain-list">
                {domains.map((d) => (
                  <li key={d.id}>
                    <div className="home-safety-family-domain-row">
                      <span>{plainWords(d.title.replace(/^\s*\d+[.)]\s*/, ""))}</span>
                      <strong>{d.score}</strong>
                    </div>
                    <div className="home-safety-family-domain-bar" aria-hidden>
                      <span style={{ width: `${Math.max(4, d.score)}%` }} />
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="card home-safety-section">
            <h2>What this means</h2>
            <p className="muted" style={{ fontSize: "0.9rem", lineHeight: 1.5 }}>
              The {withPublicBrand("LiveWell360 Safety Score")} (0–100) covers bathroom safety, moving around, lighting,
              emergency readiness and other things we checked in the home.{" "}
              <strong>Excellent / Good</strong> means living largely independently;{" "}
              <strong>Moderate / High Risk</strong> means some fixes are worth doing soon;{" "}
              <strong>Critical</strong>{" "}
              {withPublicBrand("needs attention now with your LiveWell360 team.")}
            </p>
          </section>

          <p id="plan" className="fh-anchor">
            <Link href="/kushalaya/family/plan" className="home-safety-family-inline-link">
              See the full plan and what it will look like after fixes →
            </Link>
          </p>
        </>
      )}

      <FamilyPhotosSection />
      <FamilyProductSheet
        p={viewing}
        onClose={() => setViewing(null)}
        onRequest={(x) => void ask(x.name, x.id)}
        requested={!!(viewing && asked[viewing.name])}
      />
    </FamilyShell>
  );
}
