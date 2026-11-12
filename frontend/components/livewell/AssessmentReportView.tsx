"use client";

import { useEffect, useState } from "react";
import "./assessment-report.css";
import { api } from "@/lib/api";
import { PublicBrandMark } from "@/components/BrandLogo";
import { SyncedPhotoThumb } from "@/components/livewell/AssessmentPhotos";
import { computeScoreSummary } from "@/components/livewell/ScoreSummary";
import { ageFromDob, draftScoreText, isScoreFinal } from "@/lib/livewell/assessmentDisplay";
import {
  clientDisplayName,
  computeDomainScores,
  LWA_INDEPENDENCE_BANDS,
  normalizeRating,
  safetyGradeFromScore,
  ratingLabel,
  type AssessmentCategory,
  type HomeSafetyAssessment,
} from "@/lib/livewell/assessment";
import { caregiverAnswers } from "@/lib/livewell/caregiver-answers";
import { answerLabel, hasCustomOptions } from "@/lib/livewell/question-options";
import { getApplicableCategories, categoriesForAssessment } from "@/lib/livewell/conditional";
import { buildImprovementPlan, type ImprovementPlanEntry } from "@/lib/livewell/improvement-plan";
import { EMPTY_RESIDENT_PROFILE } from "@/lib/livewell/resident-profile";
import { DEFAULT_SOLUTION_LIBRARY } from "@/lib/livewell/solution-defaults";
import { fetchAdminSolutions, getCachedSolutions } from "@/lib/livewell/solutionApi";
import type { SolutionLibrary, SolutionPriority } from "@/lib/livewell/solution-types";
import { useSafetyRubric } from "@/lib/livewell/useSafetyRubric";
import { hydratePhotoPreviews } from "@/lib/livewell/photoPersist";
import { fetchShowcaseCatalog } from "@/lib/livewell/catalogApi";
import { catalogProductImageSrc } from "@/lib/livewell/catalogImages";
import type { SafetyCatalog } from "@/lib/livewell/catalog-types";
import { buildProductRecommendations } from "@/lib/livewell/product-recommendations";
import { printPage } from "@/lib/native-app";
import { COMPANY_CIN, COMPANY_GSTIN, LEGAL_ENTITY_NAME, publicBrandName } from "@/lib/public-brand";

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d
    .toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" })
    .replace("Sept", "Sep");
}

/** Client record fields the report shows (GET /api/v1/elders/{id}). */
type ElderDetails = {
  date_of_birth?: string | null;
  gender?: string | null;
  phone?: string | null;
  address?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  custom_attributes?: Record<string, unknown> | null;
};

/** Urgent / Soon / Later — the plan's three groups. */
const GROUPS: { key: string; label: string; when: string; priorities: SolutionPriority[] }[] = [
  { key: "urgent", label: "Urgent", when: "Within 7 days", priorities: ["critical"] },
  { key: "soon", label: "Soon", when: "Within 30 days", priorities: ["high"] },
  { key: "later", label: "Later", when: "Within 90 days", priorities: ["medium", "low"] },
];
const STATUS_LABEL: Record<string, string> = {
  excellent: "Safe",
  acceptable: "Needs attention",
  unsafe: "Risk",
  na: "Not relevant",
};

const PRIORITY_RANK: Record<SolutionPriority, number> = { critical: 0, high: 1, medium: 2, low: 3 };

function groupOf(p: SolutionPriority) {
  return GROUPS.find((g) => g.priorities.includes(p)) ?? GROUPS[2];
}

const SHOW_FIRST = 8;

/** Band of a 0–100 score on the printed scale (area bars use the scale's colours). */
function bandStatus(score: number): string {
  return LWA_INDEPENDENCE_BANDS.find((b) => score >= b.min)?.status ?? "critical";
}

function tone(score: number): "good" | "fair" | "poor" {
  return score >= 75 ? "good" : score >= 50 ? "fair" : "poor";
}

