"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  archiveTemplate,
  createTemplate,
  fillPlaceholders,
  importDocx,
  listTemplates,
  templateVersions,
  updateTemplate,
  type ContractKind,
  type ContractsMeta,
  type ContractTemplate,
} from "@/lib/contracts";
import { ContractText } from "./ContractText";
import { formatIst } from "./format";

/** Sample values for the live preview (the real ones are filled in when sending). */
const SAMPLE: Record<string, string> = {
  company_name: "KushAlaya Private Limited",
  company_address: "Hyderabad, Telangana",
  company_gstin: "36ABCDE1234F1Z5",
  date: "1 Nov 2026",
  start_date: "1 Nov 2026",
  end_date: "31 Oct 2027",
  signer_name: "Ravi Kumar",
  client_name: "Lakshmi Devi",
  client_address: "Banjara Hills, Hyderabad",
  client_phone: "98765 43210",
  plan_name: "Care Plus",
  plan_amount: "₹12,000",
  vendor_name: "Ramesh",
  vendor_company: "Sri Sai Plumbing",
  vendor_address: "Ameerpet, Hyderabad",
  vendor_gstin: "36ABCDE1234F1Z5",
  vendor_phone: "98480 12345",
  vendor_services: "Plumbing, Grab bar & safety installation",
  vendor_fee: "₹1,500 per visit",
};

type Draft = { id: number | null; kind: ContractKind; title: string; body: string };

