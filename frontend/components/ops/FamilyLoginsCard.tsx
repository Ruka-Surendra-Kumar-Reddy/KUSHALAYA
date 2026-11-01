"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  addFamilyLogin,
  fetchFamilyLogins,
  generatePassword,
  resetFamilyPassword,
  setFamilyLoginActive,
  type FamilyLogin,
} from "@/lib/livewell/clientProfileApi";
import { can } from "@/lib/roles";
import { OpsModal } from "./OpsModal";

const RELATIONS = ["son", "daughter", "spouse", "family"] as const;
const REL_LABEL: Record<string, string> = { son: "Son", daughter: "Daughter", spouse: "Spouse", family: "Family" };

function lastSeen(f: FamilyLogin) {
  if (!f.last_seen_at) return "Never signed in";
  const days = Math.floor((Date.now() - new Date(f.last_seen_at).getTime()) / 86400000);
  return `Last seen ${days <= 0 ? "today" : days === 1 ? "yesterday" : `${days} days ago`}`;
}

/** Password box with Show/Hide and Generate. */
function PasswordInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [show, setShow] = useState(false);
  const [copied, setCopied] = useState(false);
  return (
    <span className="fl-pass">
      <input
        type={show ? "text" : "password"}
        value={value}
        minLength={8}
        required
        autoComplete="new-password"
        onChange={(e) => onChange(e.target.value)}
        aria-label="Password"
      />
      <button type="button" className="cp-linkbtn" onClick={() => setShow((s) => !s)}>
        {show ? "Hide" : "Show"}
      </button>
      <button
        type="button"
        className="cp-linkbtn"
        onClick={() => {
          onChange(generatePassword());
          setShow(true);
          setCopied(false);
        }}
      >
        Generate
      </button>
      {value ? (
        <button
          type="button"
          className="cp-linkbtn"
          onClick={() =>
            void navigator.clipboard
              ?.writeText(value)
              .then(() => setCopied(true))
              .catch(() => setCopied(false))
          }
        >
          {copied ? "Copied" : "Copy"}
        </button>
      ) : null}
    </span>
  );
}

const EMPTY = { name: "", relationship: "son", email: "", password: "" };