/** Plain-language names for rubric areas (report display only; rubric data unchanged). */
const FRIENDLY_AREA: Record<string, string> = {
  "home safety": "Home safety",
  "mobility & accessibility": "Moving around",
  "health & wellness": "Health",
  "activities of daily living (adl)": "Daily self-care",
  "instrumental adls (iadl)": "Household tasks",
  "cognitive & emotional wellness": "Memory & mood",
  "emergency preparedness": "Emergency readiness",
  "home condition & maintenance": "Home upkeep",
  "technology readiness": "Phones & gadgets",
  "family & caregiver support": "Family support",
  "financial & government benefits": "Money & benefits",
  "lifestyle & social engagement": "Social life",
  // Section names used by the fixes (solution library) map to the same plain areas.
  mobility: "Moving around",
  "home maintenance": "Home upkeep",
  "property management": "Home upkeep",
  "smart home & technology": "Phones & gadgets",
  "family support": "Family support",
  "activities of daily living": "Daily self-care",
  "instrumental adls": "Household tasks",
  "cognitive support": "Memory & mood",
  "emotional & social wellbeing": "Memory & mood",
  "healthcare coordination": "Health",
  "wellness & lifestyle": "Social life",
};
function areaName(title: string | null | undefined): string {
  const t = (title || "").replace(/^\d+\.\s*/, "").trim();
  return FRIENDLY_AREA[t.toLowerCase()] ?? t;
}

/** Hide internal care-team shorthand from family readers. */
function plain(text: string): string {
  const t = text
    .replace(/Eldercare\/Care Manager \(ECM\)/g, "care manager")
    .replace(/\b(\w+)\/ECM\b/g, "$1 or care manager")
    .replace(/\bECM\b/g, "care manager")
    .replace(/≤?\s*\d+\s*°F\s*\/\s*/g, "≤ "); // Indian readers: Celsius only
  return t.charAt(0).toUpperCase() + t.slice(1);
}

/** Recommended products shown in the report (pictures, no prices — the family gets a quote separately). */
const MAX_PRODUCTS = 12;

/** Score bands for the one-line score key, from the same table the score uses. */
const LEGEND = LWA_INDEPENDENCE_BANDS.map((b, i, all) => ({
  status: b.status,
  grade: b.grade,
  range: i === 0 ? `${b.min}–100` : b.min === 0 ? `0–${all[i - 1].min - 1}` : `${b.min}–${all[i - 1].min - 1}`,
  // How many points the band covers (its share of the scale bar).
  width: (i === 0 ? 101 : all[i - 1].min) - b.min,
}));

/**
 * The score scale as a bar: five coloured bands from Critical (left) to Excellent
 * (right), each as wide as its range, labels underneath, and a marker at the score.
 */
function ScoreScale({ score }: { score: number }) {
  const bands = [...LEGEND].reverse(); // low → high
  // Equal-width bands (every label fits); the marker sits proportionally inside its band.
  const lo = (b: (typeof bands)[number]) => 100 - b.width - bands.slice(bands.indexOf(b) + 1).reduce((n, x) => n + x.width, 0) + 1;
  const at = Math.max(0, Math.min(100, score));
  const idx = Math.max(0, bands.findIndex((b) => at >= lo(b) && at < lo(b) + b.width));
  const pct = ((idx + (at - lo(bands[idx])) / bands[idx].width) / bands.length) * 100;
  return (
    <figure className="rp-scale" aria-label={`Score ${score} on a 0 to 100 scale`}>
      <figcaption>Score scale · 0–100, higher is safer</figcaption>
      <div className="rp-scale-track">
        {bands.map((b) => (
          <span key={b.status} className={`rp-scale-seg is-${b.status}`} />
        ))}
        <span className="rp-scale-marker" style={{ left: `${pct}%` }}>
          <b>{score}</b>
        </span>
      </div>
      <div className="rp-scale-labels">
        {bands.map((b) => (
          <span key={b.status}>
            <strong>{b.grade.replace(/\s+Risk$/i, "")}</strong>
            <small>{b.range}</small>
          </span>
        ))}
      </div>
    </figure>
  );
}

