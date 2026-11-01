"use client";

import { FamilyLink as Link } from "@/components/livewell/family/FamilyLink";
import { useEffect, useState } from "react";
import { FamilyShell, initialsOf } from "@/components/livewell/family/FamilyShell";
import { FamilyDevicesCard } from "@/components/livewell/family/FamilyDevicesCard";
import { FamilyError } from "@/components/livewell/family/FamilyError";
import { CareTeamButtons, EmergencyNumbers } from "@/components/livewell/family/CareTeamContact";
import { familyDate, familyTime } from "@/lib/livewell/familyTime";
import { familyStatusLine, isStatusVisit, withNotedChanges } from "@/lib/livewell/familyStatus";
import { useFamilyTimezone } from "@/lib/family-zone";
import { FamilyVisitPhotos } from "@/components/livewell/family/FamilyVisitPhotos";
import { SafetyScoreCard } from "@/components/livewell/family/SafetyScoreCard";
import { KushLifeTrend } from "@/components/KushLifeTrend";
import { KushLifeLifeline } from "@/components/kushlife/KushLifeLifeline";
import { FamilyAskButtons, FamilyQuestionsCard } from "@/components/livewell/family/FamilyAsk";
import { KushLifeWeekCard } from "@/components/livewell/family/KushLifeWeekCard";
import { FamilyKushLifeExtras } from "@/components/livewell/family/FamilyKushLifeExtras";
import { JourneySteps, type Journey } from "@/components/JourneySteps";
import { FamilyScoreWhyButton } from "@/components/livewell/family/FamilyScoreWhy";
import { FamilyLiveVisit } from "@/components/livewell/family/FamilyLiveVisit";
import type { KushLifeView } from "@/lib/kushlife";
import {
  familyApi,
  fetchFamilyDashboard,
  fetchFamilyImprovementPlan,
  type FamilyDashboard,
  type FamilyStatus,
} from "@/lib/livewell/familyApi";
import { projectedScore } from "@/lib/livewell/familyPlan";
import { publicSafetyScoreName } from "@/lib/public-brand";

