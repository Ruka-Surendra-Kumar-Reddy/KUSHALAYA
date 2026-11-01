"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { formatIST } from "@/lib/ist";
import { api } from "@/lib/api";
import { FAMILY_MESSAGES_API, isCallRequest, type FamilyMessage } from "@/components/ops/MessageThread";
import {
  CHANNEL_OPTIONS,
  LEVEL_OPTIONS,
  TIMEZONE_OPTIONS,
  fetchClientContacts,
  fetchClientQuestions,
  markClientQuestionDone,
  replyClientQuestion,
  saveClientContact,
  timezoneLabel,
  type FamilyContactRow,
  type FamilyQuestion,
} from "@/lib/family-contacts";
import { can } from "@/lib/roles";

const channelLabel = (v: string) => CHANNEL_OPTIONS.find((o) => o.value === v)?.label ?? v;
const levelLabel = (v: string) => LEVEL_OPTIONS.find((o) => o.value === v)?.label ?? v;

/** Overview → How to reach the family: phone, channel, timezone and level per person (K2 #88). */
export function FamilyContactsCard({ elderId }: { elderId: number }) {
  const [rows, setRows] = useState<FamilyContactRow[] | null>(null);
  const [edit, setEdit] = useState<FamilyContactRow | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(() => {
    fetchClientContacts(elderId)
      .then(setRows)
      .catch(() => setRows([]));
  }, [elderId]);
  useEffect(load, [load]);

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!edit) return;
    setBusy(true);
    setNote(null);
    try {
      await saveClientContact(elderId, {
        key: edit.key,
        // Only when changed: an old stored number in another format must not block saving the rest.
        ...(edit.phone !== (rows?.find((r) => r.key === edit.key)?.phone ?? "") ? { phone: edit.phone } : {}),
        channel: edit.channel,
        timezone: edit.timezone,
        level: edit.level,
        ...(edit.has_login ? {} : { name: edit.name }),
      });
      setNote({ ok: true, text: `Saved for ${edit.name}.` });
      setEdit(null);
      load();
    } catch (err) {
      setNote({ ok: false, text: err instanceof Error ? err.message : "Could not save" });
    } finally {
      setBusy(false);
    }
  }

  const canEdit = can("edit");
  return (
    <section className="card fl" id="family-contacts">
      <div className="cp-card-head">
        <h2>How to reach the family</h2>
      </div>
      <p className="muted fl-meta">
        Emails follow each person&apos;s choice. Text and WhatsApp are stored for when they are switched on.
      </p>
      {rows === null ? <p className="muted">Loading…</p> : null}
      {rows && rows.length === 0 ? <p className="muted">No family members yet.</p> : null}
      <ul className="fl-list">
        {(rows ?? []).map((r) => (
          <li key={r.key}>
            <div className="fl-who">
              <strong>{r.name}</strong>
              {r.relationship ? <span className="muted"> · {r.relationship}</span> : null}
              {!r.has_login ? <span className="muted"> · email only</span> : null}
            </div>
            <div className="fl-meta muted">
              {r.phone ? <a href={`tel:${r.phone.replace(/[^0-9+]/g, "")}`}>{r.phone}</a> : "No phone"}
              {` · ${[channelLabel(r.channel), timezoneLabel(r.timezone), levelLabel(r.level)].join(" · ")}`}
              {!r.phone && needsPhone(r.channel) ? (
                <span className="fl-warn"> · ⚠ {channelLabel(r.channel)} needs a phone number — add one or pick Email</span>
              ) : null}
            </div>
            {edit?.key === r.key ? (
              <form className="fl-form" onSubmit={(e) => void save(e)}>
                {!r.has_login ? (
                  <label>
                    Name
                    <input value={edit.name} maxLength={200} onChange={(e) => setEdit({ ...edit, name: e.target.value })} />
                  </label>
                ) : null}
                <label>
                  Phone (with country code)
                  <input
                    type="tel"
                    value={edit.phone}
                    maxLength={30}
                    onChange={(e) => setEdit({ ...edit, phone: e.target.value })}
                  />
                </label>
                <label>
                  Best way to reach
                  <select
                    value={edit.channel}
                    onChange={(e) => setEdit({ ...edit, channel: e.target.value as FamilyContactRow["channel"] })}
                  >
                    {CHANNEL_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value} disabled={needsPhone(o.value) && !edit.phone.trim()}>
                        {o.label}
                        {needsPhone(o.value) && !edit.phone.trim() ? " (add a phone first)" : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Lives in
                  <select value={edit.timezone} onChange={(e) => setEdit({ ...edit, timezone: e.target.value })}>
                    {(TIMEZONE_OPTIONS.some((o) => o.value === edit.timezone)
                      ? TIMEZONE_OPTIONS
                      : [...TIMEZONE_OPTIONS, { value: edit.timezone, label: timezoneLabel(edit.timezone) }]
                    ).map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Wants to hear about
                  <select
                    value={edit.level}
                    onChange={(e) => setEdit({ ...edit, level: e.target.value as FamilyContactRow["level"] })}
                  >
                    {LEVEL_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="fl-form-actions">
                  <button type="submit" disabled={busy}>
                    {busy ? "Saving…" : "Save"}
                  </button>
                  <button type="button" className="cp-linkbtn" onClick={() => setEdit(null)}>
                    Cancel
                  </button>
                </div>
              </form>
            ) : !canEdit ? null : (
              <div className="fl-actions">
                <button type="button" className="cp-linkbtn" onClick={() => setEdit({ ...r })}>
                  Edit
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
      {note ? (
        <p className={note.ok ? "muted" : "error-text"} role="status">
          {note.text}
        </p>
      ) : null}
    </section>
  );
}

/** Overview → Family questions: "Call me" / "Ask about…", reply or mark done (K2 #91). */
export function ClientQuestionsCard({ elderId }: { elderId: number }) {
  const [rows, setRows] = useState<FamilyQuestion[] | null>(null);
  const [replyId, setReplyId] = useState<number | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    fetchClientQuestions(elderId)
      .then((r) => {
        setRows(r);
        if (window.location.hash === "#questions") document.getElementById("questions")?.scrollIntoView({ block: "start" });
      })
      .catch(() => setRows([]));
  }, [elderId]);
  useEffect(load, [load]);

  // "Call me" / "Question…" typed straight into Messages also count, until the team answers.
  const [msgQuestions, setMsgQuestions] = useState(0);
  useEffect(() => {
    api<{ messages: FamilyMessage[] }>(`${FAMILY_MESSAGES_API}/${elderId}`)
      .then((t) => {
        let n = 0;
        for (const m of t.messages ?? []) {
          if (m.sender_role === "team") n = 0;
          else if (isCallRequest(m)) n += 1;
        }
        setMsgQuestions(n);
      })
      .catch(() => setMsgQuestions(0));
  }, [elderId, rows]);

  async function run(key: string, action: () => Promise<unknown>) {
    setBusy(key);
    setError("");
    try {
      await action();
      setReplyId(null);
      setText("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
    } finally {
      setBusy("");
    }
  }

  const open = (rows ?? []).filter((q) => q.status === "open");
  const recent = (rows ?? []).filter((q) => q.status !== "open").slice(0, 5);
  // Each question form also posts its words to Messages, so take the larger count, not the sum.
  const waiting = Math.max(open.length, msgQuestions);
  const inMessagesOnly = waiting - open.length;

  const canEdit = can("edit");
  return (
    <section className="card fl" id="questions">
      <div className="cp-card-head">
        <h2>Family questions{waiting ? ` (${waiting})` : ""}</h2>
      </div>
      {inMessagesOnly > 0 ? (
        <p className="fl-meta">
          {inMessagesOnly === 1 ? "1 question was" : `${inMessagesOnly} questions were`} asked in Messages and{" "}
          {inMessagesOnly === 1 ? "waits" : "wait"} for a reply —{" "}
          <a href={`/kushalaya/messages?elder=${elderId}`}>open Messages</a>.
        </p>
      ) : null}
      <p className="muted fl-meta">The whole family sees each question and your reply (also in Messages).</p>
      {rows === null ? <p className="muted">Loading…</p> : null}
      {rows && rows.length === 0 && !inMessagesOnly ? <p className="muted">No questions yet.</p> : null}
      <ul className="fl-list">
        {[...open, ...recent].map((q) => (
          <li key={q.id} className={q.status === "open" ? undefined : "is-off"}>
            <div className="fl-who">
              <strong>{q.kind === "call_me" ? `Call me · ${q.call_window}` : q.visit_label ? `About ${q.visit_label}` : "Question"}</strong>
              <span className="muted">
                {" "}
                · {q.asker_name}
                {q.asker_phone ? (
                  <>
                    {" · "}
                    <a href={`tel:${q.asker_phone.replace(/[^0-9+]/g, "")}`}>{q.asker_phone}</a>
                  </>
                ) : null}
                {q.created_at ? ` · ${formatIST(q.created_at)}` : ""}
              </span>
            </div>
            {q.body ? <p>{q.body}</p> : null}
            {q.reply ? (
              <p className="fl-meta">
                <strong>{q.replied_by_name}:</strong> {q.reply}
              </p>
            ) : q.status === "done" ? (
              <p className="fl-meta muted">Done{q.done_by_name ? ` by ${q.done_by_name}` : ""}</p>
            ) : null}
            {q.status === "open" && canEdit ? (
              replyId === q.id ? (
                <form
                  className="fl-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void run(`r${q.id}`, () => replyClientQuestion(elderId, q.id, text.trim()));
                  }}
                >
                  <label className="cp-edit-wide">
                    Reply (the family sees this and gets an email)
                    <textarea rows={3} value={text} required maxLength={4000} onChange={(e) => setText(e.target.value)} />
                  </label>
                  <div className="fl-form-actions">
                    <button type="submit" disabled={busy !== "" || !text.trim()}>
                      {busy === `r${q.id}` ? "Sending…" : "Send reply"}
                    </button>
                    <button type="button" className="cp-linkbtn" onClick={() => setReplyId(null)}>
                      Cancel
                    </button>
                  </div>
                </form>
              ) : (
                <div className="fl-actions">
                  <button type="button" className="cp-linkbtn" onClick={() => setReplyId(q.id)}>
                    Reply
                  </button>
                  <button
                    type="button"
                    className="cp-linkbtn"
                    disabled={busy !== ""}
                    onClick={() => void run(`d${q.id}`, () => markClientQuestionDone(elderId, q.id))}
                  >
                    {busy === `d${q.id}` ? "Saving…" : "Mark done"}
                  </button>
                </div>
              )
            ) : null}
          </li>
        ))}
      </ul>
      {error ? <p className="error-text">{error}</p> : null}
    </section>
  );
}

/** WhatsApp, SMS and calls can't reach someone without a phone number. */
function needsPhone(channel: string): boolean {
  return channel === "whatsapp" || channel === "sms" || channel === "call";
}
