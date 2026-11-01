"use client";

import { useCallback, useEffect, useState } from "react";
import { api, fetchMe } from "@/lib/api";
import {
  GOAL_STATUS_LABEL,
  RISK_LEVEL_LABEL,
  shortDate,
  type CareGoal,
  type CarePlan,
  type ClientRisk,
  type GoalStatus,
  type Handover,
  type RiskLevel,
} from "@/lib/clientCare";
import "@/components/care-sheet.css";
import { can } from "@/lib/roles";

const errText = (e: unknown) => (e as Error)?.message || "Something went wrong";

type GoalForm = { id?: number; goal: string; target_date: string; status: GoalStatus; interventions: string; progress: string };
const NEW_GOAL: GoalForm = { goal: "", target_date: "", status: "active", interventions: "", progress: "" };

/** Care plan (#95): goals, what we do for each, progress in plain words, review date. */
export function ClientCarePlan({ elderId }: { elderId: number }) {
  const base = `/api/v1/home-safety/clients/${elderId}/care-plan`;
  const [plan, setPlan] = useState<CarePlan | null>(null);
  const [form, setForm] = useState<GoalForm | null>(null);
  const [reviewDate, setReviewDate] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api<CarePlan>(base).then(setPlan).catch((e) => setError(errText(e)));
  }, [base]);
  useEffect(() => load(), [load]);

  async function run(fn: () => Promise<unknown>) {
    setError("");
    try {
      await fn();
      load();
    } catch (e) {
      setError(errText(e));
    }
  }

  async function saveGoal() {
    if (!form) return;
    const body = {
      goal: form.goal,
      target_date: form.target_date || null,
      status: form.status,
      interventions: form.interventions.split("\n").map((s) => s.trim()).filter(Boolean),
      progress: form.progress,
    };
    await run(() =>
      api(form.id ? `${base}/goals/${form.id}` : `${base}/goals`, {
        method: form.id ? "PUT" : "POST",
        body: JSON.stringify(body),
      }).then(() => setForm(null)),
    );
  }

  function edit(g: CareGoal) {
    setForm({
      id: g.id,
      goal: g.goal,
      target_date: g.target_date ?? "",
      status: g.status,
      interventions: g.interventions.join("\n"),
      progress: g.progress,
    });
  }

  if (!plan) return error ? <p className="cc-err">{error}</p> : null;
  const r = plan.review;

  const canEdit = can("edit");
  return (
    <section className="card" id="care-plan">
      <div className="cc-head">
        <h2>Care plan</h2>
        <span className="cc-small">
          {r.review_date ? (
            <>
              {r.overdue ? (
                <span className="cc-tag is-overdue">Review overdue (was due {shortDate(r.review_date)})</span>
              ) : (
                <>
                  Review due {shortDate(r.review_date)}{" "}
                  <span className={`cc-tag ${r.due ? "is-due" : ""}`}>
                    {r.source === "reassessment" ? "with the 6-monthly reassessment" : r.due ? "Due soon" : "Set"}
                  </span>
                </>
              )}
            </>
          ) : (
            "No review date yet (it follows the 6-monthly reassessment once one is done)"
          )}
          {r.reviewed_at ? ` · last reviewed ${shortDate(r.reviewed_at)}` : ""}
        </span>
        {canEdit ? (
        <div className="cc-actions">
          <button type="button" className="secondary" onClick={() => void run(() => api(`${base}/review`, { method: "POST", body: JSON.stringify({ reviewed: true }) }))}>
            Mark reviewed
          </button>
          <button type="button" onClick={() => setForm(NEW_GOAL)}>
            + Goal
          </button>
        </div>
        ) : null}
      </div>
      {canEdit ? (
      <div className="cc-row" style={{ marginTop: "0.5rem" }}>
        <label className="cc-small">
          {r.review_date ? "Change review date" : "Next review"}{" "}
          <input type="date" value={reviewDate} onChange={(e) => setReviewDate(e.target.value)} />
        </label>
        <button
          type="button"
          className="secondary"
          disabled={!reviewDate}
          onClick={() => void run(() => api(`${base}/review`, { method: "POST", body: JSON.stringify({ review_date: reviewDate }) }).then(() => setReviewDate("")))}
        >
          {r.review_date ? "Change date" : "Set date"}
        </button>
      </div>
      ) : null}
      {error ? <p className="cc-err">{error}</p> : null}

      {form ? (
        <div className="cc-form">
          <label className="cc-wide">
            Goal
            <input placeholder="Walk to the gate without help" value={form.goal} onChange={(e) => setForm({ ...form, goal: e.target.value })} />
          </label>
          <label>
            Target date
            <input type="date" value={form.target_date} onChange={(e) => setForm({ ...form, target_date: e.target.value })} />
          </label>
          <label>
            Status
            <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as GoalStatus })}>
              {(Object.keys(GOAL_STATUS_LABEL) as GoalStatus[]).map((s) => (
                <option key={s} value={s}>
                  {GOAL_STATUS_LABEL[s]}
                </option>
              ))}
            </select>
          </label>
          <label className="cc-wide">
            What we do (one per line)
            <textarea rows={3} placeholder={"Walk 10 minutes with support daily\nGrab bar by the front door"} value={form.interventions} onChange={(e) => setForm({ ...form, interventions: e.target.value })} />
          </label>
          <label className="cc-wide">
            Progress (the family sees this — plain words)
            <textarea rows={2} value={form.progress} onChange={(e) => setForm({ ...form, progress: e.target.value })} />
          </label>
          <div className="cc-row">
            <button type="button" onClick={() => void saveGoal()} disabled={!form.goal.trim()}>
              Save goal
            </button>
            <button type="button" className="secondary" onClick={() => setForm(null)}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      {plan.goals.length ? (
        <ul className="cc-list">
          {plan.goals.map((g) => (
            <li key={g.id}>
              <div className="cc-row">
                <strong>{g.goal}</strong>
                <span className={`cc-tag ${g.status === "achieved" ? "is-good" : ""}`}>{g.status_label}</span>
                {g.target_date ? <span className="cc-small">by {shortDate(g.target_date)}</span> : null}
                {canEdit ? (
                <span className="cc-actions">
                  <button type="button" className="secondary" onClick={() => edit(g)}>
                    Edit
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => {
                      if (window.confirm("Delete this goal?")) void run(() => api(`${base}/goals/${g.id}`, { method: "DELETE" }));
                    }}
                  >
                    Delete
                  </button>
                </span>
                ) : null}
              </div>
              {g.interventions.length ? (
                <ul className="cc-small" style={{ margin: "0.3rem 0 0" }}>
                  {g.interventions.map((i, n) => (
                    <li key={n}>{i}</li>
                  ))}
                </ul>
              ) : null}
              {g.progress ? <p className="cc-small" style={{ margin: "0.3rem 0 0" }}>Progress: {g.progress}</p> : null}
            </li>
          ))}
        </ul>
      ) : form ? null : (
        <p className="cc-small">No goals yet. Agree two or three with the family after the assessment.</p>
      )}
    </section>
  );
}

