"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { OpsModal } from "@/components/ops/OpsModal";
import { formatIST } from "@/lib/ist";
import { api, } from "@/lib/api";
import { Flash } from "@/components/Flash";
import "@/components/ops/hiring.css";
import { isAdmin as isAdminUser } from "@/lib/roles";

type Applicant = {
  id: number;
  first_name: string;
  last_name: string;
  phone: string | null;
  email: string | null;
  address: string | null;
  source: string | null;
  stage: string;
  status: string;
  notes: string | null;
  years_experience: number | null;
  lost_reason: string | null;
  converted_caregiver_id: number | null;
  created_at: string;
};
type Note = { id: number; activity_type: string; body: string; created_by_name: string | null; created_at: string };

/** The selection steps, in order. Rejected sits outside the flow. */
const STEPS: { key: string; label: string; hint: string }[] = [
  { key: "APPLIED", label: "Applied", hint: "New applications" },
  { key: "SCREENING", label: "Phone screen", hint: "Quick call: availability, area, languages" },
  { key: "INTERVIEW", label: "Interview", hint: "Meet in person, score the interview" },
  { key: "DOCS_PENDING", label: "Documents", hint: "Aadhaar, address proof, certificates" },
  { key: "VERIFICATION", label: "Background check", hint: "Police verification and references" },
  { key: "TRAINING", label: "Training", hint: "BLS & CPR, home safety basics" },
  { key: "HIRED", label: "Hired", hint: "Added to your caregivers" },
];
const LABEL = Object.fromEntries(STEPS.map((s) => [s.key, s.label]));

/** Interview scorecard: 1–5 on each, saved as a note on the applicant. */
const SCORE_ON = ["Communication", "Experience with elders", "Patience & attitude", "Hygiene & presentation", "Reliability"];

/** Quick reasons for "Not selected" (the team can still type their own). */
const REASONS = [
  "No reply",
  "Not free for our shifts",
  "Lives too far",
  "Not enough experience",
  "Didn't give documents",
  "Background check failed",
  "Took another job",
];

/** Whole days since an ISO date. */
function daysSince(iso: string) {
  return Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000));
}

const EMPTY = { first_name: "", last_name: "", phone: "", email: "", address: "", source: "", years_experience: "", notes: "" };

/** Backend history lines use stage codes ("Prospect created in stage APPLIED"); show plain words. */
function plain(body: string) {
  return body
    .replace(/\bProspect\b/g, "Applicant")
    .replace(/\b(APPLIED|SCREENING|INTERVIEW|DOCS_PENDING|VERIFICATION|TRAINING|HIRED|REJECTED|WON)\b/g, (m) =>
      m === "REJECTED" ? "Not selected" : m === "WON" ? "Hired" : LABEL[m] || m,
    )
    .replace(/ in stage /g, " at ");
}

/** One date format across ops (lib/ist.ts): "Wed 7 Oct". */
function fmt(iso: string) {
  return formatIST(iso, { dateOnly: true }) || "";
}

