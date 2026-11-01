"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getStoredAuth } from "@/lib/api";
import { isCaregiverRole } from "@/lib/auth";
import {
  fieldSuggestions,
  loadFieldAssessment,
  saveFieldAssessment,
  uploadFieldPhoto,
  type FieldAssessment,
  type AssessmentClient,
  type FieldSuggestion,
  isFieldStaff,
} from "@/lib/jobs";
import { portalFont } from "@/components/portal-font";
import { requireLocation, type LocationPayload } from "@/lib/visit-location";
import { LocationNeeded } from "../../LocationNeeded";
import { ClientStep } from "./ClientStep";
import "../../caregiver.css";
import "./assess.css";
import { publicSafetyScoreName } from "@/lib/public-brand";
import { caregiverAnswers } from "@/lib/livewell/caregiver-answers";
import { questionAsk, questionOptions, splitHelp, type QuestionOption } from "@/lib/livewell/question-options";
import {
  isAnswered as answeredIn,
  unansweredBySection,
  unansweredQuestions,
  unansweredTitle,
  type Unanswered,
} from "@/lib/livewell/assessment-blockers";

type Rating = "excellent" | "acceptable" | "unsafe" | "na";

const RATING_BUTTONS: { value: Rating; label: string; tone: string }[] = [
  { value: "excellent", label: "Safe", tone: "is-safe" },
  { value: "acceptable", label: "Needs attention", tone: "is-watch" },
  { value: "unsafe", label: "Risk", tone: "is-risk" },
  { value: "na", label: "Not applicable", tone: "is-na" },
];

const MOBILITY = [
  { value: "none", label: "None" },
  { value: "cane", label: "Walking stick" },
  { value: "walker", label: "Walker" },
  { value: "wheelchair", label: "Wheelchair" },
];

type Question = {
  cat: string;
  id: string;
  label: string;
  group: string;
  input: string;
  hint: string;
  ask?: string;
  options?: QuestionOption[];
};
type Step =
  | { kind: "client" }
  | { kind: "profile" }
  | { kind: "section"; cat: string; items: Question[] }
  | { kind: "review" };

/**
 * Field assessment: one screen per section with every question listed and
 * answers that describe what the caregiver sees, auto-saved drafts,
 * a review screen, then submit → score + report to the family.
 */
/** Rubric titles carry numbers only on some sections ("1. Entrance"); show them all without. */
function sectionTitle(title: string): string {
  return title.replace(/^\s*\d+\s*[.):\-–]?\s+/, "").trim() || title;
}

