"use client";


import { FamilyLink as Link } from "@/components/livewell/family/FamilyLink";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { FamilyShell } from "@/components/livewell/family/FamilyShell";
import { FamilyError } from "@/components/livewell/family/FamilyError";
import { FamilyAskButtons } from "@/components/livewell/family/FamilyAsk";
import { familyClock, familyDate } from "@/lib/livewell/familyTime";
import { plainWords, withoutContextLines } from "@/lib/livewell/familyWords";
import { useFamilyTimezone } from "@/lib/family-zone";
import { NpsPrompt } from "@/components/livewell/family/FamilyKushLifeExtras";
import { VoicePlayer } from "@/components/kushlife/VoicePlayer";
import { canAskRating, isCompletedCareVisit } from "@/lib/livewell/familyVisit";

const VISIT_STATUS: Record<string, string> = {
  completed: "Done",
  scheduled: "Booked",
  planned: "Booked",
  in_progress: "Happening now",
  cancelled: "Cancelled",
  missed: "Missed",
};
import {
  familyApi,
  fetchFamilyVisit,
  submitFamilyVisitExperienceRating,
  type FamilyStatus,
  type FamilyVisit,
} from "@/lib/livewell/familyApi";
import { isStatusVisit, withNotedChanges } from "@/lib/livewell/familyStatus";
import { FamilyVisitPhotos } from "@/components/livewell/family/FamilyVisitPhotos";

