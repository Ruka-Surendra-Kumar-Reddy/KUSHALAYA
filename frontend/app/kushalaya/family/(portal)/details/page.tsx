"use client";

import { useEffect, useState } from "react";
import { FamilyShell } from "@/components/livewell/family/FamilyShell";
import { FamilyCareSheet } from "@/components/livewell/family/FamilyCareSheet";
import "@/components/care-sheet.css";
import {
  fetchMyDetails,
  requestDetailsChange,
  saveMyDetails,
  type FamilyMyDetails,
} from "@/lib/family-money";
import { CHANNEL_OPTIONS, TIMEZONE_OPTIONS, timezoneLabel } from "@/lib/family-contacts";
import { FamilyLink as Link } from "@/components/livewell/family/FamilyLink";
import { resetFamilyTimezone } from "@/lib/family-zone";
import { familyApi, type FamilyStatus } from "@/lib/livewell/familyApi";
import { statusWords } from "@/lib/livewell/familyStatus";
import { useFamilySelf } from "@/lib/livewell/familySelf";

type Contact = Pick<
  FamilyMyDetails,
  | "first_name"
  | "last_name"
  | "phone"
  | "channel"
  | "timezone"
  | "level"
  | "emergency_contact_name"
  | "emergency_contact_phone"
>;
const EMPTY_CONTACT: Contact = {
  first_name: "",
  last_name: "",
  phone: "",
  channel: "whatsapp",
  timezone: "Asia/Kolkata",
  level: "everything",
  emergency_contact_name: "",
  emergency_contact_phone: "",
};
const EMPTY_CHANGE = { conditions: "", allergies: "", medicines: "", mobility: "", note: "" };

