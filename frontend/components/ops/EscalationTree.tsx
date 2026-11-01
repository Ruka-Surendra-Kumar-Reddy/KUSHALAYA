"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { EmailChips } from "@/components/EmailChips";

type Tree = {
  ack_minutes: number;
  level2_minutes: number;
  level3_minutes: number;
  level1_phones: string[];
  level2_emails: string[];
  level2_phones: string[];
};

/** Settings → SOS escalation: who is called, and when, if nobody answers an SOS. */
export function EscalationTree({ canEdit }: { canEdit: boolean }) {
  const [tree, setTree] = useState<Tree | null>(null);
  const [status, setStatus] = useState("");

  useEffect(() => {
    api<Tree>("/api/v1/team/escalation").then(setTree).catch(() => setStatus("Could not load"));
  }, []);

  async function save(patch: Partial<Tree>) {
    if (!tree) return;
    setTree({ ...tree, ...patch });
    setStatus("Saving…");
    try {
      setTree(await api<Tree>("/api/v1/team/escalation", { method: "PUT", body: JSON.stringify(patch) }));
      setStatus("Saved");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Could not save");
    }
  }

  if (!tree) return null;

  const minutes = (key: "ack_minutes" | "level2_minutes" | "level3_minutes") => (
    <select
      className="nt-min"
      value={tree[key]}
      disabled={!canEdit}
      aria-label="Minutes"
      onChange={(e) => void save({ [key]: Number(e.target.value) })}
    >
      {[2, 3, 5, 10, 15, 20, 30, 45, 60].map((m) => (
        <option key={m} value={m}>
          {m} min
        </option>
      ))}
    </select>
  );

  return (
    <section className="card nt-esc" aria-labelledby="nt-esc-title">
      <div className="ks-email-head">
        <h2 id="nt-esc-title">SOS escalation</h2>
        {status && <small aria-live="polite">{status}</small>}
      </div>
      <p className="muted">
        When a wearable SOS, fall or family SOS comes in, the family sees it at once. If nobody on your team presses{" "}
        <b>Acknowledge</b>, it climbs these steps.
      </p>
      <ol className="nt-ladder">
        <li>
          <div className="nt-step-head">
            <span className="nt-step-no">1</span>
            <strong>Not acknowledged after {minutes("ack_minutes")}</strong>
          </div>
          <p>Email the client’s care manager and all admins, plus the people under “SOS and safety alerts” below.</p>
          <span className="nt-who-label">Also SMS these phones</span>
          <EmailChips kind="phone" value={tree.level1_phones} disabled={!canEdit} onChange={(v) => void save({ level1_phones: v })} />
        </li>
        <li>
          <div className="nt-step-head">
            <span className="nt-step-no is-amber">2</span>
            <strong>Still not acknowledged after {minutes("level2_minutes")}</strong>
          </div>
          <p>Call in the back-up people — the owner, an on-call lead.</p>
          <span className="nt-who-label">Email</span>
          <EmailChips value={tree.level2_emails} disabled={!canEdit} onChange={(v) => void save({ level2_emails: v })} />
          <span className="nt-who-label">SMS</span>
          <EmailChips kind="phone" value={tree.level2_phones} disabled={!canEdit} onChange={(v) => void save({ level2_phones: v })} />
        </li>
        <li>
          <div className="nt-step-head">
            <span className="nt-step-no is-red">3</span>
            <strong>Still not acknowledged after {minutes("level3_minutes")}</strong>
          </div>
          <p>Repeat step 2 and mark the SOS as escalated on the dashboard.</p>
        </li>
      </ol>
      <p className="muted nt-foot">Checked every 2 minutes. SMS go out once MSG91 is connected above.</p>
    </section>
  );
}