/** "field-job-45" → "KA-A-0045"; other ids unchanged. */
function reportId(id: string): string {
  const m = /^field-job-(\d+)$/.exec(id);
  return m ? `KA-A-${m[1].padStart(4, "0")}` : id;
}

const NUM_WORD = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"];
const numWord = (n: number) => NUM_WORD[n] ?? String(n);
function listJoin(items: string[]): string {
  if (items.length < 2) return items[0] ?? "";
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}
/** Band status → the one status colour family used on the page. */
function bandTone(status: string): "good" | "fair" | "poor" {
  return status === "excellent" || status === "good" ? "good" : status === "moderate" ? "fair" : "poor";
}

function ScoreRing({ score, status }: { score: number; status: string }) {
  const r = 46;
  const c = 2 * Math.PI * r;
  return (
    <svg className={`rp-ring rp-ring-${bandTone(status)}`} viewBox="0 0 108 108" role="img" aria-label={`Score ${score} out of 100`}>
      <circle cx="54" cy="54" r={r} className="rp-ring-track" />
      <circle
        cx="54"
        cy="54"
        r={r}
        className="rp-ring-fill"
        strokeDasharray={`${(c * Math.max(0, Math.min(100, score))) / 100} ${c}`}
        transform="rotate(-90 54 54)"
      />
      <text x="54" y="58" textAnchor="middle" className="rp-ring-num">
        {score}
      </text>
      <text x="54" y="76" textAnchor="middle" className="rp-ring-of">
        / 100
      </text>
    </svg>
  );
}

function PhotoThumb({ photo }: { photo: HomeSafetyAssessment["photos"][number] }) {
  if (photo.documentId) return <SyncedPhotoThumb documentId={photo.documentId} caption={photo.caption} />;
  if (photo.localPreview) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={photo.localPreview} alt={photo.caption || "Assessment photo"} />;
  }
  return <div className="rp-photo-empty">{photo.caption || "Photo"}</div>;
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <tr>
      <th scope="row">{label}</th>
      <td>{value?.trim() || "—"}</td>
    </tr>
  );
}

function SectionTitle({ n, children }: { n: number | string; children: React.ReactNode }) {
  return (
    <h2 className="rp-h2">
      <span className="rp-num">{n}</span>
      {children}
    </h2>
  );
}

type PlanRow = {
  key: string;
  title: string;
  area: string;
  group: (typeof GROUPS)[number];
  actions: string[];
  gain: number;
  because?: string[];
};

/**
 * Read-only, printable home safety report. Everything is derived from the stored
 * assessment, the client record, the rubric and the solution library; nothing writes back.
 */
