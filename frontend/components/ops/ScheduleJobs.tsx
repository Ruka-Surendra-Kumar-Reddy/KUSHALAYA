"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { isStaleCheckIn, staleLabel } from "@/lib/run-sheet";
import {
  createJob,
  JOB_KIND_LABEL,
  jobWhen,
  listJobs,
  updateJob,
  type CareJob,
  type JobKind,
} from "@/lib/jobs";
import "./schedule-jobs.css";
import { OpsModal } from "./OpsModal";
import { SearchPick } from "./SearchPick";
import { can } from "@/lib/roles";

type Client = { id: number; first_name: string; last_name: string; address?: string | null };
type Caregiver = { id: number; first_name: string; last_name: string };

/**
 * Schedule visits / assessments / installs and see what is booked.
 * Used on the Visits and Assessments pages (fixed `kind`) and the client profile
 * (fixed `elderId`).
 */
export type SchedulePrefill = {
  elder_id?: number;
  kind?: JobKind;
  request_id?: string;
  title?: string;
  tasks?: string;
  date?: string;
  time?: string;
};

export function ScheduleJobs({
  kind,
  elderId,
  title,
  prefill,
  hidePast = false,
  openToken = 0,
  hideAddButton = false,
  formOnly = false,
  onSaved,
}: {
  kind?: JobKind;
  elderId?: number;
  title?: string;
  /** Client Overview: leave out open jobs dated before today (IST) that nobody started. */
  hidePast?: boolean;
  /** Opens the form filled in, e.g. from a family request on the dashboard. */
  prefill?: SchedulePrefill | null;
  /** Bump to open the form from a page-level button (and scroll to it). */
  openToken?: number;
  /** The page has its own "Assign" button; only show "Close" here while the form is open. */
  hideAddButton?: boolean;
  /** Only the "Assign" form (the page lists the jobs itself, e.g. the Assessments board). */
  formOnly?: boolean;
  onSaved?: () => void;
}) {
  const [clients, setClients] = useState<Client[]>([]);
  const [caregivers, setCaregivers] = useState<Caregiver[]>([]);
  const [managers, setManagers] = useState<Caregiver[]>([]);
  const [jobs, setJobs] = useState<CareJob[] | null>(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    elder_id: elderId ? String(elderId) : "",
    kind: kind ?? ("visit" as JobKind),
    date: "",
    time: "10:00",
    caregiver_id: "",
    tasks: "",
    location: "",
  });

  const [fromRequest, setFromRequest] = useState<{ id: string; title?: string } | null>(null);
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!openToken) return;
    setOpen(true);
  }, [openToken]);

  useEffect(() => {
    if (!prefill) return;
    setForm((f) => ({
      ...f,
      elder_id: prefill.elder_id ? String(prefill.elder_id) : f.elder_id,
      kind: prefill.kind ?? f.kind,
      tasks: prefill.tasks ?? f.tasks,
      date: prefill.date ?? f.date,
      time: prefill.time ?? f.time,
    }));
    if (prefill.request_id) setFromRequest({ id: prefill.request_id, title: prefill.title });
    setOpen(true);
  }, [prefill]);

  const load = useCallback(async () => {
    const rows = await listJobs({ elder_id: elderId });
    setJobs(kind ? rows.filter((j) => j.kind === kind) : rows);
  }, [elderId, kind]);

  useEffect(() => {
    load().catch((e) => setError(String(e?.message || e)));
    api<Caregiver[]>("/api/v1/team/caregivers").then(setCaregivers).catch(() => undefined);
    // Home assessments are done by care managers, not caregivers.
    api<Caregiver[]>("/api/v1/team/managers").then(setManagers).catch(() => undefined);
    if (!elderId) api<Client[]>("/api/v1/elders").then(setClients).catch(() => undefined);
  }, [load, elderId]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!form.elder_id || !form.date) {
      setError("Pick a client and a date");
      return;
    }
    setSaving(true);
    try {
      await createJob({
        elder_id: Number(form.elder_id),
        kind: form.kind,
        scheduled_at: new Date(`${form.date}T${form.time || "10:00"}`).toISOString(),
        ...(form.kind === "assessment"
          ? { assignee_user_id: form.caregiver_id ? Number(form.caregiver_id) : null }
          : { caregiver_id: form.caregiver_id ? Number(form.caregiver_id) : null }),
        tasks: form.tasks,
        location: form.location || undefined,
        request_id: fromRequest?.id,
        title: fromRequest?.title,
      });
      setFromRequest(null);
      setOpen(false);
      setForm({ ...form, date: "", tasks: "", location: "", caregiver_id: "" });
      await load();
      onSaved?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not schedule");
    } finally {
      setSaving(false);
    }
  }

  async function cancel(job: CareJob) {
    if (!window.confirm(`Cancel ${job.title} for ${job.elder_name}? The family will be told.`)) return;
    await updateJob(job.id, { status: "cancelled" });
    await load();
  }

  async function reassign(job: CareJob, caregiverId: string) {
    await updateJob(job.id, { caregiver_id: caregiverId ? Number(caregiverId) : null });
    await load();
  }

  const today = new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
  const upcoming = (jobs ?? []).filter(
    (j) =>
      !["completed", "cancelled", "missed"].includes(j.status) &&
      !(
        hidePast &&
        j.status === "scheduled" &&
        j.scheduled_at &&
        new Date(j.scheduled_at).toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" }) < today
      ),
  );
  const past = (jobs ?? []).filter((j) => ["completed", "cancelled", "missed"].includes(j.status)).slice(0, 10);
  const noun = kind ? JOB_KIND_LABEL[kind].toLowerCase() : "visit";

  // View-only staff see the bookings; booking, reassigning and cancelling are for staff who can act.
  const edit = can("edit");
  const formEl = (
        <form className="sj-form" onSubmit={onSubmit}>
          {fromRequest ? (
            <p className="sj-from">
              From a family request{fromRequest.title ? `: ${fromRequest.title}` : ""}. The family is told once you
              schedule it.
            </p>
          ) : null}
          {!elderId ? (
            <SearchPick
              label="Client"
              value={form.elder_id}
              onChange={(v) => setForm({ ...form, elder_id: v })}
              items={clients.map((c) => ({
                value: String(c.id),
                label: `${c.first_name} ${c.last_name}`.trim(),
                hint: c.address || undefined,
              }))}
            />
          ) : null}
          {!kind ? (
            <label>
              Type
              <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as JobKind })}>
                <option value="visit">Care visit</option>
                <option value="assessment">Home safety assessment</option>
                <option value="install">Product installation</option>
              </select>
            </label>
          ) : null}
          <label>
            Date
            <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} required />
          </label>
          <label>
            Time
            <input type="time" value={form.time} onChange={(e) => setForm({ ...form, time: e.target.value })} />
          </label>
          <label>
            {form.kind === "assessment" ? "Care manager" : "Caregiver"}
            <select value={form.caregiver_id} onChange={(e) => setForm({ ...form, caregiver_id: e.target.value })}>
              <option value="">{form.kind === "assessment" ? "Client’s care manager" : "Assign later"}</option>
              {(form.kind === "assessment" ? managers : caregivers).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.first_name} {c.last_name}
                </option>
              ))}
            </select>
          </label>
          <label className="sj-wide">
            Work to do
            <textarea
              rows={2}
              value={form.tasks}
              onChange={(e) => setForm({ ...form, tasks: e.target.value })}
              placeholder={kind === "assessment" ? "Anything to look at closely" : "e.g. Medicines check, walk, physio exercises"}
            />
          </label>
          <label className="sj-wide">
            Location (leave empty to use the client&apos;s address)
            <input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
          </label>
          <div className="sj-actions">
            <button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Schedule and notify family"}
            </button>
          </div>
        </form>
  );
  const formTitle = kind === "assessment" ? "Schedule an assessment" : `Schedule a ${noun}`;
  // Page-level "Schedule" buttons (Assessments) only need the popup, not the list.
  if (formOnly) {
    return (
      <OpsModal open={edit && open} title={formTitle} onClose={() => setOpen(false)} wide>
        {error ? <p className="sj-error">{error}</p> : null}
        {formEl}
      </OpsModal>
    );
  }
  return (
    <section className="sj card" aria-label={title ?? "Schedule"} ref={sectionRef}>
      <div className="sj-head">
        <h2>{title ?? "Scheduled"}</h2>
        {edit && (!hideAddButton || open) ? (
          <button type="button" className={hideAddButton ? "secondary" : undefined} onClick={() => setOpen((v) => !v)}>
            {open ? "Close" : kind === "assessment" ? "Assign an assessment" : `Schedule a ${noun}`}
          </button>
        ) : null}
      </div>

      {error ? <p className="sj-error">{error}</p> : null}

      <OpsModal open={edit && open} title={formTitle} onClose={() => setOpen(false)} wide>
        {formEl}
      </OpsModal>

      {formOnly ? null : jobs === null ? (
        <p className="muted">Loading…</p>
      ) : upcoming.length === 0 ? (
        <p className="sj-empty">Nothing scheduled.</p>
      ) : (
        <ul className="sj-list">
          {upcoming.map((j) => (
            <li key={j.id}>
              <span className="sj-when">{jobWhen(j.scheduled_at)}</span>
              <span className="sj-what">
                {!elderId ? (
                  <Link href={`/kushalaya/customers/${j.elder_id}`}>
                    <strong>{j.elder_name}</strong>
                  </Link>
                ) : null}
                <span>{j.title}</span>
                {j.tasks ? <small>{j.tasks}</small> : null}
              </span>
              {j.kind === "assessment" ? (
                <span className="sj-cg">{j.assignee_name || "Care manager not set"}</span>
              ) : edit ? (
                <select
                  className="sj-cg"
                  value={j.caregiver_id ?? ""}
                  onChange={(e) => reassign(j, e.target.value)}
                  aria-label="Caregiver"
                >
                  <option value="">Not assigned</option>
                  {caregivers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.first_name} {c.last_name}
                    </option>
                  ))}
                </select>
              ) : (
                <span className="sj-cg">{j.caregiver_name || "Not assigned"}</span>
              )}
              <span className={`sj-status is-${j.status}`}>{isStaleCheckIn(j) ? staleLabel(j) : j.status_label}</span>
              {edit && j.status !== "checked_in" ? (
                <button type="button" className="sj-cancel" onClick={() => cancel(j)}>
                  Cancel
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {!formOnly && past.length ? (
        <details className="sj-past">
          <summary>Recent ({past.length})</summary>
          <ul className="sj-list">
            {past.map((j) => (
              <li key={j.id}>
                <span className="sj-when">{jobWhen(j.completed_at ?? j.scheduled_at)}</span>
                <span className="sj-what">
                  {!elderId ? <strong>{j.elder_name}</strong> : null}
                  <span>{j.title}</span>
                  {j.caregiver_note ? <small>{j.caregiver_note}</small> : null}
                </span>
                <span>{j.caregiver_name || "—"}</span>
                <span className={`sj-status is-${j.status}`}>{isStaleCheckIn(j) ? staleLabel(j) : j.status_label}</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}