type RiskForm = { id?: number; risk: string; level: RiskLevel; mitigation: string; review_date: string };
const NEW_RISK: RiskForm = { risk: "", level: "medium", mitigation: "", review_date: "" };

/** Risk register (#98): high risks and overdue reviews show on the Dashboard. */
export function ClientRiskRegister({ elderId }: { elderId: number }) {
  const base = `/api/v1/home-safety/clients/${elderId}/risks`;
  const [rows, setRows] = useState<ClientRisk[] | null>(null);
  const [form, setForm] = useState<RiskForm | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api<ClientRisk[]>(base).then(setRows).catch((e) => setError(errText(e)));
  }, [base]);
  useEffect(() => load(), [load]);

  async function run(fn: () => Promise<unknown>) {
    setError("");
    try {
      await fn();
      load();
    } catch (e) {
      setError(errText(e));
    }
  }

  async function save() {
    if (!form) return;
    const body = { risk: form.risk, level: form.level, mitigation: form.mitigation, review_date: form.review_date || null };
    await run(() =>
      api(form.id ? `${base}/${form.id}` : base, { method: form.id ? "PUT" : "POST", body: JSON.stringify(body) }).then(() => setForm(null)),
    );
  }

  if (!rows) return error ? <p className="cc-err">{error}</p> : null;

  const canEdit = can("edit");
  return (
    <section className="card" id="risks">
      <div className="cc-head">
        <h2>Risk register</h2>
        <span className="cc-small">Staff only</span>
        {canEdit ? (
          <div className="cc-actions">
            <button type="button" onClick={() => setForm(NEW_RISK)}>
              + Risk
            </button>
          </div>
        ) : null}
      </div>
      {error ? <p className="cc-err">{error}</p> : null}
      {form ? (
        <div className="cc-form">
          <label className="cc-wide">
            Risk
            <input placeholder="Falls at night going to the bathroom" value={form.risk} onChange={(e) => setForm({ ...form, risk: e.target.value })} />
          </label>
          <label>
            Level
            <select value={form.level} onChange={(e) => setForm({ ...form, level: e.target.value as RiskLevel })}>
              {(Object.keys(RISK_LEVEL_LABEL) as RiskLevel[]).map((l) => (
                <option key={l} value={l}>
                  {RISK_LEVEL_LABEL[l]}
                </option>
              ))}
            </select>
          </label>
          <label>
            Review by
            <input type="date" value={form.review_date} onChange={(e) => setForm({ ...form, review_date: e.target.value })} />
          </label>
          <label className="cc-wide">
            What we do about it
            <textarea rows={2} placeholder="Night light, commode by the bed" value={form.mitigation} onChange={(e) => setForm({ ...form, mitigation: e.target.value })} />
          </label>
          <div className="cc-row">
            <button type="button" onClick={() => void save()} disabled={!form.risk.trim()}>
              Save risk
            </button>
            <button type="button" className="secondary" onClick={() => setForm(null)}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}
      {rows.length ? (
        <ul className="cc-list">
          {rows.map((r) => (
            <li key={r.id} style={r.status === "closed" ? { opacity: 0.6 } : undefined}>
              <div className="cc-row">
                <span className={`cc-tag is-${r.level}`}>{RISK_LEVEL_LABEL[r.level]}</span>
                <strong>{r.risk}</strong>
                {r.status === "closed" ? <span className="cc-tag">Resolved</span> : null}
                {r.review_overdue ? <span className="cc-tag is-overdue">Review overdue</span> : null}
                {canEdit ? (
                <span className="cc-actions">
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => setForm({ id: r.id, risk: r.risk, level: r.level, mitigation: r.mitigation, review_date: r.review_date ?? "" })}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => void run(() => api(`${base}/${r.id}`, { method: "PUT", body: JSON.stringify({ status: r.status === "open" ? "closed" : "open" }) }))}
                  >
                    {r.status === "open" ? "Mark resolved" : "Reopen"}
                  </button>
                </span>
                ) : null}
              </div>
              <p className="cc-small" style={{ margin: "0.3rem 0 0" }}>
                {r.mitigation || "No mitigation written yet"}
                {r.owner_name ? ` · owner ${r.owner_name}` : ""}
                {r.review_date ? ` · review ${shortDate(r.review_date)}` : ""}
              </p>
            </li>
          ))}
        </ul>
      ) : form ? null : (
        <p className="cc-small">No risks recorded.</p>
      )}
    </section>
  );
}

