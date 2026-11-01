"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatIST } from "@/lib/ist";
import { plural } from "@/lib/run-sheet";

export type CareTeamCaregiver = {
  assignment_id: number;
  caregiver_id: number;
  name: string;
  phone: string | null;
  since: string | null;
  next_visit_at: string | null;
};

export type CareTeam = {
  elder_id: number;
  manager: { id: number; name: string; email: string; phone: string | null } | null;
  caregivers: CareTeamCaregiver[];
  recent_changes: { id: number; what: string; who: string; at: string | null; at_label: string }[];
  can_change_manager: boolean;
  can_edit_caregivers: boolean;
  moved_visits?: number;
  clashes?: { job_id: number; date: string | null; reason: string }[];
};

type Person = { id: number; first_name: string; last_name: string };
type Dialog =
  | { kind: "manager" }
  | { kind: "add" }
  | { kind: "replace"; row: CareTeamCaregiver }
  | { kind: "remove"; row: CareTeamCaregiver }
  | null;

const full = (p: Person) => `${p.first_name} ${p.last_name || ""}`.trim();
const tel = (phone: string) => `tel:${phone.replace(/[^\d+]/g, "")}`;

export function careTeamPath(elderId: number) {
  return `/api/v1/home-safety/clients/${elderId}/care-team`;
}

