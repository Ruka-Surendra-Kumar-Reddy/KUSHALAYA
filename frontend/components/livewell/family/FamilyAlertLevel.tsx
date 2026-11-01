"use client";

import { useEffect, useState } from "react";
import { LEVEL_OPTIONS } from "@/lib/family-contacts";
import { fetchMyDetails, saveMyDetails, type FamilyMyDetails } from "@/lib/family-money";

/** "What should we tell you about?" — on the one Notifications page; saves as soon as it changes. */
export function FamilyAlertLevel() {
  const [level, setLevel] = useState<FamilyMyDetails["level"] | null>(null);
  const [note, setNote] = useState("");

  useEffect(() => {
    fetchMyDetails()
      .then((d) => setLevel(d.level))
      .catch(() => setLevel(null));
  }, []);

  async function choose(value: FamilyMyDetails["level"]) {
    const before = level;
    setLevel(value);
    setNote("");
    try {
      await saveMyDetails({ level: value });
      setNote("Saved.");
    } catch (e) {
      setLevel(before);
      setNote(e instanceof Error ? e.message : "Couldn't save");
    }
  }

  if (level == null) return null;
  return (
    <section className="card home-safety-section fh-details-form">
      <fieldset className="fh-level">
        <legend>
          <h2>What should we tell you about?</h2>
        </legend>
        {LEVEL_OPTIONS.map((o) => (
          <label key={o.value} className="fh-level-opt">
            <input
              type="radio"
              name="alert-level"
              value={o.value}
              checked={level === o.value}
              onChange={() => void choose(o.value)}
            />
            <span>
              <strong>{o.label}</strong>
              <small className="muted"> — {o.hint}</small>
            </span>
          </label>
        ))}
        <small className="muted">
          We email you now. Text and WhatsApp messages will follow the same choice once they are switched on.
        </small>
        {note ? (
          <p className="muted" role="status">
            {note}
          </p>
        ) : null}
      </fieldset>
    </section>
  );
}