export function TemplateEditor({ meta }: { meta: ContractsMeta }) {
  const canEdit = meta.can_sign;
  const [rows, setRows] = useState<ContractTemplate[] | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saved, setSaved] = useState<ContractTemplate | null>(null);
  const [versions, setVersions] = useState<ContractTemplate[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const area = useRef<HTMLTextAreaElement>(null);
  const file = useRef<HTMLInputElement>(null);

  const load = useCallback(async (selectId?: number) => {
    try {
      const r = await listTemplates(undefined, showArchived);
      setRows(r);
      const pick = r.find((t) => t.id === selectId) || (selectId === undefined ? r[0] : undefined);
      if (pick) open(pick);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load templates");
    }
  }, [showArchived]);

  useEffect(() => {
    void load();
  }, [load]);

  function open(t: ContractTemplate) {
    setSaved(t);
    setDraft({ id: t.id, kind: t.kind, title: t.title, body: t.body });
    setVersions(null);
    setNotice("");
    setError("");
  }

  const known = useMemo(() => new Set(meta.placeholders.map((p) => p.key)), [meta]);
  const cheat = meta.placeholders.filter((p) => !draft || p.kinds.includes(draft.kind));
  const dirty = !!draft && (!saved || draft.title !== saved.title || draft.body !== saved.body || draft.id === null);

  function insert(key: string) {
    if (!draft || !canEdit) return;
    const el = area.current;
    const token = `{${key}}`;
    const start = el?.selectionStart ?? draft.body.length;
    const end = el?.selectionEnd ?? start;
    const body = draft.body.slice(0, start) + token + draft.body.slice(end);
    setDraft({ ...draft, body });
    window.setTimeout(() => {
      el?.focus();
      el?.setSelectionRange(start + token.length, start + token.length);
    }, 0);
  }

  async function save() {
    if (!draft) return;
    setBusy(true);
    setError("");
    try {
      const t = draft.id === null ? await createTemplate(draft) : await updateTemplate(draft.id, draft);
      await load(t.id);
      setNotice(draft.id === null ? "Template added." : `Saved as version ${t.version}. Contracts already sent keep their text.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  async function onDocx(f: File | undefined) {
    if (!f || !draft) return;
    setBusy(true);
    setError("");
    try {
      const { text } = await importDocx(f);
      if (!text.trim()) throw new Error("No text found in that file.");
      if (draft.body.trim() && !window.confirm("Replace the current text with the text from the Word file?")) return;
      setDraft({ ...draft, body: text });
      setNotice("Text imported. Put {placeholders} where names, dates and amounts go, then Save.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not read that file");
    } finally {
      setBusy(false);
      if (file.current) file.current.value = "";
    }
  }

  async function toggleArchive() {
    if (!saved) return;
    setBusy(true);
    try {
      await archiveTemplate(saved.id, !saved.archived);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ct-editor">
      <aside className="ct-tlist card">
        <div className="ct-tlist-head">
          <h3>Templates</h3>
          {canEdit ? (
            <select
              aria-label="New template"
              value=""
              onChange={(e) => {
                const kind = e.target.value as ContractKind;
                if (!kind) return;
                setSaved(null);
                setVersions(null);
                setDraft({ id: null, kind, title: kind === "vendor" ? "Vendor agreement" : "Client service contract", body: "" });
              }}
            >
              <option value="">+ New…</option>
              {meta.kinds.map((k) => (
                <option key={k.code} value={k.code}>
                  {k.label}
                </option>
              ))}
            </select>
          ) : null}
        </div>
        {rows === null ? <p className="muted">Loading…</p> : null}
        <ul>
          {(rows || []).map((t) => (
            <li key={t.id}>
              <button type="button" className={`ct-tbtn${draft?.id === t.id ? " is-on" : ""}`} onClick={() => open(t)}>
                <strong>{t.title}</strong>
                <small>
                  {t.kind_label} · v{t.version}
                  {t.archived ? " · archived" : ""}
                  {t.is_placeholder ? " · placeholder" : ""}
                </small>
              </button>
            </li>
          ))}
        </ul>
        <label className="ct-check">
          <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} /> Show archived
        </label>
      </aside>

      {draft ? (
        <section className="ct-edit card">
          {error ? <p className="ks-modal-error" role="alert">{error}</p> : null}
          {notice ? <p className="ct-notice">{notice}</p> : null}
          {saved?.is_placeholder ? (
            <p className="ct-warn">Placeholder wording. Replace it with KushAlaya&apos;s own contract text (paste it, or import a Word file) before sending to real vendors or clients.</p>
          ) : null}
          <div className="ct-edit-grid">
            <div className="ct-form">
              <label>
                Title
                <input value={draft.title} maxLength={200} disabled={!canEdit} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
              </label>
              <label>
                Contract text
                <textarea
                  ref={area}
                  className="ct-body-input"
                  value={draft.body}
                  disabled={!canEdit}
                  spellCheck
                  onChange={(e) => setDraft({ ...draft, body: e.target.value })}
                  placeholder={"# Heading\n\nParagraph text with {placeholders}…"}
                />
              </label>
              <p className="muted ct-note">Start a line with # for a heading. Leave a blank line between paragraphs.</p>
              {canEdit ? (
                <div className="ct-actions ct-actions-left">
                  <button type="button" disabled={busy || !dirty} onClick={() => void save()}>
                    {busy ? "Saving…" : draft.id === null ? "Add template" : "Save new version"}
                  </button>
                  <label className="secondary ct-filebtn">
                    Import Word (.docx)
                    <input ref={file} type="file" accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(e) => void onDocx(e.target.files?.[0])} />
                  </label>
                  {saved ? (
                    <>
                      <button type="button" className="secondary" onClick={() => void templateVersions(saved.id).then(setVersions)}>
                        Versions
                      </button>
                      <button type="button" className="secondary" disabled={busy} onClick={() => void toggleArchive()}>
                        {saved.archived ? "Restore" : "Archive"}
                      </button>
                    </>
                  ) : null}
                </div>
              ) : (
                <p className="muted ct-note">Only an admin can change templates.</p>
              )}
              {versions ? (
                <div className="ct-versions">
                  <h4>Versions</h4>
                  <ul>
                    {versions.map((v) => (
                      <li key={v.id}>
                        v{v.version} · {formatIst(v.created_at)}
                        {v.created_by ? ` · ${v.created_by}` : ""}
                        {v.is_current ? " · current" : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
            <div className="ct-side">
              <div className="ct-cheat">
                <h4>Placeholders</h4>
                <p className="muted ct-note">{canEdit ? "Tap to insert at the cursor." : "Filled in when a contract is sent."}</p>
                <ul>
                  {cheat.map((p) => (
                    <li key={p.key}>
                      <button type="button" className="ct-ph" disabled={!canEdit} onClick={() => insert(p.key)} title={p.label}>
                        {`{${p.key}}`}
                      </button>
                      <span>{p.label}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4>Live preview <small className="muted">(sample details)</small></h4>
                <div className="ct-preview">
                  <ContractText title={fillPlaceholders(draft.title, SAMPLE, known)} body={fillPlaceholders(draft.body, SAMPLE, known)} />
                </div>
              </div>
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}