/** Handover notes for this client (#98): hand over a shift, or move the client to another manager. */
export function ClientHandovers({ elderId, onMoved }: { elderId: number; onMoved?: () => void }) {
  const [rows, setRows] = useState<Handover[] | null>(null);
  const [people, setPeople] = useState<{ id: number; name: string }[]>([]);
  const [form, setForm] = useState<{ to: string; kind: "shift" | "client_move"; note: string } | null>(null);
  const [error, setError] = useState("");
  const [meId, setMeId] = useState<number | null>(null);

  const load = useCallback(() => {
    api<Handover[]>(`/api/v1/home-safety/clients/${elderId}/handovers`).then(setRows).catch((e) => setError(errText(e)));
  }, [elderId]);
  useEffect(() => load(), [load]);
  useEffect(() => {
    fetchMe()
      .then((m) => setMeId(m.id))
      .catch(() => setMeId(null));
  }, []);

  // ?tab=handovers lands on the Care plan tab; bring this card into view.
  const loaded = rows !== null;
  useEffect(() => {
    if (!loaded) return;
    if (new URLSearchParams(window.location.search).get("tab")?.toLowerCase() !== "handovers") return;
    document.getElementById("handovers")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [loaded]);

  async function acknowledge(id: number) {
    setError("");
    try {
      await api(`/api/v1/home-safety/handovers/${id}/acknowledge`, { method: "POST" });
      load();
    } catch (e) {
      setError(errText(e));
    }
  }

  function open() {
    setForm({ to: "", kind: "shift", note: "" });
    api<{ id: number; name: string }[]>("/api/v1/home-safety/handovers/recipients").then(setPeople).catch(() => setPeople([]));
  }

  async function send() {
    if (!form) return;
    setError("");
    try {
      await api("/api/v1/home-safety/handovers", {
        method: "POST",
        body: JSON.stringify({ kind: form.kind, to_user_id: Number(form.to), elder_id: elderId, note: form.note }),
      });
      const moved = form.kind === "client_move";
      setForm(null);
      load();
      if (moved) onMoved?.();
    } catch (e) {
      setError(errText(e));
    }
  }

  if (!rows) return error ? <p className="cc-err">{error}</p> : null;

  return (
    <section className="card" id="handovers">
      <div className="cc-head">
        <h2>Handover notes</h2>
        {can("edit") ? (
          <div className="cc-actions">
            <button type="button" onClick={open}>
              Hand over
            </button>
          </div>
        ) : null}
      </div>
      {error ? <p className="cc-err">{error}</p> : null}
      {form ? (
        <div className="cc-form">
          <label>
            To
            <select value={form.to} onChange={(e) => setForm({ ...form, to: e.target.value })}>
              <option value="">Choose a manager</option>
              {people.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Type
            <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as "shift" | "client_move" })}>
              <option value="shift">Shift handover</option>
              <option value="client_move">Move client to this manager</option>
            </select>
          </label>
          <label className="cc-wide">
            Note
            <textarea rows={3} placeholder="What the next manager needs to know" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
          </label>
          <div className="cc-row">
            <button type="button" onClick={() => void send()} disabled={!form.to || !form.note.trim()}>
              Send handover
            </button>
            <button type="button" className="secondary" onClick={() => setForm(null)}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}
      {rows.length ? (
        <ul className="cc-list">
          {rows.map((h) => (
            <li key={h.id}>
              <div className="cc-row">
                <span className="cc-tag">{h.kind_label}</span>
                <strong>
                  {h.from_name || "—"} → {h.to_name}
                </strong>
                <span className="cc-small">{shortDate(h.created_at)}</span>
                <span className={`cc-tag ${h.acknowledged_at ? "is-good" : "is-due"}`}>
                  {h.acknowledged_at ? `Acknowledged ${shortDate(h.acknowledged_at)}` : "Waiting"}
                </span>
                {!h.acknowledged_at && meId !== null && h.to_user_id === meId ? (
                  <button type="button" onClick={() => void acknowledge(h.id)}>
                    Acknowledge
                  </button>
                ) : null}
              </div>
              <p style={{ margin: "0.3rem 0 0", whiteSpace: "pre-wrap" }}>{h.note}</p>
            </li>
          ))}
        </ul>
      ) : form ? null : (
        <p className="cc-small">No handovers yet.</p>
      )}
    </section>
  );
}
