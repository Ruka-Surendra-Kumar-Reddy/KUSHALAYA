"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { BackLink, PageActions } from "@/components/ops/PageActions";
import { Directions } from "@/components/Directions";
import { Flash } from "@/components/Flash";
import { OpsModal } from "@/components/ops/OpsModal";
import { api } from "@/lib/api";
import { isClash } from "@/lib/jobs";
import {
  addDays,
  changeSeries,
  createSeries,
  endSeries,
  getRoster,
  istToday,
  listSeries,
  shortDay,
  time12Range,
  WEEKDAYS,
  type CareSeries,
  type Roster,
  type RosterChip,
  type RosterRow,
  type SeriesClash,
} from "@/lib/schedule";
import "@/components/ops/schedule.css";
import "@/components/ops/roster.css";

type Person = { id: number; first_name: string; last_name: string; address?: string | null };

const EMPTY = {
  elder_id: "",
  caregiver_id: "",
  weekdays: [0, 2, 4] as number[],
  time: "10:00",
  duration: "60",
  start_date: "",
  until: "date" as "date" | "weeks" | "open",
  end_date: "",
  weeks: "4",
  tasks: "",
};

function mondayOf(ymd: string) {
  const d = new Date(`${ymd}T00:00:00Z`);
  return addDays(ymd, -((d.getUTCDay() + 6) % 7));
}

const CLOSED = new Set(["completed", "cancelled", "missed"]);

/** Done or already in the past: read-only on the roster. */
function isPast(c: RosterChip) {
  return CLOSED.has(c.status) || new Date(c.scheduled_at).getTime() < Date.now();
}

function visitHref(c: RosterChip) {
  return `/kushalaya/visits?job=${c.id}&range=${isPast(c) ? "past" : "upcoming"}`;
}

/** ISO instant -> YYYY-MM-DD in India. */
function istYmd(iso: string) {
  return new Date(new Date(iso).getTime() + 5.5 * 3600000).toISOString().slice(0, 10);
}

function clashText(c: SeriesClash) {
  return `${shortDay(c.date)}: ${c.reason}`;
}

