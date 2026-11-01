"use client";

import { useEffect, useState } from "react";
import {
  cancelMyLeave,
  istToday,
  LEAVE_STATUS_LABEL,
  LEAVE_TYPES,
  myLeave,
  requestMyLeave,
  shortDay,
  type Leave,
} from "@/lib/schedule";

/** "My leave" in the caregiver app: ask for leave, see whether it was approved. */
export function LeaveCard() {
  const [rows, setRows] = useState<Leave[]>([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ leave_type: "ANNUAL", start_date: "", end_date: "", reason: "" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [warn, setWarn] = useState(false);
  const [confirming, setConfirming] = useState<number | null>(null);

  const load = () => myLeave().then(setRows).catch(() => undefined);
  useEffect(() => {
    void load();
  }, []);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg("");
    try {
      await requestMyLeave({ ...form, end_date: form.end_date || form.start_date, reason: form.reason || undefined });
      setForm({ leave_type: "ANNUAL", start_date: "", end_date: "", reason: "" });
      setOpen(false);
      setWarn(false);
      setMsg("Sent to your manager.");
      await load();
    } catch (err) {
      setWarn(true);
      setMsg(err instanceof Error ? err.message : "Could not send");
    } finally {
      setBusy(false);
    }
  }

  async function cancel(id: number) {
    setConfirming(null);
    try {
      await cancelMyLeave(id);
      setWarn(false);
      setMsg("Leave cancelled.");
      await load();
    } catch (err) {
      setWarn(true);
      setMsg(err instanceof Error ? err.message : "Could not cancel");
    }
  }

  const upcoming = rows.filter((r) => r.end_date >= istToday() && r.status !== "CANCELLED");

  return (
    <section aria-labelledby="cg-leave" className="cg-pay">
      <h2 id="cg-leave" className="cg-h2">My leave</h2>
      {upcoming.length ? (
        <ul className="cg-slips">
          {upcoming.map((r) => (
            <li key={r.id}>
              <span>
                {shortDay(r.start_date)}
                {r.end_date !== r.start_date ? ` – ${shortDay(r.end_date)}` : ""}
              </span>
              <span>{LEAVE_STATUS_LABEL[r.status]}</span>
              {r.status === "PENDING" && confirming !== r.id ? (
                <button type="button" className="cg-btn is-ghost" onClick={() => setConfirming(r.id)}>
                  Cancel leave
                </button>
              ) : (
                <span />
              )}
              {r.status === "REJECTED" && r.resolution_note ? (
                <small className="cg-leave-why">Reason: {r.resolution_note}</small>
              ) : null}
              {confirming === r.id ? (
                <div className="cg-confirm cg-leave-why">
                  <p>Cancel this leave request?</p>
                  <div className="cg-confirm-btns">
                    <button type="button" className="cg-btn is-ghost" onClick={() => setConfirming(null)}>
                      Keep it
                    </button>
                    <button type="button" className="cg-btn is-out" onClick={() => void cancel(r.id)}>
                      Yes, cancel leave
                    </button>
                  </div>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="cg-empty">No leave booked.</p>
      )}
      {msg ? <p className={`cg-note ${warn ? "is-warn" : "is-ok"}`}>{msg}</p> : null}
      {open ? (
        <form className="cg-leave-form" onSubmit={send}>
          <label>
            Type
            <select value={form.leave_type} onChange={(e) => setForm({ ...form, leave_type: e.target.value })}>
              {LEAVE_TYPES.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            From
            <input type="date" required min={istToday()} value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
          </label>
          <label>
            To
            <input type="date" min={form.start_date || istToday()} value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} />
          </label>
          <label>
            Reason
            <input value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} placeholder="Optional" />
          </label>
          <div className="cg-confirm-btns">
            <button type="button" className="cg-btn is-ghost" onClick={() => setOpen(false)}>
              Close
            </button>
            <button type="submit" className="cg-btn" disabled={busy}>
              {busy ? "Sending…" : "Ask for leave"}
            </button>
          </div>
        </form>
      ) : (
        <button type="button" className="cg-btn is-out" onClick={() => setOpen(true)}>
          Ask for leave
        </button>
      )}
    </section>
  );
}