function greeting(now = new Date()): string {
  const h = now.getHours();
  if (h < 5) return "Good night";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function shortDate(value: string): string {
  return familyDate(value);
}

export default function FamilyDashboardPage() {
  const [data, setData] = useState<FamilyDashboard | null>(null);
  const [error, setError] = useState("");
  const [kl, setKl] = useState<KushLifeView | null>(null);
  const [journey, setJourney] = useState<Journey | null>(null);
  // One status from the server (also used by the digest and details).
  const [serverStatus, setServerStatus] = useState<FamilyStatus | null>(null);
  const tz = useFamilyTimezone();

  function load() {
    setError("");
    fetchFamilyDashboard()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }

  useEffect(() => {
    load();
    // KushLife and the journey load on their own so the page never waits on them.
    familyApi<KushLifeView>("/kushlife").then(setKl).catch(() => undefined);
    familyApi<FamilyStatus>("/status").then(setServerStatus).catch(() => undefined);
    // The journey's target is the same projected score as /safety and /plan
    // ("43 → about 93"), worked out from the open plan items, never a flat 100.
    Promise.all([familyApi<Journey>("/journey"), fetchFamilyImprovementPlan().catch(() => null)])
      .then(([j, plan]) =>
        setJourney({
          ...j,
          target_score: plan ? projectedScore(plan.current_score ?? j.score, plan.items) : null,
        }),
      )
      .catch(() => undefined);
  }, []);

  if (!data) {
    return (
      <FamilyShell title="Family home" docTitle="Dashboard" subtitle="Loading…">
        {error ? (
          <FamilyError message={error} onRetry={load} what="your home page" />
        ) : (
          <p className="muted">Loading…</p>
        )}
      </FamilyShell>
    );
  }

  const published = data.has_published_score ?? data.safety.has_published_score;
  const level = data.care_status?.level ?? "unknown";
  // Greet the signed-in family member, never the senior (portal_me can be the elder).
  const isSelf = !!data.viewer_is_elder;
  const viewerFirst =
    data.viewer_first_name?.trim() ||
    (isSelf ? data.senior_name.trim().split(" ")[0] : "") ||
    (data.parent_name.trim().toLowerCase() !== data.senior_name.trim().toLowerCase() ? data.parent_name.trim().split(" ")[0] : "");
  const needs = data.needs_you ?? [];
  const lastAssess = data.last_visit ?? null;
  const lastKl = kl?.visits[0];
  // "Last visit" is the most recent of the assessment-style visit and the KushLife care visit.
  const klNewer =
    !!lastKl?.date &&
    (!lastAssess?.visited_at || new Date(lastKl.date).getTime() > new Date(lastAssess.visited_at).getTime());
  const last = klNewer && lastKl
    ? {
        id: `job-${lastKl.job_id}`,
        visited_at: lastKl.date as string,
        staff_name: null as string | null,
        summary: lastKl.note || lastKl.title,
        photo: null,
      }
    : lastAssess
      ? {
          id: lastAssess.id,
          visited_at: lastAssess.visited_at,
          staff_name: lastAssess.staff_name ?? null,
          summary: lastAssess.summary,
          photo: lastAssess.photo ?? null,
        }
      : null;
  // Ignore a "next visit" that is already in the past.
  const nextAt =
    data.next_visit_at && new Date(data.next_visit_at).getTime() > Date.now() ? data.next_visit_at : null;
  const elderFirst = data.senior_name.split(" ")[0] || "Your parent";
  // "Lakshmi is well · last visit Wed 7 Oct by Anita · 4/4 checks OK"
  const status = familyStatusLine({
    elderFirst,
    isSelf,
    klStatus: serverStatus?.word ?? kl?.status,
    level,
    lastVisitAt: last?.visited_at ?? null,
    staffName: last?.staff_name ?? null,
    checks: lastKl && last?.id === `job-${lastKl.job_id}` ? lastKl.checks : null,
    changes: lastKl && last?.id === `job-${lastKl.job_id}` ? serverStatus?.changes : null,
    tz,
  });

  return (
    <FamilyShell
      title="Family home"
      docTitle="Dashboard"
      hero={(ctx) => (
        <section className="fh-hero" aria-label="Today at a glance">
          <div className="fh-hero-main">
            <p className="fh-hero-kicker">{greeting()}</p>
            <h1>{viewerFirst ? `Hello, ${viewerFirst}` : "Hello"}</h1>
            <p className="fh-hero-sub">
              {isSelf ? (
                "Here is how you are doing today."
              ) : (
                <>
                  Here is how <strong>{ctx.seniorName || data.senior_name}</strong> is doing today.
                </>
              )}
            </p>
          </div>
          <div className="fh-hero-side">
            {/* "Caring for Lakshmi" means nothing to Lakshmi herself. */}
            {isSelf ? null : (
              <div className="fh-hero-elder">
                <span className="fh-elder-avatar" aria-hidden="true">
                  {initialsOf(ctx.seniorName || data.senior_name)}
                </span>
                <span className="fh-side-elder-text">
                  <small>Caring for</small>
                  <strong>{ctx.seniorName || data.senior_name}</strong>
                </span>
              </div>
            )}
            {ctx.switcher}
          </div>
        </section>
      )}
    >
      <div className="fh-home-body">
      <div className={`fh-status-line is-${status.tone}${status.tone === "alert" ? " is-warn" : ""}`} role="status">
        <p>{status.text}</p>
        {last?.photo ? (
          <FamilyVisitPhotos photos={[last.photo]} visitedAt={last.visited_at} compact />
        ) : null}
      </div>

      {needs.length > 0 ? (
        <section className="fh-needs" aria-labelledby="fh-needs-h">
          <h2 id="fh-needs-h">Needs you</h2>
          <ul>
            {needs.map((n, i) => (
              <li key={`${n.kind}-${i}`} className={n.kind === "sos" ? "is-sos" : undefined}>
                <Link href={n.href}>
                  {n.title}
                  <span>{n.action} →</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <FamilyLiveVisit />

      <div className="fh-home-pair">
      <section className="fh-home-card" aria-labelledby="fh-next-h">
        <h2 id="fh-next-h">Next visit</h2>
        {nextAt ? (
          <>
            <strong>{familyTime(nextAt, tz)}</strong>
            {data.next_visit_label ? <p className="muted">{data.next_visit_label}</p> : null}
          </>
        ) : (
          <>
            <strong>None booked</strong>
            <Link href="/kushalaya/family/services#book" className="fh-home-link">
              Request a visit →
            </Link>
          </>
        )}
      </section>

      {last ? (
        <section className="fh-home-card" aria-labelledby="fh-last-h">
          <h2 id="fh-last-h">Last visit</h2>
          <strong>
            {familyDate(last.visited_at, { tz })}
            {last.staff_name ? ` · ${last.staff_name}` : ""}
          </strong>
          {last.summary ? (
            <p>
              {/* Same status as the line above: never all ticks when the carer noted something. */}
              {isStatusVisit(last.visited_at, serverStatus?.last_visit_at)
                ? withNotedChanges(last.summary, serverStatus?.changes)
                : last.summary}
            </p>
          ) : null}
          <Link href={`/kushalaya/family/visits/${last.id}`} className="fh-home-link">
            Read report →
          </Link>
        </section>
      ) : null}
      </div>

      <CareTeamButtons contact={data.care_team_contact} messageHref="/kushalaya/family/messages" />
      <EmergencyNumbers contact={data.care_team_contact} />
      <FamilyQuestionsCard />

      <KushLifeWeekCard changesNoted={serverStatus?.changes} isSelf={isSelf} />
      <FamilyKushLifeExtras nps={false} />

      <section id="kushlife" className="card home-safety-section fh-anchor fh-kl-compact">
        {kl ? <KushLifeLifeline view={kl} /> : null}
        {kl ? (
          <details>
            <summary>
              <span>
                <strong>KushLife: {kl.visits.length ? kl.status : "Not started"}</strong>
                {kl.summary_line ? <span className="muted"> · {kl.summary_line}</span> : null}
              </span>
              <span className="fh-kl-more">See the four checks</span>
            </summary>
            <KushLifeTrend view={kl} lifeline={false} />
            {kl.visits[0] ? (
              <FamilyAskButtons
                compact
                visit={{
                  ref: String(kl.visits[0].job_id),
                  label: [kl.visits[0].title, kl.visits[0].date ? shortDate(kl.visits[0].date) : ""]
                    .filter(Boolean)
                    .join(", "),
                }}
                flagKey={kl.flags.find((f) => f.job_id === kl.visits[0].job_id)?.key}
              />
            ) : null}
          </details>
        ) : (
          <p className="muted">Loading KushLife…</p>
        )}
      </section>

      {journey ? (
        <section className="card home-safety-section">
          <JourneySteps journey={journey} family />
        </section>
      ) : null}

      <FamilyDevicesCard />

      <Link href="/kushalaya/family/safety" className="ks-score-link">
        <p className="home-safety-family-score-kicker">{publicSafetyScoreName()}</p>
        <SafetyScoreCard score={data.safety} compact />
      </Link>
      {published ? (
        <div className="fh-why">
          <FamilyScoreWhyButton />
        </div>
      ) : null}
      {/* The NPS question is asked on a visit report, after a visit (not on Home). */}
      </div>
    </FamilyShell>
  );
}