/** Hiring: caregiver applicants from application to hired. */
export default function HiringPage() {
  const isAdmin = isAdminUser();
  const [rows, setRows] = useState<Applicant[]>([]);
  const [showRejected, setShowRejected] = useState(false);
  const [adding, setAdding] = useState(false);
  // Phone: one stage at a time, picked from a dropdown. Laptop: the whole
  // board, with a hint when some stages are off to the right.
  const [phoneStage, setPhoneStage] = useState(STEPS[0]!.key);
  const boardRef = useRef<HTMLDivElement>(null);
  const [moreRight, setMoreRight] = useState(false);

  useEffect(() => {
    const el = boardRef.current;
    if (!el) return;
    const check = () => setMoreRight(el.scrollWidth - el.clientWidth - el.scrollLeft > 8);
    check();
    el.addEventListener("scroll", check, { passive: true });
    window.addEventListener("resize", check);
    return () => {
      el.removeEventListener("scroll", check);
      window.removeEventListener("resize", check);
    };
  }, [rows]);
  const [form, setForm] = useState(EMPTY);
  const [open, setOpen] = useState<Applicant | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [note, setNote] = useState("");
  const [scores, setScores] = useState<Record<string, number>>({});
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    setRows(await api<Applicant[]>("/api/v1/prospects/caregivers"));
    setLoaded(true);
  }, []);

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [load]);

  const byStep = useMemo(() => {
    const m: Record<string, Applicant[]> = {};
    for (const r of rows) (m[r.stage] ||= []).push(r);
    return m;
  }, [rows]);
  const rejected = byStep.REJECTED || [];

  async function openApplicant(a: Applicant) {
    setOpen(a);
    setRejecting(false);
    setReason("");
    setNote("");
    setScores({});
    setNotes([]);
    try {
      setNotes(await api<Note[]>(`/api/v1/prospects/caregivers/${a.id}/activities`));
    } catch {
      // Notes are optional.
    }
  }

  async function add(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api("/api/v1/prospects/caregivers", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          phone: form.phone || null,
          email: form.email || null,
          address: form.address || null,
          source: form.source || null,
          notes: form.notes || null,
          years_experience: form.years_experience ? Number(form.years_experience) : null,
        }),
      });
      setMessage(`${form.first_name} added to Applied.`);
      setForm(EMPTY);
      setAdding(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add");
    } finally {
      setBusy(false);
    }
  }

  async function move(a: Applicant, stage: string, reason?: string) {
    setBusy(true);
    try {
      const updated = await api<Applicant>(`/api/v1/prospects/caregivers/${a.id}/stage`, {
        method: "PATCH",
        body: JSON.stringify({ stage, lost_reason: reason || null }),
      });
      setOpen(updated);
      setRejecting(false);
      setReason("");
      setMessage(`${a.first_name} → ${stage === "REJECTED" ? "Not selected" : LABEL[stage]}.`);
      await load();
      setNotes(await api<Note[]>(`/api/v1/prospects/caregivers/${a.id}/activities`).catch(() => notes));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not move");
    } finally {
      setBusy(false);
    }
  }

  async function hire(a: Applicant) {
    setBusy(true);
    try {
      await api(`/api/v1/prospects/caregivers/${a.id}/convert`, { method: "POST" });
      setMessage(`${a.first_name} is hired and now on your caregiver list (Team). Assign their care manager there.`);
      setOpen(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not hire");
    } finally {
      setBusy(false);
    }
  }

  async function saveNote(e: FormEvent) {
    e.preventDefault();
    if (!open) return;
    const scored = SCORE_ON.filter((k) => scores[k]);
    const card = scored.length
      ? `Interview scorecard — ${scored.map((k) => `${k}: ${scores[k]}/5`).join(", ")} (average ${(
          scored.reduce((s, k) => s + scores[k], 0) / scored.length
        ).toFixed(1)})`
      : "";
    const body = [card, note.trim()].filter(Boolean).join("\n");
    if (!body) return;
    try {
      await api(`/api/v1/prospects/caregivers/${open.id}/activities`, {
        method: "POST",
        body: JSON.stringify({ activity_type: "NOTE", body }),
      });
      setNote("");
      setScores({});
      setNotes(await api<Note[]>(`/api/v1/prospects/caregivers/${open.id}/activities`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
    }
  }

  const stepIndex = open ? STEPS.findIndex((s) => s.key === open.stage) : -1;
  const next = stepIndex >= 0 ? STEPS[stepIndex + 1] : undefined;
  const prev = stepIndex > 0 ? STEPS[stepIndex - 1] : undefined;
  const active = rows.filter((r) => r.stage !== "REJECTED");
  const set = (k: keyof typeof EMPTY) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="ks-frame">
      <div className="ks-head-row">
        <header className="ks-head">
          <h1>Hiring</h1>
          <p className="muted">Caregiver applicants, from applying to first visit</p>
        </header>
        <div className="ks-head-actions">
          <button type="button" onClick={() => setAdding(true)} aria-label="Add applicant" title="Add applicant">
            <span className="ks-ha-icon" aria-hidden="true">+</span>
            <span className="ks-ha-label">+ Add applicant</span>
          </button>
          <Link href="/users" className="hr-team-link" aria-label="Team" title="Hired caregivers are on the Team page">
            <span className="ks-ha-icon" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c.6-3.6 3.3-5.5 6.5-5.5s5.9 1.9 6.5 5.5" /><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18.5 14.8c1.7.7 2.8 2.4 3 5.2" /></svg>
            </span>
            <span className="ks-ha-label">Team →</span>
          </Link>
        </div>
      </div>
      <Flash error={error} message={message} onClear={() => { setError(""); setMessage(""); }} />

      {loaded && active.length === 0 && !adding && (
        <div className="card hr-empty">
          <p>
            <strong>No applicants yet.</strong> Add the first one with <b>+ Add applicant</b>. Each person then moves
            step by step: phone screen, interview, documents, background check, training, hired.
          </p>
        </div>
      )}

      <OpsModal open={adding} title="New applicant" onClose={() => { setAdding(false); setForm(EMPTY); }} wide>
        <form className="hr-form" onSubmit={(e) => void add(e)}>
          {error ? <p className="ks-modal-error hr-wide" role="alert">{error}</p> : null}
          <label>First name<input required value={form.first_name} onChange={set("first_name")} /></label>
          <label>Last name<input required value={form.last_name} onChange={set("last_name")} /></label>
          <label>Phone<input type="tel" value={form.phone} onChange={set("phone")} /></label>
          <label>Email<input type="email" value={form.email} onChange={set("email")} /></label>
          <label>Area / address<input value={form.address} onChange={set("address")} /></label>
          <label>
            Years caring for elders
            <input type="number" min={0} max={50} value={form.years_experience} onChange={set("years_experience")} />
          </label>
          <label>
            Came from
            <select value={form.source} onChange={set("source")}>
              <option value="">Not known</option>
              <option value="referral">Referral</option>
              <option value="walk_in">Walk-in</option>
              <option value="agency">Agency</option>
              <option value="job_portal">Job portal</option>
              <option value="whatsapp">WhatsApp / social</option>
            </select>
          </label>
          <label className="hr-wide">Notes<input value={form.notes} onChange={set("notes")} placeholder="Languages, shifts they can do…" /></label>
          <div className="hr-form-actions">
            <button type="button" className="hr-ghost" onClick={() => { setAdding(false); setForm(EMPTY); }}>Cancel</button>
            <button type="submit" disabled={busy}>{busy ? "Adding…" : "Add to Applied"}</button>
          </div>
        </form>
      </OpsModal>

      <label className="hr-stage-pick">
        <span>Stage</span>
        <select value={phoneStage} onChange={(e) => setPhoneStage(e.target.value)}>
          {STEPS.map((s) => (
            <option key={s.key} value={s.key}>
              {s.label} ({(byStep[s.key] || []).length})
            </option>
          ))}
        </select>
      </label>
      {moreRight ? (
        <p className="hr-more-hint" aria-hidden="true">
          Scroll sideways for more stages →
        </p>
      ) : null}
      <div className="hr-board" ref={boardRef}>
        {STEPS.map((s) => (
          <section
            key={s.key}
            className={`hr-col${s.key === "HIRED" ? " is-hired" : ""}${s.key === phoneStage ? " is-picked" : ""}`}
            aria-label={s.label}
          >
            <header>
              <strong>{s.label}</strong>
              <span className="hr-count">{(byStep[s.key] || []).length}</span>
              <small>{s.hint}</small>
            </header>
            <ul>
              {(byStep[s.key] || []).map((a) => {
                const days = daysSince(a.created_at);
                return (
                  <li key={a.id}>
                    <button type="button" className={`hr-card${open?.id === a.id ? " is-open" : ""}`} onClick={() => void openApplicant(a)}>
                      <strong>{a.first_name} {a.last_name}</strong>
                      <small>
                        {[a.years_experience != null ? `${a.years_experience} yr` : "", a.address].filter(Boolean).join(" · ")}
                      </small>
                      {s.key !== "HIRED" && (
                        <span className={`hr-age${days >= 7 ? " is-old" : ""}`} title={`Applied ${fmt(a.created_at)}`}>
                          {days === 0 ? "Today" : `${days} day${days === 1 ? "" : "s"}`}
                        </span>
                      )}
                    </button>
                  </li>
                );
              })}
              {(byStep[s.key] || []).length === 0 && <li className="hr-none">No one here</li>}
            </ul>
          </section>
        ))}
      </div>

      {rejected.length > 0 && (
        <p className="hr-rejected-toggle">
          <button type="button" className="hr-link" onClick={() => setShowRejected((v) => !v)}>
            {showRejected ? "Hide" : "Show"} not selected ({rejected.length})
          </button>
        </p>
      )}
      {showRejected && (
        <ul className="hr-rejected">
          {rejected.map((a) => (
            <li key={a.id}>
              <button type="button" className="hr-link" onClick={() => void openApplicant(a)}>
                {a.first_name} {a.last_name}
              </button>
              <small>{a.lost_reason || "No reason noted"}</small>
            </li>
          ))}
        </ul>
      )}

      {open && (
        <aside className="card hr-detail" aria-label={`${open.first_name} ${open.last_name}`}>
          <div className="hr-detail-head">
            <div>
              <h2>{open.first_name} {open.last_name}</h2>
              <p className="muted">
                {open.stage === "REJECTED" ? "Not selected" : LABEL[open.stage]} ·{" "}
                {[open.phone, open.email].filter(Boolean).join(" · ") || "No contact details"}
              </p>
            </div>
            <button type="button" className="hr-link" onClick={() => setOpen(null)}>Close</button>
          </div>
          {open.notes && <p className="hr-about">{open.notes}</p>}

          {open.converted_caregiver_id ? (
            <p className="hr-hired">Hired — on your caregiver list. <Link href="/users">Open Team →</Link></p>
          ) : open.stage === "REJECTED" ? (
            <div className="hr-actions">
              <button type="button" className="hr-ghost" disabled={busy} onClick={() => void move(open, "APPLIED")}>Reconsider</button>
            </div>
          ) : (
            <>
              <div className="hr-actions">
                {next && next.key !== "HIRED" && (
                  <button type="button" disabled={busy} onClick={() => void move(open, next.key)}>
                    Move to {next.label} →
                  </button>
                )}
                {(open.stage === "TRAINING" || open.stage === "HIRED") && isAdmin && (
                  <button type="button" className="hr-go" disabled={busy} onClick={() => void hire(open)}>
                    Hire — add as caregiver
                  </button>
                )}
                {prev && (
                  <button type="button" className="hr-ghost" disabled={busy} onClick={() => void move(open, prev.key)}>
                    ← Back to {prev.label}
                  </button>
                )}
                <button
                  type="button"
                  className="hr-ghost is-danger"
                  disabled={busy}
                  onClick={() => setRejecting((v) => !v)}
                  aria-expanded={rejecting}
                >
                  Not selected
                </button>
              </div>
              {rejecting && (
                <div className="hr-reject">
                  <p>Why is {open.first_name} not selected? Only your team sees this.</p>
                  <div className="hr-chips">
                    {REASONS.map((r) => (
                      <button
                        key={r}
                        type="button"
                        className={`hr-chip${reason === r ? " is-on" : ""}`}
                        aria-pressed={reason === r}
                        onClick={() => setReason(r)}
                      >
                        {r}
                      </button>
                    ))}
                  </div>
                  <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Or type a reason" maxLength={200} />
                  <div className="hr-actions">
                    <button type="button" className="hr-ghost" onClick={() => setRejecting(false)}>Cancel</button>
                    <button
                      type="button"
                      className="is-danger"
                      disabled={busy}
                      onClick={() => void move(open, "REJECTED", reason.trim() || "Not selected")}
                    >
                      Mark not selected
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          <form className="hr-note" onSubmit={(e) => void saveNote(e)}>
            {open.stage === "INTERVIEW" && (
              <fieldset className="hr-score">
                <legend>Interview scorecard</legend>
                {SCORE_ON.map((k) => (
                  <div key={k} className="hr-score-row">
                    <span>{k}</span>
                    <span className="hr-dots" role="radiogroup" aria-label={k}>
                      {[1, 2, 3, 4, 5].map((n) => (
                        <button
                          key={n}
                          type="button"
                          role="radio"
                          aria-checked={scores[k] === n}
                          className={scores[k] && scores[k] >= n ? "is-on" : ""}
                          onClick={() => setScores({ ...scores, [k]: n })}
                        >
                          {n}
                        </button>
                      ))}
                    </span>
                  </div>
                ))}
              </fieldset>
            )}
            <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add a note — call outcome, references, documents received…" />
            <button type="submit" disabled={!note.trim() && !Object.keys(scores).length}>Save note</button>
          </form>

          {notes.length === 0 && <p className="muted hr-help">No notes yet.</p>}
          <ol className="hr-history">
            {notes.map((n) => (
              <li key={n.id}>
                <small>{fmt(n.created_at)}{n.created_by_name ? ` · ${n.created_by_name}` : ""}</small>
                <p>{plain(n.body)}</p>
              </li>
            ))}
          </ol>
        </aside>
      )}
    </div>
  );
}