export function AssessmentReportView({
  assessment: initial,
  backHref,
  backLabel = "Assessments",
}: {
  assessment: HomeSafetyAssessment;
  backHref: string;
  backLabel?: string;
}) {
  const categories: AssessmentCategory[] = useSafetyRubric();
  const [assessment, setAssessment] = useState(initial);
  const [elder, setElder] = useState<ElderDetails | null>(null);
  // Full answers: show every question, or only the ones that need action (risk / attention).
  const [actionOnly, setActionOnly] = useState(false);
  const [showLater, setShowLater] = useState(false);
  const [solutions, setSolutions] = useState<SolutionLibrary>(
    () => getCachedSolutions() ?? DEFAULT_SOLUTION_LIBRARY,
  );
  const [catalog, setCatalog] = useState<SafetyCatalog | null>(null);

  useEffect(() => {
    let cancelled = false;
    void hydratePhotoPreviews(initial).then((hydrated) => {
      if (!cancelled) setAssessment(hydrated);
    });
    fetchAdminSolutions()
      .then((lib) => {
        if (!cancelled) setSolutions(lib);
      })
      .catch(() => undefined);
    // Product pictures for "Recommended products" (public catalog: works for families too).
    fetchShowcaseCatalog()
      .then((c) => {
        if (!cancelled) setCatalog(c);
      })
      .catch(() => undefined);
    // Step 1 of the assessment saves DOB, gender, family contact and address parts
    // on the client record, not in the assessment payload — read them from there.
    if (initial.elderId != null) {
      api<ElderDetails>(`/api/v1/elders/${initial.elderId}`)
        .then((e) => {
          if (!cancelled) setElder(e ?? null);
        })
        .catch(() => undefined);
    }
    return () => {
      cancelled = true;
    };
  }, [initial]);

  // "Full answers" is collapsed on screen but always printed (the PDF appendix).
  useEffect(() => {
    const open = () => {
      document.querySelectorAll<HTMLDetailsElement>(".rp-answers").forEach((d) => (d.open = true));
      setActionOnly(false); // the PDF appendix always lists every answer
    };
    window.addEventListener("beforeprint", open);
    return () => window.removeEventListener("beforeprint", open);
  }, []);

  const profile = assessment.residentProfile ?? EMPTY_RESIDENT_PROFILE;
  const summary = computeScoreSummary(assessment, categories);
  const { band } = summary;
  const final = isScoreFinal(assessment.status);
  const scoredCategories = categoriesForAssessment(categories, assessment);
  const domains = [...computeDomainScores(scoredCategories, assessment.ratings, profile)].sort(
    (a, b) => a.score - b.score,
  );
  const plan = buildImprovementPlan(assessment, categories, solutions, profile);
  const products = catalog ? buildProductRecommendations(plan, catalog).items.slice(0, MAX_PRODUCTS) : [];
  const entries = [...plan.entries].sort(
    (a, b) => PRIORITY_RANK[a.solution.priority] - PRIORITY_RANK[b.solution.priority],
  );
  const applicable = getApplicableCategories(scoredCategories, profile, assessment.ratings);
  const name = clientDisplayName(assessment) || "Client";

  const attrs = (elder?.custom_attributes ?? {}) as Record<string, unknown>;
  const str = (v: unknown) => (typeof v === "string" ? v.trim() : "");
  const age = ageFromDob(elder?.date_of_birth) || (summary.age != null ? String(summary.age) : "");
  const addressLine = [
    str(elder?.address) || assessment.clientAddress?.trim(),
    str(attrs.area),
    [str(attrs.city), str(attrs.pincode)].filter(Boolean).join(" "),
  ]
    .filter(Boolean)
    .join(", ");
  const cap = (v: string | null | undefined) => (v ? v.charAt(0).toUpperCase() + v.slice(1) : "");
  const relation = str(attrs.contact_relation);
  const family = [
    (str(elder?.emergency_contact_name) || assessment.familyContactName?.trim() || "") +
      (relation ? ` (${relation})` : ""),
    str(elder?.emergency_contact_phone) || assessment.familyContactPhone?.trim(),
    str(attrs.contact_email),
  ]
    .filter(Boolean)
    .join(" · ");
  // More people in the same home receiving care (assessment step 1, "+ Add beneficiary").
  const others = (Array.isArray(attrs.beneficiaries) ? attrs.beneficiaries : []) as {
    name?: string;
    relation?: string;
    date_of_birth?: string;
    gender?: string;
  }[];
  const assessedOn = formatDate(assessment.completedAt || assessment.updatedAt);
  const assessor = assessment.assessorName?.trim() || "";

  const brand = publicBrandName();
  const notes = [assessment.painPoints?.trim(), assessment.notes?.trim()].filter(Boolean) as string[];

  // Display band comes from the number alone (same table as the printed score key),
  // so a 69 always reads "Moderate Risk". Critical items still lead the action table.
  const shown = safetyGradeFromScore(band.score);
  const scoreTone = bandTone(shown.status);

  // Answer counts across every question asked (free-text questions excluded).
  const counts = { unsafe: 0, acceptable: 0, excellent: 0 };
  applicable.forEach((cat) =>
    cat.items.forEach((item) => {
      if (item.inputType === "text") return;
      const r = normalizeRating(assessment.ratings[item.id]);
      if (r === "unsafe" || r === "acceptable" || r === "excellent") counts[r] += 1;
    }),
  );

  const rows: PlanRow[] = entries.length
    ? entries.map((e: ImprovementPlanEntry) => ({
        key: e.solution.id,
        title: e.solution.name || e.solution.finding,
        area: areaName(e.solution.section || e.findings[0]?.categoryTitle),
        group: groupOf(e.solution.priority),
        actions: (e.solution.recommendedSolutions ?? []).slice(0, 3).map(plain),
        gain: Math.round(Number(e.solution.scoreImprovement) || 0),
        because: e.findings.map((f) => f.itemLabel),
      }))
    : band.criticalFindings.map((f) => ({
        key: f.id,
        title: f.label,
        area: areaName(f.category),
        group: GROUPS[0],
        actions: [],
        gain: 0,
      }));
  // On screen: the most important SHOW_FIRST actions (urgent first); the rest behind "Show N more". Print shows all.
  const laterCount = Math.max(0, rows.length - SHOW_FIRST);
  const urgentRows = rows.filter((r) => r.group.key === "urgent");
  const soonCount = rows.filter((r) => r.group.key === "soon").length;

  // Two or three plain sentences built from the data.
  const first = name.split(/\s+/)[0] || name;
  const urgentAreas = Array.from(new Set(urgentRows.map((r) => r.area.toLowerCase()).filter(Boolean))).slice(0, 3);
  const summaryText = [
    counts.unsafe + counts.acceptable === 0
      ? `${first}'s home is safe in every area we checked.`
      : shown.status === "excellent" || shown.status === "good"
        ? `${first}'s home is safe in most areas, with a few things to improve.`
        : shown.status === "moderate"
          ? `${first}'s home is safe in many areas, but several need attention.`
          : shown.status === "high"
            ? `${first}'s home has serious risks in several areas.`
            : `${first}'s home needs urgent attention in many areas.`,
    urgentRows.length
      ? `${numWord(urgentRows.length)} urgent fix${urgentRows.length === 1 ? " is" : "es are"} needed${urgentAreas.length ? `, in ${listJoin(urgentAreas)}` : ""}.`
      : soonCount
        ? `Nothing is urgent; ${numWord(soonCount).toLowerCase()} item${soonCount === 1 ? "" : "s"} should be fixed within 30 days.`
        : "Nothing needs urgent action.",
    entries.length && plan.projectedScore > plan.currentScore
      ? `Completing the recommended fixes could raise the score to about ${plan.projectedScore}.`
      : "",
  ]
    .filter(Boolean)
    .join(" ");

  const genderAge = [age ? `${age} yrs` : "", cap(elder?.gender)].filter(Boolean).join(" · ");
  const loc = (attrs.home_location ?? null) as { latitude?: number; longitude?: number; label?: string } | null;
  // Only a location detected on the map; a typed address is already in "Address".
  const mapped = typeof loc?.latitude === "number" && typeof loc?.longitude === "number";
  const homeLocation = mapped
    ? loc?.label?.trim() || `${loc!.latitude!.toFixed(5)}, ${loc!.longitude!.toFixed(5)}`
    : "";

  let sec = 0;
  const next = () => ++sec;

  return (
    <div className="rp-wrap">
      <nav className="rp-bar no-print" aria-label="Report actions">
        <button
          type="button"
          className="rp-back"
          onClick={() => {
            // Back to wherever the report was opened from; Assessments when opened directly.
            if (window.history.length > 1 && document.referrer.startsWith(window.location.origin)) window.history.back();
            else window.location.assign(backHref);
          }}
        >
          <span aria-hidden="true">←</span> Back
        </button>
        <div className="ks-head-actions rp-bar-actions">
          <button type="button" onClick={() => void printPage(document.title || "Assessment report")} aria-label="Print / Save PDF" title="Print / Save PDF">
            <span className="ks-ha-icon" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M6 9V3h12v6M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
                <rect x="6" y="14" width="12" height="7" />
              </svg>
            </span>
            <span className="ks-ha-label">Print / Save PDF</span>
          </button>
        </div>
      </nav>

      <article className="rp">
        <header className="rp-head">
          <PublicBrandMark variant="header" className="rp-mark" alt={brand} />
          <div className="rp-head-title">
            <h1>Home Safety Assessment Report</h1>
            <dl className="rp-meta">
              <div>
                <dt>Report ID</dt>
                <dd>{reportId(assessment.id)}</dd>
              </div>
              <div>
                <dt>Date assessed</dt>
                <dd>{assessedOn}</dd>
              </div>
              {assessor ? (
                <div>
                  <dt>Assessed by</dt>
                  <dd>{assessor}</dd>
                </div>
              ) : null}
              {assessment.status !== "completed" ? (
                <div>
                  <dt>Status</dt>
                  <dd>Draft</dd>
                </div>
              ) : null}
            </dl>
          </div>
          <p className="rp-legal">
            <strong>{LEGAL_ENTITY_NAME}</strong>
            CIN {COMPANY_CIN}
            <br />
            GSTIN {COMPANY_GSTIN}
          </p>
        </header>

        <section className="rp-sec rp-keep">
          <SectionTitle n={next()}>Summary</SectionTitle>
          <div className="rp-sum">
            <div className="rp-sum-main">
              <p className="rp-who">
                <strong>{name}</strong>
                {genderAge ? <span>{genderAge}</span> : null}
              </p>
              <p className="rp-sum-text">{summaryText}</p>
              <ul className="rp-counts">
                <li>
                  <b className="rp-c-poor">{counts.unsafe}</b> Risks
                </li>
                <li>
                  <b className="rp-c-fair">{counts.acceptable}</b> Need attention
                </li>
                <li>
                  <b className="rp-c-good">{counts.excellent}</b> Safe
                </li>
              </ul>
            </div>
            <div className="rp-score">
              {final ? (
                <div className="rp-score-row">
                  <ScoreRing score={band.score} status={shown.status} />
                  <div className="rp-score-text">
                    <p className="rp-score-cap">Safety score</p>
                    <p className={`rp-band rp-c-${scoreTone}`}>{shown.grade}</p>
                    <p className="rp-band-line">{shown.label}</p>
                  </div>
                </div>
              ) : (
                <p className="rp-band-line">{draftScoreText(summary.complete)}</p>
              )}
            </div>
          </div>
          {/* Full width under the summary: every band label has room on screen and on A4. */}
          {final ? <ScoreScale score={band.score} /> : null}
        </section>

        <section className="rp-sec rp-keep">
          <SectionTitle n={next()}>Household &amp; contacts</SectionTitle>
          <table className="rp-kv">
            <tbody>
              <Row label="Beneficiary" value={[name, genderAge].filter(Boolean).join(" · ")} />
              <Row label="Phone" value={str(elder?.phone) || assessment.clientPhone} />
              {str(attrs.email) ? <Row label="Email" value={str(attrs.email)} /> : null}
              {others.map((b, n) => (
                <Row
                  key={n}
                  label={`Beneficiary ${n + 2}`}
                  value={[
                    b.name,
                    cap(b.relation),
                    ageFromDob(b.date_of_birth) ? `${ageFromDob(b.date_of_birth)} yrs` : "",
                    cap(b.gender),
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                />
              ))}
              <Row label="Contact person" value={family} />
              <Row label="Address" value={addressLine} />
              {homeLocation ? <Row label="Home location" value={homeLocation} /> : null}
            </tbody>
          </table>
        </section>

        <section className="rp-sec">
          <div className="rp-sec-head">
            <SectionTitle n={next()}>Priority actions</SectionTitle>
            {entries.length && plan.projectedScore > plan.currentScore ? (
              <p className="rp-proj">
                Score after fixes: {plan.currentScore} → <b>{plan.projectedScore}</b>
              </p>
            ) : null}
          </div>
          {rows.length ? (
            <>
              <table className="rp-table rp-plan">
                <thead>
                  <tr>
                    <th className="rp-col-n">#</th>
                    <th>Issue</th>
                    <th>Area</th>
                    <th>When</th>
                    <th>What to do</th>
                    <th className="rp-col-r">Score gain</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, n) => (
                    <tr key={r.key} className={n >= SHOW_FIRST && !showLater ? "rp-screen-hide" : undefined}>
                      <td className="rp-col-n">{n + 1}</td>
                      <td className="rp-issue">
                        {r.title}
                        {r.because?.length ? <small className="rp-because">Because: {r.because.join("; ")}</small> : null}
                      </td>
                      <td data-label="Area">{r.area}</td>
                      <td data-label="When" className="rp-when">
                        <span className={`rp-dot rp-dot-${r.group.key}`} aria-hidden="true" />
                        {r.group.label}
                        <small>{r.group.when.toLowerCase()}</small>
                      </td>
                      <td data-label="What to do">
                        {r.actions.length ? (
                          <ul className="rp-do">
                            {r.actions.map((a) => (
                              <li key={a}>{a}</li>
                            ))}
                          </ul>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td data-label="Score gain" className={`rp-col-r rp-gain${r.gain > 0 ? "" : " rp-blank"}`}>
                        {r.gain > 0 ? `+${r.gain}` : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {laterCount && !showLater ? (
                <button type="button" className="rp-more no-print" onClick={() => setShowLater(true)}>
                  Show {laterCount} more
                </button>
              ) : null}
            </>
          ) : (
            <p className="rp-empty">Nothing to fix right now — the home looks safe.</p>
          )}
        </section>

        {products.length ? (
          <section className="rp-sec">
            <SectionTitle n={next()}>Recommended products</SectionTitle>
            <ul className="rp-products">
              {products.map(({ product, solutionFindings }) => {
                const src = catalogProductImageSrc(product);
                return (
                  <li key={product.id} className="rp-product rp-keep">
                    {src ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={src} alt={product.name} loading="eager" />
                    ) : (
                      <div className="rp-product-noimg" aria-hidden="true">
                        {product.name.slice(0, 1)}
                      </div>
                    )}
                    <div>
                      <strong>{product.name}</strong>
                      {product.short_description ? <p>{product.short_description}</p> : null}
                      {solutionFindings[0] ? <small>For: {plain(solutionFindings[0])}</small> : null}
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        ) : null}

        {domains.length ? (
          <section className="rp-sec rp-keep">
            <SectionTitle n={next()}>Area scores</SectionTitle>
            <ul className="rp-areas">
              {domains.map((d) => (
                <li key={d.id}>
                  <span className="rp-area-name">{areaName(d.title)}</span>
                  <span className="rp-track">
                    <span className={`rp-fill rp-scale-seg is-${bandStatus(d.score)}`} style={{ width: `${Math.max(2, d.score)}%` }} />
                  </span>
                  <span className="rp-area-num">{d.score}</span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {notes.length ? (
          <section className="rp-sec rp-keep">
            <SectionTitle n={next()}>Assessor notes</SectionTitle>
            <div className="rp-notes">
              {notes.map((n, i) => (
                <p key={i}>{n}</p>
              ))}
            </div>
          </section>
        ) : null}

        {assessment.photos?.length ? (
          <section className="rp-sec">
            <SectionTitle n={next()}>Site photos</SectionTitle>
            <div className="rp-photos">
              {assessment.photos.map((photo) => (
                <figure key={photo.id} className="rp-photo rp-keep">
                  <PhotoThumb photo={photo} />
                  <figcaption>{[photo.roomType, photo.caption].filter(Boolean).join(" · ") || "Photo"}</figcaption>
                </figure>
              ))}
            </div>
          </section>
        ) : null}

        <details className="rp-answers">
          <summary>
            <h2 className="rp-h2">
              <span className="rp-num">A</span>
              Appendix — Full answers
            </h2>
            <span className="rp-answers-hint no-print">Show full answers</span>
          </summary>
          <div className="rp-ans-bar no-print">
            <span className="rp-ans-key">
              {(["unsafe", "acceptable", "excellent", "na"] as const).map((r) => (
                <span key={r} className="rp-status">
                  <span className={`rp-dot rp-dot-${r}`} aria-hidden="true" />
                  {STATUS_LABEL[r]}
                </span>
              ))}
            </span>
            <label className="rp-ans-toggle">
              <input type="checkbox" checked={actionOnly} onChange={(e) => setActionOnly(e.target.checked)} />
              Only items needing action
            </label>
          </div>
          {applicable.map((cat) => {
            const rated = cat.items.map((item) => ({ item, rating: normalizeRating(assessment.ratings[item.id]) }));
            const risks = rated.filter((r) => r.rating === "unsafe").length;
            const watch = rated.filter((r) => r.rating === "acceptable").length;
            const list = actionOnly ? rated.filter((r) => r.rating === "unsafe" || r.rating === "acceptable") : rated;
            if (actionOnly && !list.length) return null;
            const score = domains.find((d) => d.id === cat.id)?.score;
            return (
              <section key={cat.id} className="rp-ans-cat">
                <h3>
                  {areaName(cat.title)}
                  <small>
                    {score != null ? `${score}/100 · ` : ""}
                    {risks || watch
                      ? [risks ? `${risks} risk${risks === 1 ? "" : "s"}` : "", watch ? `${watch} need attention` : ""]
                          .filter(Boolean)
                          .join(" · ")
                      : "All safe"}
                  </small>
                </h3>
                <table className="rp-ans">
                  <tbody>
                    {list.map(({ item, rating }) => {
                      const words = caregiverAnswers(item.id);
                      const note = assessment.itemNotes?.[item.id]?.trim() || "";
                      const text = item.inputType === "text";
                      const answer = text
                        ? note || "—"
                        : assessment.answerLabels?.[item.id]?.trim() ||
                          (hasCustomOptions(item) ? answerLabel(item, rating) : undefined) ||
                          (words && rating ? (words as Record<string, string>)[rating] : undefined) ||
                          ratingLabel(rating);
                      return (
                        <tr key={item.id} className={`is-${text ? "text" : rating || "none"}`}>
                          <td className="rp-ans-q">{item.ask?.trim() || words?.ask || item.label}</td>
                          <td className="rp-ans-a">
                            <span className="rp-ans-text">{answer}</span>
                            {!text ? (
                              <span className="rp-status">
                                <span className={`rp-dot rp-dot-${rating || "none"}`} aria-hidden="true" />
                                {rating ? STATUS_LABEL[rating] : "Not answered"}
                              </span>
                            ) : null}
                            {note && !text ? <span className="rp-ans-note">Note: {note}</span> : null}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </section>
            );
          })}
        </details>

        <footer className="rp-foot">
          <p>Guidance from a home visit — not a medical diagnosis.</p>
          <p>
            © {new Date().getFullYear()} {LEGAL_ENTITY_NAME} · CIN {COMPANY_CIN} · GSTIN {COMPANY_GSTIN}
          </p>
        </footer>
      </article>
    </div>
  );
}