export default function RosterPage() {
  const [week, setWeek] = useState(() => mondayOf(istToday()));
  const [roster, setRoster] = useState<Roster | null>(null);
  const [series, setSeries] = useState<CareSeries[]>([]);
  const [clients, setClients] = useState<Person[]>([]);
  const [caregivers, setCaregivers] = useState<Person[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [clashes, setClashes] = useState<SeriesClash[]>([]);
  const [editing, setEditing] = useState<{ chip: RosterChip; time: string; caregiver_id: string; days: number[] } | null>(null);
  const [editClash, setEditClash] = useState("");
  const [editError, setEditError] = useState("");
  const [editScope, setEditScope] = useState<"one" | "following">("one");
  const [formError, setFormError] = useState("");
  const [ending, setEnding] = useState<{ id: number; date: string; error: string } | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  // Phone: one caregiver and one day at a time.
  const [phoneCg, setPhoneCg] = useState<string>("");
  // Opens on today when the week shown is this week (Monday-based index), else Monday.
  const todayIdx = (w: string) => {
    const i = Math.round((Date.parse(`${istToday()}T12:00:00Z`) - Date.parse(`${w}T12:00:00Z`)) / 86400000);
    return i >= 0 && i < 7 ? i : 0;
  };
  const [phoneDay, setPhoneDay] = useState(() => todayIdx(mondayOf(istToday())));
  useEffect(() => {
    setPhoneDay(todayIdx(week));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [week]);

  const load = useCallback(async () => {
    try {
      const [r, s] = await Promise.all([getRoster(week), listSeries()]);
      setRoster(r);
      setSeries(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load the roster");
    }
  }, [week]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    api<Person[]>("/api/v1/team/clients").then(setClients).catch(() => undefined);
    api<Person[]>("/api/v1/team/caregivers").then(setCaregivers).catch(() => undefined);
  }, []);

  const rows: RosterRow[] = useMemo(
    () => (roster ? [...roster.caregivers, ...(roster.unassigned ? [roster.unassigned] : [])] : []),
    [roster],
  );
  // Phone picker always offers "Not assigned", even in a week with no unassigned visits.
  const phoneRows: RosterRow[] = useMemo(
    () =>
      roster && !roster.unassigned
        ? [
            ...rows,
            {
              caregiver_id: null,
              name: "Not assigned",
              other_team: false,
              active: true,
              days: roster.days.map((d) => ({ date: d.date, visits: [], leave: null })),
            } as RosterRow,
          ]
        : rows,
    [roster, rows],
  );
  const phoneRow = phoneRows.find((r) => String(r.caregiver_id ?? "none") === phoneCg) ?? phoneRows[0];
  const seriesById = useMemo(() => new Map(series.map((s) => [s.id, s])), [series]);

  function toggleDay(d: number, list: number[]) {
    return list.includes(d) ? list.filter((x) => x !== d) : [...list, d].sort();
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form.weekdays.length) {
      setError("Pick at least one day of the week");
      return;
    }
    setSaving(true);
    setError("");
    setFormError("");
    try {
      const out = await createSeries({
        elder_id: Number(form.elder_id),
        caregiver_id: form.caregiver_id ? Number(form.caregiver_id) : null,
        weekdays: form.weekdays,
        time: form.time,
        duration_minutes: Number(form.duration) || 60,
        start_date: form.start_date || undefined,
        end_date: form.until === "date" && form.end_date ? form.end_date : undefined,
        weeks: form.until === "weeks" ? Number(form.weeks) : undefined,
        tasks: form.tasks || undefined,
      });
      setClashes(out.clashes);
      setMessage(
        `${out.created} visits booked (${out.series.summary}). The family has been told.` +
          (out.clashes.length ? ` ${out.clashes.length} need another caregiver — see below.` : ""),
      );
      setForm(EMPTY);
      setOpen(false);
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not book the repeating visits");
    } finally {
      setSaving(false);
    }
  }

  function startEdit(chip: RosterChip) {
    const s = chip.series_id ? seriesById.get(chip.series_id) : undefined;
    setEditClash("");
    setEditError("");
    setEditing({
      chip,
      time: chip.start,
      caregiver_id: chip.caregiver_id ? String(chip.caregiver_id) : "",
      days: s?.weekdays ?? [],
    });
  }

  async function applyEdit(scope: "one" | "following", force = false) {
    if (!editing?.chip.series_id) return;
    const s = seriesById.get(editing.chip.series_id);
    const body = {
      job_id: editing.chip.id,
      scope,
      time: editing.time,
      caregiver_id: editing.caregiver_id ? Number(editing.caregiver_id) : null,
      force,
      ...(scope === "following" && s && editing.days.join() !== s.weekdays.join() ? { weekdays: editing.days } : {}),
    };
    setEditScope(scope);
    setEditClash("");
    setEditError("");
    try {
      const out = await changeSeries(editing.chip.series_id, body);
      setEditing(null);
      if (scope === "following") {
        setClashes(out.clashes ?? []);
        const kept = (out.kept ?? []).map((j) => (j.scheduled_at ? shortDay(istYmd(j.scheduled_at)) : "")).filter(Boolean);
        setMessage(
          `This and following visits changed: ${out.series.summary}. The family has been told.` +
            (kept.length ? ` Kept your one-off change on ${kept.join(", ")}.` : ""),
        );
      } else {
        setMessage("This visit changed — the family has been told.");
      }
      await load();
    } catch (err) {
      if (isClash(err)) setEditClash(err.message);
      else setEditError(err instanceof Error ? err.message : "Could not change the visit");
    }
  }

  async function stop(s: CareSeries, fromToday: boolean) {
    if (!ending) return;
    try {
      const out = await endSeries(s.id, fromToday ? undefined : ending.date || undefined);
      setEnding(null);
      setMessage(`Repeating visits ended: ${out.removed} upcoming visits removed. The family has been told.`);
      await load();
    } catch (err) {
      setEnding({ ...ending, error: err instanceof Error ? err.message : "Could not end the repeating visits" });
    }
  }

  const chipBody = (c: RosterChip) => (
    <>
      <strong>{time12Range(c.start, c.end)}</strong>
      <span>{c.elder_name}</span>
      {c.needs_cover ? <em className="rs-cover">Needs cover</em> : null}
      {c.series_id ? <small aria-label="repeating">↻</small> : null}
    </>
  );

  // Upcoming repeating visits open the change card; one-off and past visits link to Schedule.
  const chip = (c: RosterChip) =>
    c.series_id && !isPast(c) ? (
      <button
        key={c.id}
        type="button"
        className={`rs-chip is-${c.status} is-series`}
        onClick={() => startEdit(c)}
        title="Repeating visit — click to change"
      >
        {chipBody(c)}
      </button>
    ) : (
      <Link
        key={c.id}
        href={visitHref(c)}
        className={`rs-chip is-${c.status} is-link${c.series_id ? " is-series" : ""}`}
        title={isPast(c) ? `${c.title} — view on Schedule` : `${c.title} — open on Schedule`}
      >
        {chipBody(c)}
      </Link>
    );

  const cell = (row: RosterRow, i: number) => {
    const d = row.days[i];
    return (
      <div className={`rs-cell${d.leave ? ` is-leave is-${d.leave.status.toLowerCase()}` : ""}`}>
        {d.leave ? <span className="rs-leave">{d.leave.status === "APPROVED" ? "On leave" : "Leave asked"}</span> : null}
        {d.visits.map(chip)}
      </div>
    );
  };

  const set = (k: keyof typeof EMPTY) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  return (
    <>
      <p className="ks-back-row">
        <BackLink href="/kushalaya/visits" label="Visits" />
      </p>
      <PageHeader title="Weekly roster" subtitle="Who is where, every day — and repeating visits" />
      <Flash error={error} message={message} onClear={() => { setError(""); setMessage(""); }} />

      <PageActions>
        <button type="button" onClick={() => setOpen(true)}>
          + Repeating visit
        </button>
      </PageActions>

      <OpsModal open={open} title="Repeating visit" onClose={() => setOpen(false)} wide>
        <form className="sc-form" onSubmit={save}>
          {error ? <p className="ks-modal-error sc-wide" role="alert">{error}</p> : null}
          <label>
            Client
            <select value={form.elder_id} onChange={set("elder_id")} required>
              <option value="">Choose…</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.first_name} {c.last_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Caregiver
            <select value={form.caregiver_id} onChange={set("caregiver_id")}>
              <option value="">Assign later</option>
              {caregivers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.first_name} {c.last_name}
                </option>
              ))}
            </select>
          </label>
          <fieldset className="sc-wide rs-days">
            <legend>Days</legend>
            {WEEKDAYS.map((d, i) => (
              <button
                key={d}
                type="button"
                aria-pressed={form.weekdays.includes(i)}
                className={form.weekdays.includes(i) ? "is-on" : ""}
                onClick={() => setForm({ ...form, weekdays: toggleDay(i, form.weekdays) })}
              >
                {d}
              </button>
            ))}
          </fieldset>
          <label>
            Time (IST)
            <input type="time" value={form.time} onChange={set("time")} required />
          </label>
          <label>
            Minutes
            <input type="number" min={15} max={720} step={15} value={form.duration} onChange={set("duration")} />
          </label>
          <label>
            First day
            <input type="date" value={form.start_date} min={istToday()} onChange={set("start_date")} />
          </label>
          <label>
            Until
            <select value={form.until} onChange={(e) => setForm({ ...form, until: e.target.value as typeof form.until })}>
              <option value="date">A date</option>
              <option value="weeks">Number of weeks</option>
              <option value="open">No end date</option>
            </select>
          </label>
          {form.until === "date" ? (
            <label>
              Last day
              <input type="date" value={form.end_date} min={form.start_date || istToday()} onChange={set("end_date")} required />
            </label>
          ) : form.until === "weeks" ? (
            <label>
              Weeks
              <input type="number" min={1} max={52} value={form.weeks} onChange={set("weeks")} />
            </label>
          ) : null}
          <label className="sc-wide">
            Work to do
            <input value={form.tasks} onChange={set("tasks")} placeholder="e.g. Medicines check, short walk" />
          </label>
          {formError ? (
            <p className="sc-clash sc-wide" role="alert">
              {formError}
            </p>
          ) : null}
          <div className="sc-form-actions">
            <button type="button" className="secondary" disabled={saving} onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button type="submit" disabled={saving}>
              {saving ? "Booking…" : "Book repeating visits"}
            </button>
          </div>
        </form>
      </OpsModal>

      {clashes.length ? (
        <section className="card rs-clashes" role="alert">
          <h3>Need another caregiver ({clashes.length})</h3>
          <p>
            These visits are booked for the client but have no caregiver yet. Pick one from the roster or{" "}
            <Link href="/kushalaya/visits/leave">Leave and cover</Link>.
          </p>
          <ul>
            {clashes.map((c) => (
              <li key={c.job_id}>{clashText(c)}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {editing ? (
        <section className="card rs-edit">
          <h3>
            {editing.chip.elder_name} · {shortDay(editing.chip.scheduled_at.slice(0, 10))}
          </h3>
          <Directions
            address={clients.find((c) => c.id === editing.chip.elder_id)?.address}
            name={editing.chip.elder_name}
          />
          <div className="sc-form">
            <label>
              Time (IST)
              <input type="time" value={editing.time} onChange={(e) => setEditing({ ...editing, time: e.target.value })} />
            </label>
            <label>
              Caregiver
              <select value={editing.caregiver_id} onChange={(e) => setEditing({ ...editing, caregiver_id: e.target.value })}>
                <option value="">Not assigned</option>
                {caregivers.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.first_name} {c.last_name}
                  </option>
                ))}
              </select>
            </label>
            <fieldset className="sc-wide rs-days">
              <legend>Days (this and following only)</legend>
              {WEEKDAYS.map((d, i) => (
                <button
                  key={d}
                  type="button"
                  aria-pressed={editing.days.includes(i)}
                  className={editing.days.includes(i) ? "is-on" : ""}
                  onClick={() => setEditing({ ...editing, days: toggleDay(i, editing.days) })}
                >
                  {d}
                </button>
              ))}
            </fieldset>
          </div>
          {editClash ? (
            <p className="sc-clash" role="alert">
              {editClash}
              <button type="button" className="sc-step" onClick={() => void applyEdit(editScope, true)}>
                Book anyway
              </button>
            </p>
          ) : null}
          {editError ? (
            <p className="sc-clash" role="alert">
              {editError}
            </p>
          ) : null}
          <div className="sc-form-actions">
            <button type="button" onClick={() => void applyEdit("one")}>
              This visit only
            </button>
            <button type="button" onClick={() => void applyEdit("following")}>
              This and following
            </button>
            <button type="button" className="sc-text" onClick={() => setEditing(null)}>
              Close
            </button>
          </div>
        </section>
      ) : null}

      <div className="rs-weeknav">
        <button type="button" className="sc-step" onClick={() => setWeek(addDays(week, -7))} aria-label="Previous week">
          ‹
        </button>
        <strong>Week of {shortDay(week)}</strong>
        <button type="button" className="sc-step" onClick={() => setWeek(addDays(week, 7))} aria-label="Next week">
          ›
        </button>
        <button type="button" className="sc-text" onClick={() => setWeek(mondayOf(istToday()))}>
          This week
        </button>
      </div>

      {roster === null ? (
        <div className="card sc-empty">Loading…</div>
      ) : rows.length === 0 ? (
        <div className="card sc-empty">No caregivers in your team yet.</div>
      ) : (
        <>
          <div className="rs-grid card" role="table" aria-label="Weekly roster">
            <div className="rs-row rs-head" role="row">
              <div className="rs-name" role="columnheader">
                Caregiver
              </div>
              {roster.days.map((d) => (
                <div key={d.date} role="columnheader" className={d.date === istToday() ? "is-today" : ""}>
                  {d.label}
                </div>
              ))}
            </div>
            {rows.map((r) => (
              <div
                key={`${r.other_team ? "o" : ""}${r.caregiver_id ?? "none"}`}
                className={`rs-row${r.other_team ? " is-other-team" : r.caregiver_id ? "" : " is-unassigned"}`}
                role="row"
              >
                <div className="rs-name" role="rowheader">
                  {r.name}
                </div>
                {r.days.map((_, i) => (
                  <div key={i} role="cell">
                    {cell(r, i)}
                  </div>
                ))}
              </div>
            ))}
          </div>

          <div className="rs-phone card">
            <label>
              Caregiver
              <select value={phoneCg || String(rows[0]?.caregiver_id ?? "none")} onChange={(e) => setPhoneCg(e.target.value)}>
                {phoneRows.map((r) => (
                  <option key={r.caregiver_id ?? "none"} value={String(r.caregiver_id ?? "none")}>
                    {r.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="sc-tabs rs-daytabs" role="tablist">
              {roster.days.map((d, i) => (
                <button
                  key={d.date}
                  type="button"
                  role="tab"
                  aria-selected={phoneDay === i}
                  aria-label={shortDay(d.date)}
                  className={`${phoneDay === i ? "is-on" : ""}${d.date === istToday() ? " is-today" : ""}`}
                  onClick={() => setPhoneDay(i)}
                >
                  <span>{WEEKDAYS[i].slice(0, 2)}</span>
                  <strong>{Number(d.date.slice(8, 10))}</strong>
                </button>
              ))}
            </div>
            {phoneRow ? (
              phoneRow.days[phoneDay].visits.length || phoneRow.days[phoneDay].leave ? (
                cell(phoneRow, phoneDay)
              ) : (
                <p className="sc-empty">No visits.</p>
              )
            ) : null}
          </div>
        </>
      )}

      <section className="card rs-series">
        <h3>Repeating visits</h3>
        {series.length === 0 ? (
          <p className="sc-empty">None yet. Use “+ Repeating visit” for regular visits such as Mon/Wed/Fri 10:00.</p>
        ) : (
          <ul>
            {series.map((s) => (
              <li key={s.id}>
                <span>
                  <strong>{s.elder_name}</strong> — {s.summary}
                  {s.clashes.length ? (
                    <>
                      {" · "}
                      <Link className="rs-warn" href="/kushalaya/visits/leave">
                        {s.clashes.length} clash{s.clashes.length > 1 ? "es" : ""} — find cover
                      </Link>
                    </>
                  ) : null}
                </span>
                {ending?.id === s.id ? (
                  <div className="rs-end">
                    <label>
                      Last day to keep
                      <input
                        type="date"
                        value={ending.date}
                        min={istToday()}
                        onChange={(e) => setEnding({ ...ending, date: e.target.value, error: "" })}
                      />
                    </label>
                    <button type="button" disabled={!ending.date} onClick={() => void stop(s, false)}>
                      End after this day
                    </button>
                    <button type="button" className="secondary" onClick={() => void stop(s, true)}>
                      Stop from today
                    </button>
                    <button type="button" className="sc-text" onClick={() => setEnding(null)}>
                      Cancel
                    </button>
                    {ending.error ? (
                      <p className="sc-clash" role="alert">
                        {ending.error}
                      </p>
                    ) : null}
                  </div>
                ) : (
                  <button type="button" className="sc-text is-danger" onClick={() => setEnding({ id: s.id, date: "", error: "" })}>
                    End…
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
