"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { zonePlace } from "@/lib/ist";
import { familyTime } from "@/lib/livewell/familyTime";
import { useFamilyTimezone } from "@/lib/family-zone";
import { FamilyLink } from "./FamilyLink";
import { askCareTeam, fetchFamilyQuestions, type AskInput, type FamilyQuestion } from "@/lib/family-contacts";

const WINDOWS: { value: NonNullable<AskInput["window"]>; label: string }[] = [
  { value: "asap", label: "As soon as you can" },
  { value: "morning", label: "Morning (9 AM–12 PM)" },
  { value: "afternoon", label: "Afternoon (12–5 PM)" },
  { value: "evening", label: "Evening (5–8 PM)" },
];

/**
 * "Call me" / "Ask about…" (K2 #91). With `visit` it asks about that visit (and its
 * KushLife flag, if any). The question goes to the Family Partner; the whole family sees it.
 */
export function FamilyAskButtons({
  visit,
  flagKey,
  onSent,
  compact = false,
}: {
  visit?: { ref: string; label: string };
  flagKey?: string;
  onSent?: (q: FamilyQuestion) => void;
  compact?: boolean;
}) {
  const [mode, setMode] = useState<"" | "call_me" | "ask">("");
  const [day, setDay] = useState<"today" | "tomorrow">("today");
  const [win, setWin] = useState<NonNullable<AskInput["window"]>>("asap");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const tz = useFamilyTimezone();

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!mode) return;
    setBusy(true);
    setNote(null);
    try {
      const q = await askCareTeam({
        kind: mode,
        body: text.trim() || undefined,
        ...(mode === "call_me" ? { window: win, day: win === "asap" ? "today" : day } : {}),
        ...(visit ? { visit_ref: visit.ref, visit_label: visit.label } : {}),
        ...(flagKey ? { flag_key: flagKey } : {}),
      });
      setNote({
        ok: true,
        text:
          mode === "call_me"
            ? `Sent. Your Family Partner will call you — ${q.call_window.toLowerCase()}.`
            : "Sent. Your Family Partner usually replies within a day — here and in Messages.",
      });
      setMode("");
      setText("");
      onSent?.(q);
    } catch (err) {
      setNote({ ok: false, text: err instanceof Error ? err.message : "Couldn't send" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`fh-ask${compact ? " is-compact" : ""}`}>
      <div className="fh-ask-btns">
        <button
          type="button"
          className={mode === "call_me" ? "" : "secondary"}
          aria-expanded={mode === "call_me"}
          onClick={() => {
            setNote(null); // a fresh form never shows the last "Sent"
            setMode((m) => (m === "call_me" ? "" : "call_me"));
          }}
        >
          Call me
        </button>
        <button
          type="button"
          className={mode === "ask" ? "" : "secondary"}
          aria-expanded={mode === "ask"}
          onClick={() => {
            setNote(null);
            setMode((m) => (m === "ask" ? "" : "ask"));
          }}
        >
          {visit ? "Ask about this visit" : "Ask about…"}
        </button>
      </div>
      {mode ? (
        <form className="fh-details-form fh-ask-form" onSubmit={(e) => void submit(e)}>
          {mode === "call_me" ? (
            <>
              <label>
                <span className="muted">When suits you?</span>
                <select value={win} onChange={(e) => setWin(e.target.value as typeof win)}>
                  {WINDOWS.map((w) => (
                    <option key={w.value} value={w.value}>
                      {w.label}
                    </option>
                  ))}
                </select>
              </label>
              <p className="muted fh-ask-zone">
                {/* Same label as everywhere else: "IST" for India. */}
                Times are {zonePlace(tz) === "India" ? "IST" : `${zonePlace(tz)} time`} —{" "}
                <FamilyLink href="/kushalaya/family/details">change</FamilyLink>
              </p>
              {win !== "asap" ? (
                <label>
                  <span className="muted">Day</span>
                  <select value={day} onChange={(e) => setDay(e.target.value as typeof day)}>
                    <option value="today">Today</option>
                    <option value="tomorrow">Tomorrow</option>
                  </select>
                </label>
              ) : null}
              <label>
                <span className="muted">What is it about? (optional)</span>
                <input value={text} maxLength={1000} onChange={(e) => setText(e.target.value)} />
              </label>
            </>
          ) : (
            <label>
              <span className="muted">{visit ? `Your question about ${visit.label}` : "Your question"}</span>
              <textarea rows={3} value={text} maxLength={1000} required onChange={(e) => setText(e.target.value)} />
            </label>
          )}
          <button type="submit" disabled={busy}>
            {busy ? "Sending…" : mode === "call_me" ? "Ask for a call" : "Send question"}
          </button>
        </form>
      ) : null}
      {note ? (
        <p className={note.ok ? "muted" : "error-text"} role="status">
          {note.text}
        </p>
      ) : null}
    </div>
  );
}

/** Questions from anyone in the family for this parent, with the care team's replies. */
export function FamilyQuestionsCard() {
  const [rows, setRows] = useState<FamilyQuestion[] | null>(null);
  const load = useCallback(() => {
    fetchFamilyQuestions()
      .then(setRows)
      .catch(() => setRows([]));
  }, []);
  useEffect(load, [load]);

  const recent = (rows ?? []).slice(0, 5);
  const tz = useFamilyTimezone();
  return (
    <section className="fh-home-card fh-questions" aria-labelledby="fh-q-h">
      <h2 id="fh-q-h">Talk to your Family Partner</h2>
      <FamilyAskButtons onSent={load} />
      {recent.length ? (
        <ul className="fh-q-list">
          {recent.map((q) => (
            <li key={q.id} className={q.status === "open" ? "is-open" : undefined}>
              <p>
                <strong>{q.kind === "call_me" ? `Call request · ${q.call_window}` : q.visit_label ? `About ${q.visit_label}` : "Question"}</strong>
                <small className="muted">
                  {" "}
                  {q.is_mine ? "You" : q.asker_name}
                  {q.created_at ? ` · ${familyTime(q.created_at, tz)}` : ""}
                </small>
              </p>
              {q.body ? <p>{q.body}</p> : null}
              {q.reply ? (
                <p className="fh-q-reply">
                  <strong>{q.replied_by_name || "Care team"}:</strong> {q.reply}
                </p>
              ) : (
                <p className="muted">{q.status === "done" ? "Done" : "Waiting for a reply"}</p>
              )}
            </li>
          ))}
        </ul>
      ) : rows ? (
        <p className="muted">Your Family Partner usually replies within a day.</p>
      ) : null}
    </section>
  );
}
