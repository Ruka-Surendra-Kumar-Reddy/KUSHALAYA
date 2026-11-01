"use client";

import { useState } from "react";
import { saveSignatory, type Signatory } from "@/lib/contracts";
import { SignaturePad, SignatureView, type SignatureValue } from "./SignaturePad";

/**
 * An admin's signature for KushAlaya: name, designation and a drawn or typed signature.
 * Saved once, then applied by every "Sign & send".
 */
export function SignatorySetup({
  current,
  defaultName,
  onSaved,
  onCancel,
}: {
  current: Signatory | null;
  defaultName: string;
  onSaved: (s: Signatory) => void;
  onCancel?: () => void;
}) {
  const [editing, setEditing] = useState(!current);
  const [name, setName] = useState(current?.name || defaultName);
  const [designation, setDesignation] = useState(current?.designation || "");
  const [sig, setSig] = useState<SignatureValue>({ png: null, text: null });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (current && !editing) {
    return (
      <div className="ct-signatory">
        <div className="ct-sigbox">
          <SignatureView png={current.signature_png} text={current.signature_text} />
          <p>
            <strong>{current.name}</strong>
            <br />
            <span className="muted">{current.designation}</span>
          </p>
        </div>
        <button type="button" className="secondary" onClick={() => setEditing(true)}>
          Change signature
        </button>
      </div>
    );
  }

  async function save() {
    setError("");
    if (!designation.trim()) return setError("Add your designation, e.g. Director.");
    if (!sig.png && !sig.text) return setError("Draw your signature or type it.");
    setBusy(true);
    try {
      const s = await saveSignatory({ name, designation, signature_png: sig.png, signature_text: sig.text });
      setEditing(false);
      onSaved(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ct-signatory ct-form">
      <p className="muted ct-note">
        You sign for KushAlaya as an authorised signatory. Your signature is saved and added to each contract you
        send; the time, your IP address and the text&apos;s fingerprint are recorded each time.
      </p>
      {error ? <p className="ks-modal-error" role="alert">{error}</p> : null}
      <div className="ct-grid2">
        <label>
          Full name
          <input value={name} maxLength={200} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          Designation
          <input value={designation} maxLength={120} placeholder="e.g. Director" onChange={(e) => setDesignation(e.target.value)} />
        </label>
      </div>
      <SignaturePad onChange={setSig} defaultTyped={name} label="Your signature" />
      <div className="ct-actions">
        {onCancel || current ? (
          <button type="button" className="secondary" disabled={busy} onClick={() => (current ? setEditing(false) : onCancel?.())}>
            Cancel
          </button>
        ) : null}
        <button type="button" disabled={busy} onClick={() => void save()}>
          {busy ? "Saving…" : "Save my signature"}
        </button>
      </div>
    </div>
  );
}