export default function FieldAssessmentPage() {
  const staff = isFieldStaff();
  // Opened from Ops → Assessments ("New assessment") goes back there.
  // Opened from the Operations board ("Start assessment" on a lead) goes back there.
  const [from, setFrom] = useState("");
  useEffect(
    () =>
      setFrom(new URLSearchParams(window.location.search).get("from") || ""),
    [],
  );
  const backHref = staff
    ? from === "assessments"
      ? "/kushalaya/assessments"
      : from === "leads"
        ? "/kushalaya/enquiries"
        : "/kushalaya/visits"
    : "/caregiver";
  const backLabel = staff
    ? from === "assessments"
      ? "Back to Assessments"
      : from === "leads"
        ? "Back to Operations"
        : "Back to Schedule"
    : "Back to my day";
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const jobId = Number(params.id);
  const draftKey = `kaa-field-${jobId}`;

  const [form, setForm] = useState<FieldAssessment | null>(null);
  const [client, setClient] = useState<AssessmentClient | null>(null);
  const [ratings, setRatings] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  // Which option was tapped (several options may save the same rating); shown in the report.
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [profile, setProfile] = useState<{
    hasStairs?: boolean;
    mobilityDevice?: string;
  }>({});
  const [index, setIndex] = useState(0);
  const [showSkipped, setShowSkipped] = useState(false);
  const [noteOpen, setNoteOpen] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState<"idle" | "saving" | "saved" | "error">(
    "idle",
  );
  const [saveError, setSaveError] = useState("");
  const [done, setDone] = useState<{ score: number | null } | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  // After a blocked submit: unanswered questions are marked and listed.
  const [showMissing, setShowMissing] = useState(false);
  const [resumeAt, setResumeAt] = useState<"" | "start" | "gap">("");
  // Next tapped with gaps on this step: its missing answers turn red and the step stays.
  const [flagStep, setFlagStep] = useState<number | null>(null);
  const [focus, setFocus] = useState<{ id: string; tick: number } | null>(null);
  const blocker = useRef<HTMLDivElement>(null);
  const [locNeed, setLocNeed] = useState(false);
  const [locating, setLocating] = useState(false);
  const [photos, setPhotos] = useState(0);
  const [photoBusy, setPhotoBusy] = useState(false);
  const [suggested, setSuggested] = useState<FieldSuggestion[] | null>(null);
  const dirty = useRef(0);
  const camera = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const auth = getStoredAuth();
    if (!auth || !(isCaregiverRole(auth.role) || isFieldStaff())) {
      router.replace("/login");
      return;
    }
    loadFieldAssessment(jobId)
      .then((data) => {
        setForm(data);
        setClient(data.client ?? null);
        let r = data.ratings || {};
        let n = data.item_notes || {};
        let l = data.answer_labels || {};
        let p = (data.resident_profile || {}) as typeof profile;
        try {
          const local = JSON.parse(localStorage.getItem(draftKey) || "null");
          if (
            local &&
            Object.keys(local.ratings || {}).length > Object.keys(r).length
          ) {
            r = local.ratings;
            n = local.notes || n;
            l = local.labels || l;
            p = local.profile || p;
          }
        } catch {
          // No local draft.
        }
        // Details already on file: open at the questions — at the first unanswered one
        // when continuing a draft (set once the steps are known, below).
        if (data.client?.confirmed) setResumeAt(Object.keys(r).length ? "gap" : "start");
        setRatings(r);
        setNotes(n);
        setLabels(l);
        setProfile(p);
        if (data.status === "completed") setDone({ score: data.score });
      })
      .catch((e) =>
        setError(
          e instanceof Error ? e.message : "Could not load the assessment",
        ),
      );
  }, [jobId, router, draftKey]);

  const steps: Step[] = useMemo(() => {
    if (!form) return [];
    // Questions that didn't apply to this home last time stay hidden (still N/A) unless asked for.
    const hidden = new Set(
      showSkipped
        ? []
        : (form.skip_for_home || []).filter((id) => ratings[id] === "na"),
    );
    const sections: Step[] = form.categories
      .map((c) => ({
        kind: "section" as const,
        cat: sectionTitle(c.title),
        items: c.items
          .filter((i) => !hidden.has(i.id))
          .map((i) => ({
            cat: sectionTitle(c.title),
            id: i.id,
            label: i.label,
            group: i.group,
            input: i.input_type,
            hint: i.hint,
            ask: i.ask,
            options: i.options,
          })),
      }))
      .filter((c) => c.items.length > 0);
    // 3 stages: client info → assessment (profile + sections) → review.
    return [
      { kind: "client" },
      { kind: "profile" },
      ...sections,
      { kind: "review" },
    ];
    // eslint-disable-next-line react-hooks/exhaustive-deps -- recompute only when the toggle or form changes
  }, [form, showSkipped]);
  const skippedCount = (form?.skip_for_home || []).filter(
    (id) => ratings[id] === "na",
  ).length;

  const questions = steps.flatMap((s) => (s.kind === "section" ? s.items : []));
  const isAnswered = (q: Question) => answeredIn(q, ratings, notes);
  const answered = questions.filter(isAnswered).length;
  const missing = unansweredQuestions(steps, ratings, notes);
  useEffect(() => {
    if (!resumeAt || !steps.length) return;
    // "start": the "Before you start" questions. "gap": the first unanswered section, or Review.
    setIndex(resumeAt === "start" ? 1 : (missing[0]?.step ?? steps.length - 1));
    setResumeAt("");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, when the steps are first known
  }, [resumeAt, steps.length]);

  const save = useCallback(
    async (complete = false, where: LocationPayload | null = null) => {
      setSaving("saving");
      try {
        const res = await saveFieldAssessment(jobId, {
          ratings,
          item_notes: notes,
          answer_labels: labels,
          resident_profile: profile,
          complete,
          ...(where ?? {}),
        });
        dirty.current = 0;
        setSaving("saved");
        setSaveError("");
        try {
          if (complete) localStorage.removeItem(draftKey);
        } catch {
          // ignore
        }
        return res;
      } catch (e) {
        setSaving("error");
        // Answers stay on this device either way; say why the server didn't take them.
        setSaveError(
          `Not saved to the server: ${e instanceof Error ? e.message : "no connection"}. Your answers are kept on this device — tap Save draft to try again.`,
        );
        throw e;
      }
    },
    [jobId, ratings, notes, labels, profile, draftKey],
  );

  // Keep a local copy on every change; save to the server every few answers.
  useEffect(() => {
    if (!form) return;
    try {
      localStorage.setItem(
        draftKey,
        JSON.stringify({ ratings, notes, labels, profile }),
      );
    } catch {
      // ignore
    }
    if (dirty.current >= 5) save().catch(() => undefined);
  }, [ratings, notes, labels, profile, form, draftKey, save]);

  const step = steps[index];
  const go = (next: number) => {
    // Moving between sections saves the draft (never needs every answer or a location).
    if (dirty.current > 0) save().catch(() => undefined);
    setIndex(Math.max(0, Math.min(steps.length - 1, next)));
    window.scrollTo({ top: 0 });
  };
  const jumpTo = (u: Unanswered | undefined) => {
    if (!u) return;
    setFocus((f) => ({ id: u.id, tick: (f?.tick ?? 0) + 1 }));
    go(u.step);
  };
  // Keep the current section's tab in view (centred) in the sideways tab bar.
  const tabs = useRef<HTMLElement>(null);
  useEffect(() => {
    const nav = tabs.current;
    const tab = nav?.querySelector<HTMLElement>(".fa-sec.is-on");
    if (!nav || !tab) return;
    nav.scrollTo({ left: tab.offsetLeft - (nav.clientWidth - tab.offsetWidth) / 2, behavior: "smooth" });
  }, [index, form]);
  // Bring the question asked for into view (below the sticky bars).
  useEffect(() => {
    if (!focus) return;
    const el = document.getElementById(`fa-q-${focus.id}`);
    if (el) {
      el.scrollIntoView({ block: "center" });
      el.querySelector<HTMLElement>("button, textarea")?.focus({
        preventScroll: true,
      });
    }
  }, [focus, index]);

  async function saveDraft() {
    try {
      await save();
    } catch {
      // saveError says what happened.
    }
  }

  function answer(id: string, value: string, label?: string) {
    setRatings((r) => ({ ...r, [id]: value }));
    setLabels((l) => {
      const next = { ...l };
      if (label) next[id] = label;
      else delete next[id];
      return next;
    });
    dirty.current += 1;
  }

  async function addPhoto(file: File | undefined, room: string) {
    if (!file) return;
    setPhotoBusy(true);
    try {
      const res = await uploadFieldPhoto(jobId, file, room);
      setPhotos(res.count);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not upload the photo");
    } finally {
      setPhotoBusy(false);
      if (camera.current) camera.current.value = "";
    }
  }

  // Suggested products refresh when the caregiver reaches the review screen.
  const atReview = steps[index]?.kind === "review";
  useEffect(() => {
    if (!atReview) return;
    save()
      .then(() => fieldSuggestions(jobId))
      .then(setSuggested)
      .catch(() => setSuggested([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [atReview, jobId]);

  const showBlocker = () =>
    window.setTimeout(
      () => blocker.current?.scrollIntoView({ block: "start" }),
      50,
    );

  async function submit() {
    if (submitting) return;
    // Every question needs an answer (the last option covers "doesn't apply"); an
    // unanswered one would count as a risk and publish a misleading score.
    if (client && !client.confirmed) {
      go(0);
      return;
    }
    if (missing.length > 0) {
      setShowMissing(true);
      setError("");
      showBlocker();
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      // Finishing closes the visit: the caregiver app needs where it was finished.
      // Office staff are not asked (their route does not take a location).
      let where: LocationPayload | null = null;
      if (!staff) {
        setLocating(true);
        try {
          where = await requireLocation();
          setLocNeed(false);
        } catch {
          setLocNeed(true);
          showBlocker();
          return;
        } finally {
          setLocating(false);
        }
      }
      const res = await save(true, where);
      setDone({ score: res.score });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not submit");
      showBlocker();
    } finally {
      setSubmitting(false);
    }
  }

  if (error && !form) {
    return (
      <div className={`cg-app ${portalFont.variable}`}>
        <main className="cg-main">
          <p className="cg-note is-warn">{error}</p>
          <Link className="cg-btn is-ghost" href={backHref}>
            {backLabel}
          </Link>
        </main>
      </div>
    );
  }

  if (!form || !step) {
    return (
      <div className={`cg-app ${portalFont.variable}`}>
        <main className="cg-main">
          <p className="cg-empty">Loading the assessment…</p>
        </main>
      </div>
    );
  }

  if (done) {
    return (
      <div className={`cg-app ${portalFont.variable}`}>
        <main className="cg-main fa-done">
          <section className="cg-hero">
            <p className="cg-eyebrow">Assessment submitted</p>
            <h1>{form.job.elder_name}</h1>
            <p className="cg-hero-sub">
              {done.score != null
                ? `${publicSafetyScoreName()} ${done.score}/100. `
                : ""}
              The family can see the report now.
            </p>
          </section>
          {staff ? (
            <div className="fa-done-actions">
              <Link
                className="cg-btn"
                href={`/kushalaya/customers/${form.job.elder_id}?tab=assessments`}
              >
                View report
              </Link>
              <Link
                className="cg-btn is-ghost"
                href={`/kushalaya/customers/${form.job.elder_id}?tab=orders`}
              >
                Review suggested products
              </Link>
              <Link className="cg-btn is-ghost" href={backHref}>
                {backLabel}
              </Link>
            </div>
          ) : (
            <Link className="cg-btn" href={backHref}>
              {backLabel}
            </Link>
          )}
        </main>
      </div>
    );
  }

  const pct = Math.round((answered / Math.max(1, questions.length)) * 100);
  const counts = {
    safe: questions.filter((q) => ratings[q.id] === "excellent").length,
    watch: questions.filter((q) => ratings[q.id] === "acceptable").length,
    risk: questions.filter((q) => ratings[q.id] === "unsafe").length,
  };
  const risks = questions.filter((q) => ratings[q.id] === "unsafe");
  const firstOpen = missing[0]?.step ?? -1;
  const missingHere =
    step.kind === "section"
      ? missing.filter((m) => m.step === index).length
      : 0;
  const sectionOf = (id: string) =>
    steps.findIndex(
      (s) => s.kind === "section" && s.items.some((q) => q.id === id),
    );

  return (
    <div className={`cg-app ${portalFont.variable}`}>
      <div className="fa-top">
        <header className="fa-bar">
          <Link href={backHref} className="fa-back" aria-label={backLabel}>
            ←
          </Link>
          <div className="fa-bar-text">
            <strong>{form.job.elder_name}</strong>
            <small>
              {answered} of {questions.length} answered
              {saving === "idle"
                ? ""
                : saving === "saving"
                  ? " · Saving…"
                  : saving === "error"
                    ? " · Not saved yet"
                    : " · Saved"}
            </small>
          </div>
          <button
            type="button"
            className="fa-save"
            onClick={() => void saveDraft()}
            disabled={saving === "saving" || submitting}
          >
            {saving === "saving" ? "Saving…" : "Save draft"}
          </button>
        </header>
        <div className="fa-progress" aria-hidden="true">
          <span style={{ width: `${pct}%` }} />
        </div>
        <nav ref={tabs} className="fa-sections" aria-label="Sections">
          {steps.map((s, i) => {
            if (s.kind === "client" || s.kind === "review") {
              const ok =
                s.kind === "client" ? Boolean(client?.confirmed) : false;
              return (
                <button
                  key={s.kind}
                  type="button"
                  className={`fa-sec${i === index ? " is-on" : ""}${ok ? " is-done" : ""}`}
                  aria-current={i === index ? "step" : undefined}
                  onClick={() => go(i)}
                >
                  {s.kind === "client" ? "1 · Client info" : "3 · Review"}
                  {ok ? <small>✓</small> : null}
                </button>
              );
            }
            if (s.kind !== "section") return null;
            const done = s.items.filter(isAnswered).length;
            return (
              <button
                key={s.cat}
                type="button"
                className={`fa-sec${i === index ? " is-on" : ""}${done === s.items.length ? " is-done" : showMissing ? " is-missing" : ""}`}
                aria-current={i === index ? "step" : undefined}
                onClick={() => go(i)}
              >
                {s.cat}
                <small>
                  {done}/{s.items.length}
                </small>
              </button>
            );
          })}
        </nav>
      </div>

      <main className="cg-main fa-main">
        {saveError ? (
          <div className="cg-note is-warn fa-banner" role="status">
            <span>{saveError}</span>
            <button
              type="button"
              className="cg-btn is-ghost"
              onClick={() => void saveDraft()}
              disabled={saving === "saving"}
            >
              {saving === "saving" ? "Saving…" : "Try again"}
            </button>
          </div>
        ) : null}
        {error && step.kind !== "review" ? (
          <p className="cg-note is-warn">{error}</p>
        ) : null}
        {step.kind === "client" && client ? (
          <ClientStep
            jobId={jobId}
            client={client}
            onSaved={(c) => {
              setClient(c);
              go(1);
            }}
          />
        ) : null}

        {step.kind === "profile" ? (
          <section className="fa-card">
            {skippedCount > 0 && (
              <p className="fa-skipped">
                {skippedCount} question{skippedCount === 1 ? "" : "s"} didn’t
                apply to this home last time — already marked Not applicable.{" "}
                <button
                  type="button"
                  className="fa-skipped-link"
                  onClick={() => setShowSkipped((v) => !v)}
                >
                  {showSkipped ? "Hide them" : "Show them"}
                </button>
              </p>
            )}
            <p className="fa-cat">Step 2 of 3 · Before you start</p>
            <h1 className="fa-q">About the home</h1>
            <div className="fa-list">
              {(
                [
                  {
                    key: "stairs",
                    ask: "Are there stairs or steps in the home?",
                    done: profile.hasStairs !== undefined,
                    opts: [
                      {
                        l: "Yes",
                        on: profile.hasStairs === true,
                        pick: () =>
                          setProfile((p) => ({ ...p, hasStairs: true })),
                      },
                      {
                        l: "No",
                        on: profile.hasStairs === false,
                        pick: () =>
                          setProfile((p) => ({ ...p, hasStairs: false })),
                      },
                    ],
                  },
                  {
                    key: "aid",
                    ask: "Does the person use a mobility aid?",
                    done: Boolean(profile.mobilityDevice),
                    opts: MOBILITY.map((o) => ({
                      l: o.label,
                      on: profile.mobilityDevice === o.value,
                      pick: () =>
                        setProfile((p) => ({ ...p, mobilityDevice: o.value })),
                    })),
                  },
                ] as const
              ).map((item) => (
                // Same question card and option buttons as the sections that follow.
                <div
                  key={item.key}
                  className={`fa-item${item.done ? " is-answered" : flagStep === index ? " is-missing" : ""}`}
                >
                  <p className="fa-item-q">{item.ask}</p>
                  {!item.done && flagStep === index ? (
                    <p className="fa-req">Answer this question</p>
                  ) : null}
                  <div className="fa-opts">
                    {item.opts.map((o) => (
                      <button
                        key={o.l}
                        type="button"
                        className={`fa-opt is-pick${o.on ? " is-on" : ""}`}
                        aria-pressed={o.on}
                        onClick={o.pick}
                      >
                        {o.l}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <button
              type="button"
              className="cg-btn fa-next"
              onClick={() => {
                if (
                  profile.hasStairs === undefined ||
                  !profile.mobilityDevice
                ) {
                  setFlagStep(index);
                  return;
                }
                setFlagStep(null);
                go(firstOpen > 1 ? firstOpen : 2);
              }}
            >
              {answered ? "Continue" : "Start"}
            </button>
          </section>
        ) : null}

        {step.kind === "section" ? (
          <section className="fa-card">
            <p className="fa-cat">
              Step 2 of 3 · Section {steps.indexOf(step) - 1} of{" "}
              {steps.length - 3}
            </p>
            <h1 className="fa-q">{step.cat}</h1>
            {showMissing && missingHere ? (
              <p className="fa-missing-note" role="status">
                {missingHere} question{missingHere === 1 ? "" : "s"} below still
                need{missingHere === 1 ? "s" : ""} an answer — marked in red.
              </p>
            ) : null}
            <ol className="fa-list">
              {step.items.map((q) => {
                const words = caregiverAnswers(q.id);
                const opts = questionOptions({ id: q.id, label: q.label, help: q.hint, options: q.options });
                // The tapped option, else the first option that saves this rating (older answers).
                const onLabel =
                  labels[q.id] && opts.some((o) => o.label === labels[q.id] && o.rating === ratings[q.id])
                    ? labels[q.id]
                    : opts.find((o) => o.rating === ratings[q.id])?.label;
                return (
                  <li
                    key={q.id}
                    id={`fa-q-${q.id}`}
                    className={`fa-item${isAnswered(q) ? " is-answered" : showMissing || flagStep === index ? " is-missing" : ""}`}
                  >
                    {showMissing && !isAnswered(q) ? (
                      <span className="fa-tag">Not answered yet</span>
                    ) : null}
                    <p className="fa-item-q">{questionAsk({ id: q.id, label: q.label, ask: q.ask })}</p>
                    {!isAnswered(q) && (showMissing || flagStep === index) ? (
                      <p className="fa-req">Answer this question</p>
                    ) : null}
                    {q.hint && !words && !q.options?.length ? (
                      <p className="fa-hint">{splitHelp(q.hint).lookFor || q.hint}</p>
                    ) : null}
                    {q.input === "text" ? (
                      <textarea
                        className="fa-text"
                        rows={3}
                        value={notes[q.id] || ""}
                        onChange={(e) => {
                          setNotes((n) => ({ ...n, [q.id]: e.target.value }));
                          dirty.current += 1;
                        }}
                        placeholder="Type your answer"
                      />
                    ) : q.input === "yesno" ? (
                      <div className="fa-opts">
                        <button
                          type="button"
                          className={`fa-opt is-safe${ratings[q.id] === "excellent" ? " is-on" : ""}`}
                          aria-pressed={ratings[q.id] === "excellent"}
                          onClick={() => answer(q.id, "excellent")}
                        >
                          {ratings[q.id] === "excellent" ? "✓ " : ""}
                          Yes
                        </button>
                        <button
                          type="button"
                          className={`fa-opt is-risk${ratings[q.id] === "unsafe" ? " is-on" : ""}`}
                          aria-pressed={ratings[q.id] === "unsafe"}
                          onClick={() => answer(q.id, "unsafe")}
                        >
                          {ratings[q.id] === "unsafe" ? "✓ " : ""}
                          No
                        </button>
                      </div>
                    ) : (
                      <div className={`fa-opts${opts.length === 3 ? " is-3" : ""}`}>
                        {opts.map((o, k) => {
                          const on = onLabel === o.label && ratings[q.id] === o.rating;
                          const tone = RATING_BUTTONS.find((b) => b.value === o.rating)?.tone ?? "";
                          return (
                            <button
                              key={`${k}-${o.label}`}
                              type="button"
                              className={`fa-opt ${tone}${on ? " is-on" : ""}`}
                              aria-pressed={on}
                              onClick={() => answer(q.id, o.rating, o.label)}
                            >
                              {on ? "✓ " : ""}
                              {o.label}
                            </button>
                          );
                        })}
                      </div>
                    )}
                    {q.input !== "text" ? (
                      noteOpen[q.id] || notes[q.id] ? (
                        <textarea
                          className="fa-text"
                          rows={2}
                          value={notes[q.id] || ""}
                          onChange={(e) => {
                            setNotes((n) => ({ ...n, [q.id]: e.target.value }));
                            dirty.current += 1;
                          }}
                          placeholder="Note (optional)"
                        />
                      ) : (
                        <button
                          type="button"
                          className="fa-link"
                          onClick={() =>
                            setNoteOpen((o) => ({ ...o, [q.id]: true }))
                          }
                        >
                          + Add a note
                        </button>
                      )
                    ) : null}
                  </li>
                );
              })}
            </ol>


            {showMissing && missing.length && !missingHere ? (
              <button
                type="button"
                className="cg-btn is-soft fa-next"
                onClick={() => jumpTo(missing[0])}
              >
                Next unanswered question ({missing.length} left)
              </button>
            ) : null}
            <div className="fa-nav">
              <button
                type="button"
                className="cg-btn is-ghost"
                onClick={() => go(index - 1)}
              >
                Back
              </button>
              <button
                type="button"
                className="cg-btn"
                onClick={() => {
                  const gap =
                    step.kind === "section"
                      ? step.items.find((q) => !isAnswered(q))
                      : undefined;
                  if (gap) {
                    // Show what is missing here (red) and stay; the section tabs still jump anywhere.
                    setFlagStep(index);
                    setFocus((f) => ({ id: gap.id, tick: (f?.tick ?? 0) + 1 }));
                    return;
                  }
                  setFlagStep(null);
                  go(index + 1);
                }}
              >
                {steps[index + 1]?.kind === "review"
                  ? "Review"
                  : "Next section"}
              </button>
            </div>
          </section>
        ) : null}

        {step.kind === "review" ? (
          <section className="fa-card">
            <p className="fa-cat">Step 3 of 3 · Review</p>
            {client ? (
              <div
                className={
                  client.confirmed
                    ? "fa-client-sum"
                    : "fa-client-sum is-missing"
                }
              >
                <div>
                  <strong>
                    {[client.details.first_name, client.details.last_name]
                      .filter(Boolean)
                      .join(" ") || "Client"}
                  </strong>
                  <small>
                    {client.confirmed
                      ? [
                          client.details.address,
                          client.details.city,
                          client.details.pincode,
                        ]
                          .filter(Boolean)
                          .join(", ") +
                        (client.location?.mode === "auto"
                          ? " · location detected"
                          : " · address entered manually")
                      : "Client details and home location not confirmed yet"}
                  </small>
                </div>
                <button
                  type="button"
                  className="cg-btn is-ghost"
                  onClick={() => go(0)}
                >
                  {client.confirmed ? "Edit" : "Confirm details"}
                </button>
              </div>
            ) : null}
            <h1 className="fa-q">
              {answered} of {questions.length} answered
            </h1>
            <div className="fa-summary">
              <span className="is-safe">
                <strong>{counts.safe}</strong> Safe
              </span>
              <span className="is-watch">
                <strong>{counts.watch}</strong> Needs attention
              </span>
              <span className="is-risk">
                <strong>{counts.risk}</strong> Risk
              </span>
            </div>
            {risks.length ? (
              <>
                <h2 className="fa-q is-small">Risks found</h2>
                <ul className="fa-risks">
                  {risks.map((q) => (
                    <li key={q.id}>
                      <button type="button" onClick={() => go(sectionOf(q.id))}>
                        {q.label}
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
            {suggested && suggested.length ? (
              <>
                <h2 className="fa-q is-small">Suggested for this home</h2>
                <ul className="fa-sugg">
                  {suggested.map((s) => (
                    <li
                      key={s.product_id}
                      className={s.priority === "high" ? "is-high" : ""}
                    >
                      <strong>{s.name}</strong>
                      <small>{s.reasons.map((r) => r.label).join(" · ")}</small>
                    </li>
                  ))}
                </ul>
                <p className="fa-hint">
                  Your manager turns these into an order with the family.
                </p>
              </>
            ) : null}
            <div ref={blocker} className="fa-blockers">
              {missing.length ? (
                <div
                  className={`fa-left${showMissing ? " is-alert" : ""}`}
                  role={showMissing ? "alert" : undefined}
                >
                  <strong>{unansweredTitle(missing.length)}</strong>
                  <p>
                    Every question needs an answer before you submit. If one
                    doesn’t apply to this home, choose the last option.
                  </p>
                  <ul className="fa-left-list">
                    {unansweredBySection(missing).map((s) => (
                      <li key={s.step}>
                        <button
                          type="button"
                          onClick={() =>
                            jumpTo(missing.find((m) => m.step === s.step))
                          }
                        >
                          {s.cat} <span>{s.count} left</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                  <button
                    type="button"
                    className="cg-btn"
                    onClick={() => jumpTo(missing[0])}
                  >
                    Go to the first unanswered question
                  </button>
                </div>
              ) : null}
              {error ? (
                <p className="cg-note is-warn" role="alert">
                  {error}
                </p>
              ) : null}
              {locNeed ? (
                <LocationNeeded
                  action="completed"
                  busy={locating}
                  onRetry={() => void submit()}
                  onCancel={() => setLocNeed(false)}
                />
              ) : null}
            </div>
            <button
              type="button"
              className="cg-btn is-out fa-next"
              onClick={() => void submit()}
              disabled={submitting}
            >
              {locating
                ? "Finding you…"
                : submitting
                  ? "Submitting…"
                  : "Submit assessment"}
            </button>
            <p className="fa-hint">
              The score and report go to the family as soon as you submit.
            </p>
          </section>
        ) : null}
      </main>
    </div>
  );
}
