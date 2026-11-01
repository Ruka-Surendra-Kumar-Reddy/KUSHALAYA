"use client";

import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { BackLink, PageActions } from "@/components/ops/PageActions";
import { Flash } from "@/components/Flash";
import { OpsModal } from "@/components/ops/OpsModal";
import { api } from "@/lib/api";
import { jobWhen, type CareJob } from "@/lib/jobs";
import {
  addLeave,
  affectedVisits,
  approveLeave,
  findCover,
  istToday,
  LEAVE_STATUS_LABEL,
  LEAVE_TYPES,
  listLeave,
  reassign,
  rejectLeave,
  shortDay,
  type CoverSuggestion,
  type Leave,
} from "@/lib/schedule";
import "@/components/ops/schedule.css";
import "@/components/ops/roster.css";

type Person = { id: number; first_name: string; last_name: string };

const TYPE_LABEL = Object.fromEntries(LEAVE_TYPES.map((t) => [t.id, t.label]));

const needCover = (n: number) => `${n} visit${n === 1 ? " needs" : "s need"} cover`;

const EMPTY = { caregiver_id: "", leave_type: "ANNUAL", start_date: "", end_date: "", reason: "", approve: true };

export default function LeavePage() {
  const [rows, setRows] = useState<Leave[] | null>(null);
  const [caregivers, setCaregivers] = useState<Person[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [active, setActive] = useState<Leave | null>(null);
  const [visits, setVisits] = useState<CareJob[]>([]);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [cover, setCover] = useState<Record<number, CoverSuggestion[]>>({});
  const [target, setTarget] = useState("");
  const [failed, setFailed] = useState<{ job_id: number; reason: string }[]>([]);
  // Caregiver of the last move (a cover chip or the bulk picker), for "Book anyway".
  const [lastTo, setLastTo] = useState<number | null>(null);
  const [moveError, setMoveError] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      setRows(await listLeave());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load leave");
    }
  }, []);

  useEffect(() => {
    void load();
    api<Person[]>("/api/v1/team/caregivers").then(setCaregivers).catch(() => undefined);
  }, [load]);

  function showAffected(leave: Leave, list: CareJob[]) {
    setActive(leave);
    setVisits(list);
    setPicked(new Set(list.map((v) => v.id)));
    setCover({});
    setFailed([]);
    setTarget("");
    setLastTo(null);
    setMoveError("");
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const out = await addLeave({
        caregiver_id: Number(form.caregiver_id),
        leave_type: form.leave_type,
        start_date: form.start_date,
        end_date: form.end_date || form.start_date,
        reason: form.reason || undefined,
        approve: form.approve,
      });
      setForm(EMPTY);
      setOpen(false);
      setMessage(form.approve ? `Leave approved. ${needCover(out.affected.length)}.` : "Leave recorded — waiting for approval.");
      if (form.approve) showAffected(out.leave, out.affected);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the leave");
    } finally {
      setSaving(false);
    }
  }

  async function approve(l: Leave) {
    try {
      const out = await approveLeave(l.id);
      setMessage(`Leave approved. ${needCover(out.affected.length)}.`);
      showAffected(out.leave, out.affected);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not approve");
    }
  }

  async function reject(l: Leave) {
    const reason = window.prompt(`Reason for not approving ${l.caregiver_name}'s leave (optional):`, "");
    if (reason === null) return;
    try {
      await rejectLeave(l.id, reason || undefined);
      setMessage("Leave not approved — the caregiver will see it in the app.");
      if (active?.id === l.id) setActive(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update");
    }
  }

  async function open_(l: Leave) {
    try {
      showAffected(l, await affectedVisits(l.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load visits");
    }
  }

  async function suggest(job: CareJob) {
    try {
      const out = await findCover(job.id);
      setCover((c) => ({ ...c, [job.id]: out.suggestions }));
      if (!out.suggestions.length) setMessage(`No one is free for ${job.elder_name} on ${jobWhen(job.scheduled_at)}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not find cover");
    }
  }

  async function move(jobIds: number[], caregiverId: number | null, force = false) {
    setLastTo(caregiverId);
    setMoveError("");
    try {
      const out = await reassign(jobIds, caregiverId, force);
      setFailed(out.failed);
      const moved = new Set(out.moved.map((j) => j.id));
      setVisits((v) => v.filter((j) => !moved.has(j.id)));
      setPicked((p) => new Set([...p].filter((id) => !moved.has(id))));
      const n = out.moved.length;
      if (n) {
        setMessage(
          `${n} visit${n === 1 ? "" : "s"} reassigned — families told.` +
            (out.failed.length ? ` ${out.failed.length} could not move (see below).` : ""),
        );
      } else {
        setMessage("");
      }
      await load();
    } catch (err) {
      setFailed([]);
      setMoveError(err instanceof Error ? err.message : "Could not reassign");
    }
  }

  const set = (k: keyof typeof EMPTY) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });
  const visitName = (id: number) => {
    const v = visits.find((j) => j.id === id);
    return v ? `${v.elder_name}, ${jobWhen(v.scheduled_at)}` : `Visit ${id}`;
  };

  return (
    <>
      <p className="ks-back-row">
        <BackLink href="/kushalaya/visits" label="Visits" />
      </p>
      <PageHeader title="Leave and cover" subtitle="Caregiver leave, the visits it affects, and who can cover" />
      <Flash error={error} message={message} onClear={() => { setError(""); setMessage(""); }} />

      <PageActions>
        <button type="button" onClick={() => setOpen(true)}>
          + Add leave
        </button>
      </PageActions>

      <OpsModal open={open} title="Add leave" onClose={() => setOpen(false)}>
        <form className="sc-form" onSubmit={save}>
          {error ? <p className="ks-modal-error sc-wide" role="alert">{error}</p> : null}
          <label>
            Caregiver
            <select value={form.caregiver_id} onChange={set("caregiver_id")} required>
              <option value="">Choose…</option>
              {caregivers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.first_name} {c.last_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Type
            <select value={form.leave_type} onChange={set("leave_type")}>
              {LEAVE_TYPES.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            From
            <input type="date" value={form.start_date} min={istToday()} onChange={set("start_date")} required />
          </label>
          <label>
            To
            <input type="date" value={form.end_date} min={form.start_date || istToday()} onChange={set("end_date")} />
          </label>
          <label className="sc-wide">
            Reason
            <input value={form.reason} onChange={set("reason")} placeholder="Optional" />
          </label>
          <label className="sc-wide">
            <span>
              <input type="checkbox" checked={form.approve} onChange={(e) => setForm({ ...form, approve: e.target.checked })} />{" "}
              Approve now
            </span>
          </label>
          <div className="sc-form-actions">
            <button type="button" className="secondary" disabled={saving} onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save leave"}
            </button>
          </div>
        </form>
      </OpsModal>

      {active ? (
        <section className="card rs-affected">
          <h3>
            {active.caregiver_name} · {shortDay(active.start_date)} – {shortDay(active.end_date)}:{" "}
            {visits.length ? `${visits.length} visit${visits.length === 1 ? "" : "s"} to cover` : "all visits covered"}
          </h3>
          {visits.length ? (
            <>
              <ul className="rs-list">
                {visits.map((v) => (
                  <li key={v.id} className="rs-visit">
                    <label className="rs-visit-pick">
                    <input
                      type="checkbox"
                      aria-label={`Select ${v.elder_name}`}
                      checked={picked.has(v.id)}
                      onChange={() =>
                        setPicked((p) => {
                          const n = new Set(p);
                          if (n.has(v.id)) n.delete(v.id);
                          else n.add(v.id);
                          return n;
                        })
                      }
                    />
                    </label>
                    <span>
                      <strong>{v.elder_name}</strong> · {jobWhen(v.scheduled_at)} · {v.title}
                    </span>
                    <button type="button" className="sc-step" onClick={() => void suggest(v)}>
                      Find cover
                    </button>
                    {cover[v.id] ? (
                      <div className="rs-suggest">
                        {cover[v.id].length === 0 ? (
                          <small>No one is free then.</small>
                        ) : (
                          cover[v.id].map((s) => (
                            <button key={s.caregiver_id} type="button" className="sc-step is-go" onClick={() => void move([v.id], s.caregiver_id)}>
                              {s.name}
                              {s.same_team ? " · team" : ""}
                              {s.knows_client ? " · knows client" : ""}
                              {` · ${s.visits_that_day} that day`}
                            </button>
                          ))
                        )}
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
              <div className="rs-bulk">
                <label>
                  Give selected ({picked.size}) to
                  <select value={target} onChange={(e) => setTarget(e.target.value)}>
                    <option value="">Choose…</option>
                    {caregivers
                      .filter((c) => c.id !== active.caregiver_id)
                      .map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.first_name} {c.last_name}
                        </option>
                      ))}
                  </select>
                </label>
                <button type="button" disabled={!target || !picked.size} onClick={() => void move([...picked], Number(target))}>
                  Reassign
                </button>
              </div>
            </>
          ) : null}
          {moveError ? (
            <p className="sc-clash" role="alert">
              {moveError}
            </p>
          ) : null}
          {failed.length ? (
            <div className="sc-clash" role="alert">
              <p style={{ margin: 0 }}>
                {failed.length === 1 ? "This visit was not moved:" : `These ${failed.length} visits were not moved:`}
              </p>
              <ul>
                {failed.map((f) => (
                  <li key={f.job_id}>
                    {visitName(f.job_id)}: {f.reason}
                  </li>
                ))}
              </ul>
              {lastTo ? (
                <button type="button" className="sc-step" onClick={() => void move(failed.map((f) => f.job_id), lastTo, true)}>
                  Book anyway
                </button>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="card rs-series">
        <h3>Leave</h3>
        {rows === null ? (
          <p className="sc-empty">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="sc-empty">No leave recorded.</p>
        ) : (
          <ul>
            {rows.map((l) => (
              <li key={l.id}>
                <span>
                  <strong>{l.caregiver_name}</strong> · {shortDay(l.start_date)}
                  {l.end_date !== l.start_date ? ` – ${shortDay(l.end_date)}` : ""} · {TYPE_LABEL[l.leave_type] ?? l.leave_type}{" "}
                  <span className={`rs-badge is-${l.status.toLowerCase()}`}>{LEAVE_STATUS_LABEL[l.status]}</span>
                  {l.affected_count && l.status !== "REJECTED" && l.status !== "CANCELLED" ? (
                    <em className="rs-warn"> · {needCover(l.affected_count)}</em>
                  ) : null}
                  {l.reason ? <small> — {l.reason}</small> : null}
                  {l.status === "REJECTED" && l.resolution_note ? (
                    <small className="rs-note"> · Reason not approved: {l.resolution_note}</small>
                  ) : null}
                </span>
                <span className="rs-actions">
                  {l.status === "PENDING" ? (
                    <>
                      <button type="button" className="sc-step is-go" onClick={() => void approve(l)}>
                        Approve
                      </button>
                      <button type="button" className="sc-text is-danger" onClick={() => void reject(l)}>
                        Don’t approve
                      </button>
                    </>
                  ) : null}
                  {l.status === "APPROVED" && l.affected_count ? (
                    <button type="button" className="sc-step" onClick={() => void open_(l)}>
                      Find cover
                    </button>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