export default function FamilyVisitDetailPage() {
  const params = useParams();
  const visitId = String(params.id ?? "");
  const [visit, setVisit] = useState<FamilyVisit | null>(null);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [rateMessage, setRateMessage] = useState("");
  const tz = useFamilyTimezone();

  function load() {
    if (!visitId) return;
    setLoadError("");
    fetchFamilyVisit(visitId)
      .then(setVisit)
      .catch((e) => setLoadError(e instanceof Error ? e.message : "Failed to load"));
  }

  // The same status as Home (GET /family/status): what the carer noted on the latest visit.
  const [status, setStatus] = useState<FamilyStatus | null>(null);

  useEffect(() => {
    load();
    familyApi<FamilyStatus>("/status").then(setStatus).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visitId]);

  async function submitRating(e: React.FormEvent) {
    e.preventDefault();
    if (!visitId || rating < 1) return;
    setSubmitting(true);
    setError("");
    setRateMessage("");
    try {
      const updated = await submitFamilyVisitExperienceRating(visitId, {
        rating,
        comment,
      });
      // The rating reply has no photo list; keep the one already shown.
      setVisit((prev) => ({ ...updated, photos: updated.photos?.length ? updated.photos : prev?.photos }));
      setRateMessage("Thank you. Your care manager reads every rating.");
      setComment("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save rating");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <FamilyShell
      title={visit ? `${visit.visit_type} · ${familyDate(visit.visited_at, { tz })}` : "Visit report"}
      docTitle="Visit report"
      back={{ href: "/kushalaya/family/updates", label: "← All updates" }}
    >
      {/not found|404|invalid/i.test(loadError) ? (
        <div className="card home-safety-empty">
          <p>
            <strong>This visit report isn&rsquo;t available.</strong>
          </p>
          <p className="muted">It may have been removed, or the link is wrong.</p>
          <Link href="/kushalaya/family/updates" className="home-safety-family-inline-link">
            See all updates →
          </Link>
        </div>
      ) : (
        <FamilyError message={loadError} onRetry={load} what="this visit report" />
      )}
      {error && <p className="error-text">{error}</p>}
      {!visit && !error && !loadError ? <p>Loading…</p> : null}
      {visit && (
        <article className="card home-safety-family-visit-report">
          <header className="fh-visit-head">
            <p className="muted">
              <span className="home-safety-pill home-safety-pill-neutral">
                {VISIT_STATUS[String(visit.status || "").toLowerCase()] ?? "Visit"}
              </span>{" "}
              {/* The API leaves out a finish within a minute of check-in, and the
                  duration is the real time between them (never the planned length). */}
              {visit.checked_in_at
                ? `Checked in ${familyClock(visit.checked_in_at, tz)}${
                    visit.checked_out_at ? ` · finished ${familyClock(visit.checked_out_at, tz)}` : ""
                  }${visit.checked_out_at && visit.duration_minutes ? ` · ${visit.duration_minutes} min` : ""}`
                : familyClock(visit.visited_at, tz)}
            </p>
          </header>
          {visit.staff_name || visit.partner_name ? (
            <p className="fh-visit-who">
              <span className="fh-elder-avatar" aria-hidden="true">
                {(visit.staff_name || visit.partner_name || "?").trim().charAt(0).toUpperCase()}
              </span>
              <span>
                <small className="muted">Visited by</small>{" "}
                <strong>{[visit.staff_name, visit.partner_name].filter(Boolean).join(" · ")}</strong>
              </span>
            </p>
          ) : null}

          {/* An assessment's check-in ("Overall normal") would contradict its safety score, so it is not shown. */}
          {visit.checkin && typeof visit.checkin === "object" && !/assessment/i.test(visit.visit_type) ? (
            <p className="muted" style={{ fontSize: "0.9rem" }}>
              Check-in: {plainWords(String(visit.checkin.overall || "").replace(/_/g, " "))}
              {visit.checkin.mobility
                ? ` · walking ${String(visit.checkin.mobility).replace(/_/g, " ")}`
                : ""}
              {visit.checkin.medication && visit.checkin.medication !== "none"
                ? ` · meds ${String(visit.checkin.medication)}`
                : ""}
            </p>
          ) : null}

          {withoutContextLines(visit.summary) ? (
            <section className="home-safety-visit-section">
              <h3>Visit summary</h3>
              <p>
                {plainWords(
                  isStatusVisit(visit.visited_at, status?.last_visit_at)
                    ? withNotedChanges(withoutContextLines(visit.summary), status?.changes)
                    : withoutContextLines(visit.summary),
                )}
              </p>
            </section>
          ) : null}

          {visit.family_message ? (
            <section className="home-safety-visit-section home-safety-family-msg-section">
              <h3>Message from Care Manager</h3>
              <p>{visit.family_message}</p>
            </section>
          ) : null}

          {withoutContextLines(visit.wellness_notes) && visit.wellness_notes !== visit.family_message ? (
            <section className="home-safety-visit-section">
              <h3>Wellness notes</h3>
              <p>{plainWords(withoutContextLines(visit.wellness_notes))}</p>
            </section>
          ) : null}

          {visit.concerns.length > 0 ? (
            <section className="home-safety-visit-section">
              <h3>Concerns identified</h3>
              <ul className="home-safety-family-highlights">
                {visit.concerns.map((c) => (
                  <li key={c}>{plainWords(c)}</li>
                ))}
              </ul>
            </section>
          ) : null}

          {withoutContextLines(visit.recommendations) ? (
            <section className="home-safety-visit-section">
              <h3>Recommendations</h3>
              <p>{plainWords(withoutContextLines(visit.recommendations))}</p>
            </section>
          ) : null}

          <FamilyVisitPhotos photos={visit.photos ?? []} visitedAt={visit.visited_at} />
          {!visit.photos?.length && String(visit.status).toLowerCase() === "completed" ? (
            <section className="home-safety-visit-section">
              <h3>Photos</h3>
              <p className="muted">No photos this visit.</p>
            </section>
          ) : null}

          {visit.voice_notes?.length ? (
            <section className="home-safety-visit-section">
              <h3>Voice notes from the visit</h3>
              {visit.voice_notes.map((n) => (
                <p key={n.id}><VoicePlayer note={n} /></p>
              ))}
            </section>
          ) : null}

          {visit.experience_rating != null ? (
            <section className="home-safety-visit-section">
              <h3>Your rating</h3>
              <p>
                ★ {visit.experience_rating} / 5
                {visit.rated_at
                  ? ` · ${familyDate(visit.rated_at, { tz })}`
                  : ""}
              </p>
              {visit.experience_comment ? <p className="muted">{visit.experience_comment}</p> : null}
              {rateMessage && !visit.can_rate ? <p className="muted" role="status">{rateMessage}</p> : null}
            </section>
          ) : null}

          {visit.can_rate && canAskRating(visit) ? (
            <section className="home-safety-visit-section">
              <h3>How was this visit?</h3>
              {rateMessage ? <p className="muted" role="status">{rateMessage}</p> : null}
              <form onSubmit={submitRating} className="home-safety-visit-rate-form">
                <div className="fh-stars" role="radiogroup" aria-label="Your rating, 1 to 5 stars">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button
                      key={n}
                      type="button"
                      role="radio"
                      aria-checked={rating === n}
                      aria-label={`${n} star${n === 1 ? "" : "s"}${n === 1 ? " — poor" : n === 5 ? " — excellent" : ""}`}
                      className={rating >= n ? "is-on" : ""}
                      onClick={() => setRating(n)}
                    >
                      ★
                    </button>
                  ))}
                </div>
                <p className="fh-stars-ends muted"><span>Poor</span><span>Excellent</span></p>
                <label className="home-safety-field">
                  Comment (optional)
                  <textarea
                    rows={3}
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="What went well? Anything we should improve?"
                  />
                </label>
                <button type="submit" disabled={submitting || rating < 1}>
                  {submitting ? "Sending…" : "Send rating"}
                </button>
              </form>
            </section>
          ) : null}
          <section className="card home-safety-section fh-visit-ask">
            <h3>Questions about this visit?</h3>
            <FamilyAskButtons
              compact
              visit={{
                ref: String(visit.id),
                label: `${visit.visit_type}, ${familyDate(visit.visited_at, { tz })}`,
              }}
            />
          </section>
          {/* Asked only after a completed care visit, never on an assessment or the
              baseline report (the API asks at most once every 90 days). */}
          {isCompletedCareVisit(visit) ? <NpsPrompt /> : null}
        </article>
      )}
    </FamilyShell>
  );
}