/** Overview → Family: who signs in to the family site, with add / reset / deactivate inline. */
export function FamilyLoginsCard({ elderId, primaryIds }: { elderId: number; primaryIds: number[] }) {
  const [logins, setLogins] = useState<FamilyLogin[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [resetId, setResetId] = useState<number | null>(null);
  const [newPass, setNewPass] = useState("");
  const [confirmOff, setConfirmOff] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(
    () => fetchFamilyLogins(elderId).then(setLogins).catch(() => setLogins([])),
    [elderId],
  );
  useEffect(() => {
    void load().then(() => {
      // Clients list links here as …/customers/{id}#family.
      if (window.location.hash === "#family") document.getElementById("family")?.scrollIntoView({ block: "start" });
    });
  }, [load]);

  async function run(action: () => Promise<unknown>, ok: string) {
    setBusy(true);
    setNote(null);
    try {
      await action();
      setNote({ ok: true, text: ok });
      await load();
      return true;
    } catch (err) {
      setNote({ ok: false, text: err instanceof Error ? err.message : "Could not save" });
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function add(e: FormEvent) {
    e.preventDefault();
    const email = form.email.trim().toLowerCase();
    const done = await run(
      () => addFamilyLogin(elderId, { ...form, email }),
      `Login created. They sign in at family.kushalaya.com with ${email} and the password you set.`,
    );
    if (done) {
      setForm(EMPTY);
      setAdding(false);
    }
  }

  async function reset(e: FormEvent, f: FamilyLogin) {
    e.preventDefault();
    const done = await run(
      () => resetFamilyPassword(elderId, f.id, newPass),
      `Password changed for ${f.email}. Share it with them privately.`,
    );
    if (done) {
      setResetId(null);
      setNewPass("");
    }
  }

  const canEdit = can("edit");
  return (
    <section className="card fl" id="family">
      <div className="cp-card-head">
        <h2>Family</h2>
        {canEdit && !adding ? (
          <button type="button" className="cp-linkbtn" onClick={() => setAdding(true)}>
            + Add family member
          </button>
        ) : null}
      </div>
      {logins === null ? <p className="muted">Loading…</p> : null}
      {logins && logins.length === 0 && !adding ? (
        <p className="muted">
          No family logins yet.
          {canEdit ? (
            <>
              {" "}
              <button type="button" className="cp-linkbtn" onClick={() => setAdding(true)}>
                Add a family member
              </button>
            </>
          ) : null}
        </p>
      ) : null}
      <ul className="fl-list">
        {(logins ?? []).map((f) => (
          <li key={f.id} className={f.active ? "" : "is-off"}>
            <div className="fl-who">
              <strong>{f.name || f.email}</strong>
              <span className="muted"> {REL_LABEL[f.relationship] ?? f.relationship}</span>
              {primaryIds.includes(f.id) ? <span className="cp-pill cp-pill-completed">Primary</span> : null}
              {!f.active ? <span className="cp-pill cp-pill-cancelled">Deactivated</span> : null}
            </div>
            <div className="muted fl-meta">
              {f.email} · {lastSeen(f)}
            </div>
            {canEdit ? (
            <div className="fl-actions">
              <button
                type="button"
                className="cp-linkbtn"
                onClick={() => {
                  setResetId(resetId === f.id ? null : f.id);
                  setNewPass("");
                }}
              >
                Reset password
              </button>
              <button
                type="button"
                className="cp-linkbtn"
                disabled={busy}
                onClick={() =>
                  f.active
                    ? setConfirmOff(f.id)
                    : void run(() => setFamilyLoginActive(elderId, f.id, true), `${f.email} can sign in again.`)
                }
              >
                {f.active ? "Deactivate" : "Reactivate"}
              </button>
            </div>
            ) : null}
            {confirmOff === f.id ? (
              <div className="fl-confirm" role="alert">
                <span>{(f.name || f.email).split(" ")[0]} will be signed out and can&apos;t sign in. Continue?</span>
                <button
                  type="button"
                  className="danger"
                  disabled={busy}
                  onClick={() =>
                    void run(() => setFamilyLoginActive(elderId, f.id, false), `${f.email} can no longer sign in.`).then(
                      () => setConfirmOff(null),
                    )
                  }
                >
                  Deactivate
                </button>
                <button type="button" className="secondary" onClick={() => setConfirmOff(null)}>
                  Cancel
                </button>
              </div>
            ) : null}
            {resetId === f.id ? (
              <form className="fl-form fl-inline" onSubmit={(e) => void reset(e, f)}>
                <label>
                  New password (at least 8 characters)
                  <PasswordInput value={newPass} onChange={setNewPass} />
                </label>
                <button type="submit" className="primary" disabled={busy}>
                  Save password
                </button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    setResetId(null);
                    setNewPass("");
                  }}
                >
                  Cancel
                </button>
              </form>
            ) : null}
          </li>
        ))}
      </ul>
      <OpsModal open={adding} title="Add family member" onClose={() => { setAdding(false); setForm(EMPTY); }}>
        <form className="fl-form" onSubmit={(e) => void add(e)}>
          {note && !note.ok ? <p className="ks-modal-error" role="alert">{note.text}</p> : null}
          <label>
            Name
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Ravi Rao" />
          </label>
          <label>
            Relationship
            <select value={form.relationship} onChange={(e) => setForm({ ...form, relationship: e.target.value })}>
              {RELATIONS.map((r) => (
                <option key={r} value={r}>
                  {REL_LABEL[r]}
                </option>
              ))}
            </select>
          </label>
          <label>
            Email (their username)
            <input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </label>
          <label>
            Password (at least 8 characters)
            <PasswordInput value={form.password} onChange={(password) => setForm({ ...form, password })} />
          </label>
          <div className="fl-form-actions">
            <button type="submit" className="primary" disabled={busy}>
              {busy ? "Adding…" : "Add family member"}
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setAdding(false);
                setForm(EMPTY);
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      </OpsModal>
      {note ? <p className={note.ok ? "cp-ok" : "error-text"}>{note.text}</p> : null}
    </section>
  );
}
