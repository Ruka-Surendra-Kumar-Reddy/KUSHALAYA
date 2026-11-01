"use client";

import { useEffect, useState } from "react";
import { EmailChips } from "@/components/EmailChips";
import { familyApi } from "@/lib/livewell/familyApi";

type Prefs = {
  extra: string[];
  off: string[];
  logins: string[];
  events: { key: string; label: string }[];
};

/** Family: which emails we get, and who else gets them. Saves on every change. */
export function FamilyEmailPrefs() {
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [status, setStatus] = useState("");

  useEffect(() => {
    familyApi<Prefs>("/email-prefs")
      .then(setPrefs)
      .catch(() => setStatus("Could not load your email choices."));
  }, []);

  async function save(patch: Partial<Pick<Prefs, "extra" | "off">>) {
    if (!prefs) return;
    setPrefs({ ...prefs, ...patch });
    setStatus("Saving…");
    try {
      setPrefs(await familyApi<Prefs>("/email-prefs", { method: "PUT", body: JSON.stringify(patch) }));
      setStatus("Saved");
    } catch {
      setStatus("Could not save — try again.");
    }
  }

  if (!prefs) return <section className="card home-safety-section">{status || "Loading…"}</section>;

  return (
    <section className="card home-safety-section ks-email-prefs" aria-labelledby="email-prefs-title">
      <div className="ks-email-head">
        <h2 id="email-prefs-title">Email notifications</h2>
        {status && <small aria-live="polite">{status}</small>}
      </div>
      <p className="muted">Everything also appears under Alerts in the app. Turn off what you don’t want by email.</p>
      <ul className="ks-switches">
        {prefs.events.map((e) => {
          const on = !prefs.off.includes(e.key);
          return (
            <li key={e.key}>
              <label>
                <input
                  type="checkbox"
                  role="switch"
                  checked={on}
                  onChange={() => save({ off: on ? [...prefs.off, e.key] : prefs.off.filter((k) => k !== e.key) })}
                />
                <span>{e.label}</span>
              </label>
            </li>
          );
        })}
      </ul>
      <h3>Who gets these emails</h3>
      <p className="muted">
        Family members who sign in: {prefs.logins.length ? prefs.logins.join(", ") : "none yet"}. Add anyone else — a
        brother or sister abroad — below.
      </p>
      <EmailChips value={prefs.extra} onChange={(extra) => save({ extra })} label="Add a family email" />
    </section>
  );
}