/** My details: your own name and phone, the parent's emergency contact, and a health-change request. */
export default function FamilyDetailsPage() {
  const [details, setDetails] = useState<FamilyMyDetails | null>(null);
  const [form, setForm] = useState<Contact>(EMPTY_CONTACT);
  const [change, setChange] = useState(EMPTY_CHANGE);
  const [busy, setBusy] = useState<"" | "save" | "change">("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  // The same status as Home and the digest (GET /family/status).
  const [status, setStatus] = useState<FamilyStatus | null>(null);

  function fill(d: FamilyMyDetails) {
    setDetails(d);
    setForm({
      first_name: d.first_name,
      last_name: d.last_name,
      phone: d.phone,
      channel: d.channel,
      timezone: d.timezone || "Asia/Kolkata",
      level: d.level,
      emergency_contact_name: d.emergency_contact_name,
      emergency_contact_phone: d.emergency_contact_phone,
    });
  }

  useEffect(() => {
    familyApi<FamilyStatus>("/status").then(setStatus).catch(() => undefined);
    fetchMyDetails()
      .then(fill)
      .catch((e) => setError(e instanceof Error ? e.message : "Couldn't load your details"));
  }, []);

  const set = (k: keyof Contact) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setNotice("");
    setBusy("save");
    try {
      // Phones only when changed: an old number in another format must not block saving the rest.
      const { phone, emergency_contact_phone, ...rest } = form;
      fill(
        await saveMyDetails({
          ...rest,
          ...(phone !== (details?.phone ?? "") ? { phone } : {}),
          ...(emergency_contact_phone !== (details?.emergency_contact_phone ?? "") ? { emergency_contact_phone } : {}),
        }),
      );
      setNotice("Saved.");
      resetFamilyTimezone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save");
    } finally {
      setBusy("");
    }
  }

  async function sendChange(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setNotice("");
    setBusy("change");
    try {
      await requestDetailsChange(change);
      setChange(EMPTY_CHANGE);
      setNotice("Sent. Your care team will check it and update the health details.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't send");
    } finally {
      setBusy("");
    }
  }

  const parent = details?.elder_name || "your family member";
  const health = details?.health;
  // The elder reading their own record: "your", not "your parent" / "Lakshmi's".
  const { isSelf } = useFamilySelf();

  return (
    <FamilyShell
      title="My details"
      subtitle={
        isSelf
          ? "Your contact details, your emergency contact and your health details"
          : `Your contact details, the emergency contact, and health details for ${parent}`
      }
    >
      {error ? <p className="error-text">{error}</p> : null}
      {notice ? <p className="muted" role="status">{notice}</p> : null}

      <section className="card home-safety-section">
        <h2>You</h2>
        <form className="fh-details-form" onSubmit={(e) => void save(e)}>
          <label>
            <span className="muted">First name</span>
            <input value={form.first_name} onChange={set("first_name")} autoComplete="given-name" required />
          </label>
          <label>
            <span className="muted">Last name</span>
            <input value={form.last_name} onChange={set("last_name")} autoComplete="family-name" />
          </label>
          <label>
            <span className="muted">Phone (with country code)</span>
            <input
              value={form.phone}
              onChange={set("phone")}
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              placeholder="+971 50 123 4567"
            />
          </label>
          {details ? <small className="muted">Email: {details.email} (to change it, message the care team)</small> : null}
          <label>
            <span className="muted">Best way to reach you</span>
            <select value={form.channel} onChange={set("channel")}>
              {CHANNEL_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="muted">Where you live (times in the app, emails and digests use this)</span>
            <select value={form.timezone} onChange={set("timezone")}>
              {(TIMEZONE_OPTIONS.some((o) => o.value === form.timezone)
                ? TIMEZONE_OPTIONS
                : [...TIMEZONE_OPTIONS, { value: form.timezone, label: timezoneLabel(form.timezone) }]
              ).map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          {/* Notification choices live on one page: Notifications. */}
          <p className="muted">
            What we tell you about, emails and digests:{" "}
            <Link href="/kushalaya/family/digests" className="fh-tap">
              Notifications →
            </Link>
          </p>

          <h2>{isSelf ? "Your emergency contact" : `Emergency contact for ${parent}`}</h2>
          <p className="muted">
            {isSelf
              ? "The person we call first if something happens to you."
              : "The person we call first if something happens and we can't reach you."}
          </p>
          <label>
            <span className="muted">Name</span>
            <input value={form.emergency_contact_name} onChange={set("emergency_contact_name")} />
          </label>
          <label>
            <span className="muted">Phone</span>
            <input
              value={form.emergency_contact_phone}
              onChange={set("emergency_contact_phone")}
              type="tel"
              inputMode="tel"
              placeholder="+91 98765 43210"
            />
          </label>
          <button type="submit" disabled={busy !== "" || !details}>
            {busy === "save" ? "Saving…" : "Save"}
          </button>
        </form>
      </section>

      <section className="card home-safety-section">
        <h2>{isSelf ? "Your health details" : `${parent}'s health details`}</h2>
        {status ? (
          <p className="fh-details-status">
            <strong>Now:</strong> {statusWords(status.word)}
            {status.checks_text ? ` · last visit ${status.checks_text}` : status.changes.length ? ` · ${status.changes_text}` : ""}
          </p>
        ) : null}
        {health ? <FamilyCareSheet /> : null}
        <p className="muted">
          Something changed? Tell us below. A Family Partner checks it and updates the record, so the
          caregivers always see the right details.
        </p>
        <form className="fh-details-form" onSubmit={(e) => void sendChange(e)}>
          <label>
            <span className="muted">Health conditions</span>
            <input value={change.conditions} onChange={(e) => setChange({ ...change, conditions: e.target.value })} />
          </label>
          <label>
            <span className="muted">Allergies</span>
            <input value={change.allergies} onChange={(e) => setChange({ ...change, allergies: e.target.value })} />
          </label>
          <label>
            <span className="muted">Medicines</span>
            <input value={change.medicines} onChange={(e) => setChange({ ...change, medicines: e.target.value })} />
          </label>
          <label>
            <span className="muted">Walking and mobility</span>
            <input value={change.mobility} onChange={(e) => setChange({ ...change, mobility: e.target.value })} />
          </label>
          <label>
            <span className="muted">Anything else</span>
            <textarea rows={3} value={change.note} onChange={(e) => setChange({ ...change, note: e.target.value })} />
          </label>
          <button type="submit" className="secondary" disabled={busy !== ""}>
            {busy === "change" ? "Sending…" : "Request a change"}
          </button>
        </form>
      </section>
    </FamilyShell>
  );
}
