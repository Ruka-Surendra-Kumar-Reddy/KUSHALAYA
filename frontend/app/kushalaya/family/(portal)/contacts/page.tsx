"use client";

import { useEffect, useState } from "react";
import { FamilyShell } from "@/components/livewell/family/FamilyShell";
import { FamilyError } from "@/components/livewell/family/FamilyError";
import {
  fetchEmergencyContacts,
  fetchFamilyCircle,
  fetchFamilyDashboard,
  type EmergencyContact,
} from "@/lib/livewell/familyApi";
import { contactsToCall } from "@/lib/livewell/familyStatus";

export default function FamilyContactsPage() {
  const [contacts, setContacts] = useState<EmergencyContact[]>([]);
  const [error, setError] = useState("");
  const [senior, setSenior] = useState("");
  const [primary, setPrimary] = useState(false);

  function load() {
    setError("");
    // The senior is never listed as their own "local person to call".
    Promise.all([fetchEmergencyContacts(), fetchFamilyDashboard().catch(() => null)])
      .then(([rows, d]) => {
        const name = d?.senior_name || "";
        setSenior(name);
        setContacts(contactsToCall(rows, name));
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
    fetchFamilyCircle()
      .then((m) => setPrimary(!!m.find((x) => x.is_you)?.is_primary))
      .catch(() => undefined);
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <FamilyShell title="Emergency contacts" subtitle="Local people to call. Tap to call.">
      <FamilyError message={error} onRetry={load} what="the contacts" />
      {contacts.length === 0 ? (
        <div className="card home-safety-empty">
          <p>No local person to call is on file yet.</p>
          <p className="muted">
            {primary
              ? "Add a neighbour or a doctor: send their name and number to your care team in Messages and they will add it."
              : `Ask ${senior.split(" ")[0] || "the main family member"} to add a neighbour or a doctor.`}
          </p>
        </div>
      ) : (
        <ul className="home-safety-family-contact-list">
          {contacts.map((c) => (
            <li key={`${c.name}-${c.phone}`} className="card home-safety-family-contact">
              <div>
                <strong>{c.name}</strong>
                {c.is_primary && (
                  <span className="home-safety-saved-badge" style={{ marginLeft: "0.5rem" }}>
                    Primary
                  </span>
                )}
                {c.relationship && (
                  <p className="muted" style={{ fontSize: "0.85rem", margin: "0.25rem 0 0" }}>
                    {c.relationship}
                  </p>
                )}
                {c.phone ? (
                  <p className="fh-contact-phone">
                    <a href={`tel:${c.phone.replace(/\s/g, "")}`}>{c.phone}</a>
                  </p>
                ) : null}
              </div>
              {c.phone ? (
                <a href={`tel:${c.phone.replace(/\s/g, "")}`} className="home-safety-family-call fh-call-44"
                  aria-label={`Call ${c.name}`}
                >
                  Call
                </a>
              ) : (
                <span className="muted">No phone</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </FamilyShell>
  );
}