/** Overview card: care manager + regular caregivers, with Change / Add / Replace / Remove. */
export function CareTeamCard({ elderId, onChanged }: { elderId: number; onChanged?: () => void }) {
  const [team, setTeam] = useState<CareTeam | null>(null);
  const [error, setError] = useState("");
  const [dialog, setDialog] = useState<Dialog>(null);
  const [notice, setNotice] = useState<{ text: string; clashes: CareTeam["clashes"] } | null>(null);

  const load = useCallback(() => {
    api<CareTeam>(careTeamPath(elderId))
      .then((t) => {
        setTeam(t);
        setError("");
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load the care team"));
  }, [elderId]);

  useEffect(load, [load]);

  function done(t: CareTeam, text: string) {
    setTeam(t);
    setDialog(null);
    setNotice({ text, clashes: t.clashes });
    onChanged?.();
  }

  if (!team) {
    return (
      <section className="card ct-card">
        <h2>Care team</h2>
        <p className="muted">{error || "Loading…"}</p>
      </section>
    );
  }

  const m = team.manager;
  return (
    <section className="card ct-card" aria-labelledby="ct-title">
      <h2 id="ct-title">Care team</h2>
      {notice ? (
        <div className="ct-notice" role="status">
          <p>{notice.text}</p>
          {notice.clashes?.length ? (
            <>
              <p>
                <strong>Not moved ({notice.clashes.length}):</strong>
              </p>
              <ul>
                {notice.clashes.map((c, i) => (
                  <li key={`${c.job_id}-${i}`}>
                    {c.date ? `${formatIST(c.date, { dateOnly: true })}: ` : ""}
                    {c.reason}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          <button type="button" className="secondary ct-btn" onClick={() => setNotice(null)}>
            OK
          </button>
        </div>
      ) : null}

      <div className="ct-block">
        <div className="ct-head">
          <h3>Care manager</h3>
          {team.can_change_manager ? (
            <button type="button" className="secondary ct-btn" onClick={() => setDialog({ kind: "manager" })}>
              Change
            </button>
          ) : null}
        </div>
        {m ? (
          <div className="ct-person">
            <strong>{m.name}</strong>
            <span className="ct-contacts">
              {m.phone ? (
                <a className="ct-link" href={tel(m.phone)}>
                  {m.phone}
                </a>
              ) : null}
              <a className="ct-link" href={`mailto:${m.email}`}>
                {m.email}
              </a>
            </span>
          </div>
        ) : (
          <p className="muted">No care manager yet.</p>
        )}
      </div>

      <div className="ct-block">
        <div className="ct-head">
          <h3>Caregivers</h3>
          {team.can_edit_caregivers ? (
            <button type="button" className="secondary ct-btn" onClick={() => setDialog({ kind: "add" })}>
              Add
            </button>
          ) : null}
        </div>
        {team.caregivers.length ? (
          <ul className="ct-list">
            {team.caregivers.map((c) => (
              <li key={c.assignment_id} className="ct-person">
                <strong>{c.name}</strong>
                <span className="ct-contacts">
                  {c.phone ? (
                    <a className="ct-link" href={tel(c.phone)}>
                      {c.phone}
                    </a>
                  ) : null}
                  <span className="muted">Since {c.since ? formatIST(c.since, { dateOnly: true }) : "—"}</span>
                  <span className="muted">
                    Next visit: {c.next_visit_at ? formatIST(c.next_visit_at) : "none booked"}
                  </span>
                </span>
                {team.can_edit_caregivers ? (
                  <span className="ct-actions">
                    <button type="button" className="secondary ct-btn" onClick={() => setDialog({ kind: "replace", row: c })}>
                      Replace
                    </button>
                    <button type="button" className="secondary ct-btn" onClick={() => setDialog({ kind: "remove", row: c })}>
                      Remove
                    </button>
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No regular caregiver yet.</p>
        )}
      </div>

      <details className="ct-block ct-recent">
        <summary>Recent changes ({team.recent_changes.length})</summary>
        {team.recent_changes.length ? (
          <ul className="ct-list">
            {team.recent_changes.map((r) => (
              <li key={r.id}>
                <span>{r.what}</span>
                <small className="muted">
                  {r.who} · {r.at_label} IST
                </small>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No changes yet.</p>
        )}
      </details>

      {dialog ? (
        <CareTeamDialog
          elderId={elderId}
          dialog={dialog}
          currentManagerId={m?.id ?? null}
          onClose={() => setDialog(null)}
          onDone={done}
        />
      ) : null}
    </section>
  );
}

function CareTeamDialog({
  elderId,
  dialog,
  currentManagerId,
  onClose,
  onDone,
}: {
  elderId: number;
  dialog: NonNullable<Dialog>;
  currentManagerId: number | null;
  onClose: () => void;
  onDone: (t: CareTeam, text: string) => void;
}) {
  const [people, setPeople] = useState<Person[]>([]);
  const [pick, setPick] = useState("");
  const [note, setNote] = useState("");
  const [move, setMove] = useState<"yes" | "no">("yes");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (dialog.kind === "remove") return;
    const url = dialog.kind === "manager" ? "/api/v1/team/managers" : "/api/v1/team/caregivers";
    api<Person[]>(url)
      .then(setPeople)
      .catch(() => setError("Could not load the list"));
  }, [dialog.kind]);

  const base = careTeamPath(elderId);
  const choices = people.filter((p) =>
    dialog.kind === "manager" ? p.id !== currentManagerId : dialog.kind === "replace" ? p.id !== dialog.row.caregiver_id : true,
  );
  const picked = choices.find((p) => String(p.id) === pick);
  const title =
    dialog.kind === "manager"
      ? "Change care manager"
      : dialog.kind === "add"
        ? "Add caregiver"
        : dialog.kind === "replace"
          ? `Replace ${dialog.row.name}`
          : `Remove ${dialog.row.name}?`;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (dialog.kind === "manager") {
        const t = await api<CareTeam>(`${base}/manager`, {
          method: "PUT",
          body: JSON.stringify({ manager_user_id: Number(pick), note: note.trim() || null }),
        });
        onDone(t, `${picked ? full(picked) : "The new manager"} is now the care manager. They have the handover note.`);
      } else if (dialog.kind === "add") {
        const t = await api<CareTeam>(`${base}/caregivers`, {
          method: "POST",
          body: JSON.stringify({ caregiver_id: Number(pick) }),
        });
        onDone(t, `${picked ? full(picked) : "Caregiver"} added to the care team.`);
      } else if (dialog.kind === "replace") {
        const t = await api<CareTeam>(`${base}/caregivers/${dialog.row.assignment_id}/replace`, {
          method: "POST",
          body: JSON.stringify({ caregiver_id: Number(pick), move_visits: move === "yes" }),
        });
        const who = picked ? full(picked) : "the new caregiver";
        onDone(
          t,
          move === "yes"
            ? `${dialog.row.name} replaced by ${who}. ${plural(t.moved_visits ?? 0, "upcoming visit")} moved. The family has been told.`
            : `${dialog.row.name} replaced by ${who}. Visits not changed. The family has been told.`,
        );
      } else {
        const t = await api<CareTeam>(`${base}/caregivers/${dialog.row.assignment_id}`, { method: "DELETE" });
        onDone(t, `${dialog.row.name} removed from the care team. Past visits are kept.`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
      setBusy(false);
    }
  }

  return (
    <div className="home-safety-showcase-modal-backdrop" role="presentation" onClick={onClose}>
      <form
        className="home-safety-showcase-modal card ct-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
      >
        <h2>{title}</h2>
        {dialog.kind === "remove" ? (
          <p>They stop being a regular caregiver for this client. Visit history is kept; booked visits are not changed.</p>
        ) : (
          <label className="ct-field">
            {dialog.kind === "manager" ? "New care manager" : "Caregiver"}
            <select value={pick} onChange={(e) => setPick(e.target.value)} required>
              <option value="">Choose…</option>
              {choices.map((p) => (
                <option key={p.id} value={p.id}>
                  {full(p)}
                </option>
              ))}
            </select>
          </label>
        )}
        {dialog.kind === "manager" ? (
          <label className="ct-field">
            Handover note (optional)
            <textarea rows={3} value={note} maxLength={4000} onChange={(e) => setNote(e.target.value)} />
          </label>
        ) : null}
        {dialog.kind === "replace" ? (
          <fieldset className="ct-field">
            <legend>
              Also move upcoming visits and repeating visits to {picked ? full(picked) : "the new caregiver"}?
            </legend>
            <label className="ct-radio">
              <input type="radio" name="move" checked={move === "yes"} onChange={() => setMove("yes")} /> Yes, move them
            </label>
            <label className="ct-radio">
              <input type="radio" name="move" checked={move === "no"} onChange={() => setMove("no")} /> No, only change
              the regular caregiver
            </label>
          </fieldset>
        ) : null}
        {error ? (
          <p className="error" role="alert">
            {error}
          </p>
        ) : null}
        <div className="ct-dialog-actions">
          <button type="button" className="secondary ct-btn" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button
            type="submit"
            className={dialog.kind === "remove" ? "danger ct-btn" : "ct-btn"}
            disabled={busy || (dialog.kind !== "remove" && !pick)}
          >
            {busy ? "Saving…" : dialog.kind === "remove" ? "Remove" : "Save"}
          </button>
        </div>
      </form>
    </div>
  );
}
