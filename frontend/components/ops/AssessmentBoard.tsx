"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { assessmentBoard, updateJob, type AssessmentBoardRow } from "@/lib/jobs";
import { can } from "@/lib/roles";
import { OpsModal } from "@/components/ops/OpsModal";
import { formatIST, istInputToISO, istInputValue } from "@/lib/ist";
import "./assessment-board.css";

type Tab = AssessmentBoardRow["status"];
const TABS: { id: Tab; label: string; empty: string }[] = [
  { id: "scheduled", label: "Scheduled", empty: "Nothing scheduled." },
  { id: "in_progress", label: "In progress", empty: "No assessment in progress." },
  { id: "completed", label: "Completed", empty: "No completed assessments yet." },
];
type Caregiver = { id: number; first_name: string; last_name: string };

function when(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

function rowDate(r: AssessmentBoardRow) {
  if (r.status === "completed") return r.completed_at || r.updated_at;
  if (r.status === "in_progress") return r.updated_at || r.scheduled_at;
  return r.scheduled_at;
}

/**
 * Assessments page: one list in three tabs (Scheduled · In progress · Completed),
 * one search, aligned rows: date · client · caregiver · status · one action.
 */
export function AssessmentBoard({ reloadToken = 0 }: { reloadToken?: number }) {
  const edit = can("edit");
  const [rows, setRows] = useState<AssessmentBoardRow[] | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("scheduled");
  const [q, setQ] = useState("");
  const [caregivers, setCaregivers] = useState<Caregiver[]>([]);

  const load = useCallback(() => {
    assessmentBoard()
      .then((r) => {
        setRows(r);
        setError("");
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load assessments"));
  }, []);
  useEffect(load, [load, reloadToken]);
  useEffect(() => {
    // Home assessments are done by care managers (the client's point of contact).
    if (edit) api<Caregiver[]>("/api/v1/team/managers").then(setCaregivers).catch(() => undefined);
  }, [edit]);

  const counts = useMemo(() => {
    const c: Record<Tab, number> = { scheduled: 0, in_progress: 0, completed: 0 };
    for (const r of rows ?? []) c[r.status] += 1;
    return c;
  }, [rows]);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const list = (rows ?? []).filter(
      (r) =>
        r.status === tab &&
        (!needle ||
          [r.client_name, r.client_phone, r.area, r.care_manager_name, r.caregiver_name].some((v) => (v || "").toLowerCase().includes(needle))),
    );
    // Scheduled: soonest first. Others: newest first.
    return list.sort((a, b) => {
      const x = new Date(rowDate(a) || 0).getTime();
      const y = new Date(rowDate(b) || 0).getTime();
      return tab === "scheduled" ? x - y : y - x;
    });
  }, [rows, tab, q]);

  async function assign(r: AssessmentBoardRow, managerId: string) {
    if (!r.job_id) return;
    try {
      await updateJob(r.job_id, { assignee_user_id: managerId ? Number(managerId) : null });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not change the care manager");
    }
  }

  const [moving, setMoving] = useState<AssessmentBoardRow | null>(null);
  const [moveDate, setMoveDate] = useState("");
  const [moveTime, setMoveTime] = useState("10:00");
  const [moveBusy, setMoveBusy] = useState(false);
  const [moveError, setMoveError] = useState("");

  function openMove(r: AssessmentBoardRow) {
    setMoving(r);
    setMoveDate(istInputValue(86400000).slice(0, 10));
    setMoveTime("10:00");
    setMoveError("");
  }

  async function saveMove(e: React.FormEvent) {
    e.preventDefault();
    if (!moving?.job_id || !moveDate || !moveTime) return;
    setMoveBusy(true);
    setMoveError("");
    try {
      await updateJob(moving.job_id, { scheduled_at: istInputToISO(`${moveDate}T${moveTime}`), force: true });
      setMoving(null);
      load();
    } catch (err) {
      setMoveError(err instanceof Error ? err.message : "Could not change the date");
    } finally {
      setMoveBusy(false);
    }
  }

  async function cancel(r: AssessmentBoardRow) {
    if (!r.job_id || !window.confirm(`Cancel the assessment for ${r.client_name}?`)) return;
    try {
      await updateJob(r.job_id, { status: "cancelled" });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not cancel the assessment");
    }
  }

  function action(r: AssessmentBoardRow) {
    if (r.status === "completed") {
      return r.assessment_id ? (
        <Link className="ab-act" href={`/kushalaya/assessments/${encodeURIComponent(r.assessment_id)}/report`}>
          View report
        </Link>
      ) : null;
    }
    if (!edit || !r.job_id) return null;
    return (
      <Link className="ab-act is-primary" href={`/caregiver/assess/${r.job_id}?from=assessments`}>
        {r.status === "in_progress" ? "Continue" : "Start"}
      </Link>
    );
  }

  return (
    <section className="ab card" aria-label="Assessments">
      <div className="ab-top">
        <div className="ab-tabs" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className={tab === t.id ? "is-on" : undefined}
              onClick={() => setTab(t.id)}
            >
              {t.label} <span>{counts[t.id]}</span>
            </button>
          ))}
        </div>
        <input
          className="ab-search"
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search name, phone, area…"
          aria-label="Search assessments"
        />
      </div>

      {error ? <p className="error">{error}</p> : null}
      {rows === null && !error ? <p className="muted">Loading…</p> : null}
      {rows !== null && shown.length === 0 ? (
        <p className="ab-empty">{q ? "No match." : TABS.find((t) => t.id === tab)?.empty}</p>
      ) : null}

      {shown.length ? (
        <div className="ab-table" role="table">
          <div className="ab-row ab-head" role="row">
            <span role="columnheader">{tab === "completed" ? "Completed" : tab === "in_progress" ? "Last saved" : "Scheduled for"}</span>
            <span role="columnheader">Client</span>
            <span role="columnheader">Care manager</span>
            <span role="columnheader">{tab === "completed" ? "Score" : "Status"}</span>
            <span role="columnheader" aria-label="Actions" />
          </div>
          {shown.map((r) => (
            <div className="ab-row" role="row" key={r.key}>
              <span className="ab-when" role="cell" data-label="When">
                {when(rowDate(r))}
              </span>
              <span className="ab-client" role="cell" data-label="Client">
                <strong>
                  <span className="ab-name">{r.client_name}</span>
                  {r.is_lead ? <em className="ab-tag">Lead</em> : null}
                </strong>
                <small>{[r.area, r.client_phone].filter(Boolean).join(" · ") || "No address yet"}</small>
              </span>
              <span className="ab-cg" role="cell" data-label="Care manager">
                {edit && r.status === "scheduled" && r.job_id ? (
                  <select value={r.care_manager_id ?? ""} onChange={(e) => void assign(r, e.target.value)} aria-label="Care manager">
                    <option value="">Not assigned</option>
                    {caregivers.map((c) => (
                      <option key={c.id} value={c.id}>
                        {`${c.first_name} ${c.last_name}`.trim()}
                      </option>
                    ))}
                  </select>
                ) : (
                  r.care_manager_name || r.caregiver_name || "—"
                )}
              </span>
              <span className="ab-state" role="cell" data-label={tab === "completed" ? "Score" : "Status"}>
                {r.status === "completed" ? (
                  <b className="ab-score">{r.score ?? "—"}</b>
                ) : r.overdue_days > 0 ? (
                  <b className="ab-pill is-late">Overdue · {r.overdue_days}d</b>
                ) : r.status === "in_progress" ? (
                  <b className="ab-pill is-prog">{r.answered} answered</b>
                ) : (
                  <b className="ab-pill">Scheduled</b>
                )}
              </span>
              <span className="ab-actions" role="cell">
                {action(r)}
                {edit && r.status === "scheduled" && r.job_id ? (
                  <button type="button" className="ab-cancel ab-move" onClick={() => openMove(r)}>
                    Change time
                  </button>
                ) : null}
                {edit && r.status !== "completed" && r.job_id ? (
                  <button type="button" className="ab-cancel" onClick={() => void cancel(r)}>
                    Cancel
                  </button>
                ) : null}
              </span>
            </div>
          ))}
        </div>
      ) : null}
      <OpsModal open={moving !== null} title={moving ? `Change time: ${moving.client_name}` : ""} onClose={() => setMoving(null)}>
        {moving ? (
          <form onSubmit={saveMove} style={{ display: "grid", gap: "0.75rem" }}>
            <p className="muted">Now: {moving.scheduled_at ? formatIST(moving.scheduled_at) : "no time set"}</p>
            <label>
              New date
              <input type="date" value={moveDate} min={istInputValue().slice(0, 10)} required onChange={(e) => setMoveDate(e.target.value)} />
            </label>
            <label>
              New time (IST)
              <input type="time" value={moveTime} required onChange={(e) => setMoveTime(e.target.value)} />
            </label>
            {moveError ? (
              <p className="error" role="alert">
                {moveError}
              </p>
            ) : null}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
              <button type="button" className="secondary" onClick={() => setMoving(null)} disabled={moveBusy}>
                Close
              </button>
              <button type="submit" disabled={moveBusy}>
                {moveBusy ? "Saving…" : "Save new time"}
              </button>
            </div>
          </form>
        ) : null}
      </OpsModal>
    </section>
  );
}
