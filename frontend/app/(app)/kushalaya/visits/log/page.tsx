"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { BackLink, PageActions } from "@/components/ops/PageActions";
import { PageHeader } from "@/components/PageHeader";
import { dayMonth } from "@/lib/ist";
import { api } from "@/lib/api";
import { Flash } from "@/components/Flash";
import { KushLifeCaptureForm } from "@/components/KushLifeCapture";
import { emptyCapture, missingAnswers, toPayload } from "@/lib/kushlife";
import "@/components/ops/schedule.css";

type Client = { id: number; first_name: string; last_name: string };
type Caregiver = { id: number; first_name: string; last_name: string };
function nowLocal() {
  const d = new Date();
  d.setMinutes(Math.floor(d.getMinutes() / 15) * 15, 0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return { date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`, time: `${pad(d.getHours())}:${pad(d.getMinutes())}` };
}

/** "Wed 7 Oct" for the picked date, so it reads the same as everywhere else. */
function lvDay(ymd: string) {
  const d = new Date(`${ymd}T12:00:00+05:30`);
  if (Number.isNaN(d.getTime())) return "";
  return dayMonth(d, undefined, true);
}

/** Log a past visit: a visit that happened without being booked on Schedule. */
export default function LogPastVisitPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [caregivers, setCaregivers] = useState<Caregiver[]>([]);
  const [elderId, setElderId] = useState("");
  const [caregiverId, setCaregiverId] = useState("");
  const [when, setWhen] = useState(nowLocal);
  const [duration, setDuration] = useState("60");
  const [kl, setKl] = useState(emptyCapture);
  const [note, setNote] = useState("");
  const [hazard, setHazard] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<{ elderId: string; name: string } | null>(null);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    if (q.get("elder")) setElderId(q.get("elder") as string);
    api<Client[]>("/api/v1/team/clients").then(setClients).catch(() => undefined);
    api<Caregiver[]>("/api/v1/team/caregivers").then(setCaregivers).catch(() => undefined);
  }, []);

  async function save(e: FormEvent) {
    e.preventDefault();
    setError("");
    const at = new Date(`${when.date}T${when.time}`);
    if (Number.isNaN(at.getTime())) return setError("Pick the date and time of the visit.");
    if (at.getTime() > Date.now()) return setError("That time is in the future — book it on Schedule instead.");
    const missing = missingAnswers(kl);
    if (missing.length) return setError(`Please answer the KushLife check: ${missing.join(", ")}.`);
    setSaving(true);
    try {
      await api("/api/v1/jobs/log-past", {
        method: "POST",
        body: JSON.stringify({
          elder_id: Number(elderId),
          caregiver_id: caregiverId ? Number(caregiverId) : null,
          visited_at: at.toISOString(),
          duration_minutes: Number(duration) || null,
          kushlife: toPayload(kl),
          note,
          hazard: hazard.trim() ? { note: hazard.trim() } : null,
        }),
      });
      const c = clients.find((x) => String(x.id) === elderId);
      setSaved({ elderId, name: c ? c.first_name : "the client" });
      setKl(emptyCapture());
      setNote("");
      setHazard("");
      setWhen(nowLocal());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the visit");
    } finally {
      setSaving(false);
    }
  }

  const concerns = Object.values(kl.checks).filter((c) => c.status === "concern").length;

  return (
    <>
      <p className="ks-back-row">
        <BackLink href="/kushalaya/visits" label="Visits" />
      </p>
      <PageHeader title="Log a past visit" subtitle="For a visit that already happened without being booked. The family gets the report." />
      <Flash error={error} message="" onClear={() => setError("")} />
      <PageActions
        items={[
          { href: "/kushalaya/visits?tab=past", label: "Past visits" },
          { href: "/kushalaya/visits?schedule=1", label: "Schedule a visit instead" },
        ]}
      />

      {saved && (
        <div className="card lv-done">
          <strong>Visit saved — {saved.name}’s family can see the report.</strong>
          <span>
            <Link href={`/kushalaya/customers/${saved.elderId}`}>Open client →</Link>
            <button type="button" className="sc-text" onClick={() => setSaved(null)}>
              Log another
            </button>
          </span>
        </div>
      )}

      {!saved && (
        <form className="card lv-form" onSubmit={(e) => void save(e)}>
          <section className="lv-grid">
            <label>
              Client
              <select required value={elderId} onChange={(e) => setElderId(e.target.value)}>
                <option value="">Choose a client…</option>
                {clients.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.first_name} {c.last_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Who visited
              <select value={caregiverId} onChange={(e) => setCaregiverId(e.target.value)}>
                <option value="">Care manager (me)</option>
                {caregivers.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.first_name} {c.last_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Date
              <span className="lv-date">
                <input type="date" required value={when.date} max={nowLocal().date} onChange={(e) => setWhen({ ...when, date: e.target.value })} />
                {when.date ? <small className="muted">{lvDay(when.date)}</small> : null}
              </span>
            </label>
            <label>
              Time
              <input type="time" required value={when.time} onChange={(e) => setWhen({ ...when, time: e.target.value })} />
            </label>
            <label>
              How long
              <select value={duration} onChange={(e) => setDuration(e.target.value)}>
                <option value="30">30 min</option>
                <option value="60">1 hour</option>
                <option value="90">1½ hours</option>
                <option value="120">2 hours</option>
                <option value="240">Half day</option>
              </select>
            </label>
          </section>

          <div className="lv-kl">
            <KushLifeCaptureForm value={kl} onChange={setKl} />
          </div>

          <label className="lv-field">
            Note for the family
            <textarea
              rows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="How the visit went, what was done, anything they should know"
            />
          </label>
          <label className="lv-field">
            <span>
              Hazard spotted at home <span className="muted">(optional)</span>
            </span>
            <input value={hazard} onChange={(e) => setHazard(e.target.value)} placeholder="e.g. Loose rug near the bathroom door" />
          </label>

          <div className="lv-actions">
            <span className="muted">{concerns ? `${concerns} check${concerns === 1 ? "" : "s"} changed — the family will see it.` : "The family gets the KushLife report."}</span>
            <button type="submit" disabled={saving || !elderId}>
              {saving ? "Saving…" : "Save visit"}
            </button>
          </div>
        </form>
      )}
    </>
  );
}
