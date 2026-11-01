"use client";

import { useEffect, useMemo, useState } from "react";
import {
  contractsMeta,
  createContract,
  listTemplates,
  previewContract,
  type Contract,
  type ContractKind,
  type ContractsMeta,
  type ContractTemplate,
  type Preview,
} from "@/lib/contracts";
import { ContractText } from "./ContractText";
import { ContractLinkActions } from "./ContractsPanel";
import { SignatorySetup } from "./SignatorySetup";

type Party = { kind: ContractKind; elderId?: number; vendorId?: number; partyName: string };

/** Drawer: pick a template → fill fields → choose signer → Sign & send (admin) or send for KushAlaya signature. */
export function SendContract({ party, onClose, onDone }: { party: Party; onClose: () => void; onDone: () => void }) {
  const [meta, setMeta] = useState<ContractsMeta | null>(null);
  const [templates, setTemplates] = useState<ContractTemplate[] | null>(null);
  const [templateId, setTemplateId] = useState(0);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [signer, setSigner] = useState({ name: "", email: "", mobile: "", relation: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [settingUp, setSettingUp] = useState(false);
  const [done, setDone] = useState<Contract | null>(null);

  const ref = useMemo(() => (party.elderId ? { elder_id: party.elderId } : { vendor_id: party.vendorId }), [party]);
  const labels = useMemo(() => Object.fromEntries((meta?.placeholders || []).map((p) => [p.key, p.label])), [meta]);

  useEffect(() => {
    contractsMeta().then(setMeta).catch(() => undefined);
    listTemplates(party.kind)
      .then((t) => {
        setTemplates(t);
        if (t[0]) setTemplateId(t[0].id);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load templates"));
  }, [party.kind]);

  // Preview: on template change, and shortly after a field or the signer name changes.
  useEffect(() => {
    if (!templateId) return;
    const t = window.setTimeout(() => {
      previewContract({ ...ref, template_id: templateId, signer_name: signer.name, fields })
        .then((p) => {
          setPreview(p);
          setSigner((s) => (s.name || !p.suggested_signers[0] ? s : { ...p.suggested_signers[0] }));
        })
        .catch((e) => setError(e instanceof Error ? e.message : "Could not fill the template"));
    }, 300);
    return () => window.clearTimeout(t);
  }, [templateId, fields, signer.name, ref]);

  const canSign = !!meta?.can_sign;
  const hasSignature = !!meta?.signatory;

  async function submit(action: "draft" | "submit" | "sign_and_send") {
    setError("");
    if (!signer.name.trim()) return setError("Add the name of the person who signs.");
    if (action !== "draft" && !signer.email.trim() && !signer.mobile.trim())
      return setError("Add the signer's email or mobile so the link can reach them.");
    if (action === "sign_and_send" && !hasSignature) return setSettingUp(true);
    setBusy(true);
    try {
      const c = await createContract({
        ...ref,
        template_id: templateId,
        signer_name: signer.name,
        signer_email: signer.email || null,
        signer_mobile: signer.mobile || null,
        signer_relation: signer.relation || null,
        fields,
        action,
      });
      setDone(c);
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create the contract");
    } finally {
      setBusy(false);
    }
  }

  const myName = meta?.my_name || "";

  return (
    <>
      <div className="ks-side-drawer-scrim" onMouseDown={onClose} />
      <aside className="ks-side-drawer ct-drawer" role="dialog" aria-modal="true" aria-label="Send contract">
        <header className="ks-side-drawer-head">
          <h2>{party.kind === "vendor" ? "Send agreement" : "Send contract"}</h2>
          <button type="button" className="secondary ct-x" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>
        <p className="muted ct-sub">{party.partyName}</p>
        {error ? <p className="ks-modal-error" role="alert">{error}</p> : null}

        {done ? (
          <div className="ct-done">
            <p className={`ct-pill is-${done.status}`}>{done.status === "sent" ? "Signed by KushAlaya and sent" : done.status === "awaiting_company" ? "Waiting for KushAlaya signature" : "Saved as draft"}</p>
            {done.status === "sent" ? (
              <>
                <p>
                  {done.signer_email ? `Emailed to ${done.signer_email}. ` : ""}
                  Share the link on WhatsApp too — it works for {meta?.link_days ?? 30} days.
                </p>
                <ContractLinkActions c={done} />
              </>
            ) : done.status === "awaiting_company" ? (
              <p>An admin has been asked to sign it for KushAlaya. The link goes out once they sign.</p>
            ) : null}
            <div className="ct-actions">
              <button type="button" onClick={onClose}>
                Done
              </button>
            </div>
          </div>
        ) : settingUp ? (
          <>
            <h3 className="ct-h3">Your signature for KushAlaya</h3>
            <SignatorySetup
              current={null}
              defaultName={myName}
              onCancel={() => setSettingUp(false)}
              onSaved={(s) => {
                setMeta((m) => (m ? { ...m, signatory: s } : m));
                setSettingUp(false);
              }}
            />
          </>
        ) : (
          <div className="ct-form">
            <label>
              Template
              <select value={templateId} onChange={(e) => setTemplateId(Number(e.target.value))}>
                {(templates || []).map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title} (v{t.version}){t.is_placeholder ? " — placeholder wording" : ""}
                  </option>
                ))}
              </select>
            </label>
            {templates && templates.length === 0 ? <p className="muted">No templates yet. Add one under Contracts → Templates.</p> : null}

            <h3 className="ct-h3">Who signs</h3>
            {preview?.suggested_signers.length ? (
              <div className="ct-chips" aria-label="Suggested signers">
                {preview.suggested_signers.map((s, i) => (
                  <button key={i} type="button" className={`ct-chip${s.name === signer.name ? " is-on" : ""}`} onClick={() => setSigner({ ...s })}>
                    {s.name} <small>{s.relation}</small>
                  </button>
                ))}
              </div>
            ) : null}
            <div className="ct-grid2">
              <label>
                Name *
                <input value={signer.name} maxLength={200} onChange={(e) => setSigner({ ...signer, name: e.target.value })} />
              </label>
              <label>
                Relation / role
                <input value={signer.relation} maxLength={60} placeholder="Son, Owner…" onChange={(e) => setSigner({ ...signer, relation: e.target.value })} />
              </label>
              <label>
                Email
                <input type="email" value={signer.email} onChange={(e) => setSigner({ ...signer, email: e.target.value })} />
              </label>
              <label>
                Mobile (WhatsApp)
                <input type="tel" value={signer.mobile} onChange={(e) => setSigner({ ...signer, mobile: e.target.value })} />
              </label>
            </div>

            {preview && Object.keys(preview.fields).length ? (
              <details className="ct-fields" open={preview.missing.length > 0}>
                <summary>
                  Filled-in details{preview.missing.length ? ` · ${preview.missing.length} to add` : ""}
                </summary>
                <div className="ct-grid2">
                  {Object.entries(preview.fields).map(([k, v]) => (
                    <label key={k}>
                      {labels[k] || k}
                      <input
                        value={fields[k] ?? v}
                        className={!v && !fields[k] ? "is-missing" : ""}
                        onChange={(e) => setFields({ ...fields, [k]: e.target.value })}
                      />
                    </label>
                  ))}
                </div>
              </details>
            ) : null}

            <h3 className="ct-h3">Preview</h3>
            <div className="ct-preview" aria-label="Contract preview">
              {preview ? <ContractText title={preview.title} body={preview.body} /> : <p className="muted">Filling in the template…</p>}
            </div>

            <div className="ct-actions ct-actions-sticky">
              <button type="button" className="secondary" disabled={busy || !preview} onClick={() => void submit("draft")}>
                Save draft
              </button>
              {canSign ? (
                <button type="button" disabled={busy || !preview} onClick={() => void submit("sign_and_send")}>
                  {busy ? "Signing…" : hasSignature ? "Sign & send" : "Set up signature to sign"}
                </button>
              ) : (
                <button type="button" disabled={busy || !preview} onClick={() => void submit("submit")}>
                  {busy ? "Sending…" : "Send for KushAlaya signature"}
                </button>
              )}
            </div>
            {canSign && hasSignature ? (
              <p className="muted ct-note">
                Signs for KushAlaya as {meta?.signatory?.name}, {meta?.signatory?.designation}, then sends the link. The text is
                locked once signed.
              </p>
            ) : !canSign ? (
              <p className="muted ct-note">An admin signs for KushAlaya first; then the link goes to the signer.</p>
            ) : null}
          </div>
        )}
      </aside>
    </>
  );
}
