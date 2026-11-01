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
import { detailLabel, fromFriendly, fromSections, toFriendly, toSections, type Section } from "./templateSections";

/** Sample values for the live preview (the real ones are filled in when sending). */
const SAMPLE: Record<string, string> = {
  company_name: "KushAlaya Private Limited",
  company_address: "Uppal, Hyderabad, Telangana",
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
  vendor_services: "Plumbing, grab bar and safety installation",
  vendor_fee: "₹1,500 per visit",
};

type Draft = { id: number | null; kind: ContractKind; title: string; sections: Section[] };

/**
 * Agreement templates, edited in plain words: each section is a title and its text,
 * and details such as the vendor's name are [Vendor company] tags picked from a menu.
 * Stored as before ("# Heading" lines and {keys}), so sending and the PDF are unchanged.
 */
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
  const [view, setView] = useState<"edit" | "preview">("edit");
  const texts = useRef<Record<number, HTMLTextAreaElement | null>>({});
  const file = useRef<HTMLInputElement>(null);

  const known = useMemo(() => new Set(meta.placeholders.map((p) => p.key)), [meta]);

  const open = useCallback(
    (t: ContractTemplate) => {
      setSaved(t);
      setDraft({
        id: t.id,
        kind: t.kind,
        title: toFriendly(t.title, known),
        sections: toSections(t.body).map((s) => ({ heading: toFriendly(s.heading, known), text: toFriendly(s.text, known) })),
      });
      setVersions(null);
      setNotice("");
      setError("");
      setView("edit");
    },
    [known],
  );

  const load = useCallback(
    async (selectId?: number) => {
      try {
        const r = await listTemplates(undefined, showArchived);
        setRows(r);
        const pick = r.find((t) => t.id === selectId) || (selectId === undefined ? r[0] : undefined);
        if (pick) open(pick);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load templates");
      }
    },
    [showArchived, open],
  );

  useEffect(() => {
    void load();
  }, [load]);

  /** What will be saved, in the stored form. */
  const stored = useMemo(() => {
    if (!draft) return null;
    return {
      title: fromFriendly(draft.title, known),
      body: fromSections(draft.sections.map((s) => ({ heading: fromFriendly(s.heading, known), text: fromFriendly(s.text, known) }))),
    };
  }, [draft, known]);

  const details = meta.placeholders.filter((p) => !draft || p.kinds.includes(draft.kind));
  const dirty = !!draft && !!stored && (!saved || draft.id === null || stored.title !== saved.title || stored.body.trim() !== saved.body.trim());

  function setSection(i: number, patch: Partial<Section>) {
    if (!draft) return;
    setDraft({ ...draft, sections: draft.sections.map((s, k) => (k === i ? { ...s, ...patch } : s)) });
  }

  function addSection(after: number) {
    if (!draft) return;
    const next = [...draft.sections];
    next.splice(after + 1, 0, { heading: "", text: "" });
    setDraft({ ...draft, sections: next });
    window.setTimeout(() => texts.current[after + 1]?.focus(), 0);
  }

  function moveSection(i: number, dir: -1 | 1) {
    if (!draft) return;
    const j = i + dir;
    if (j < 0 || j >= draft.sections.length) return;
    const next = [...draft.sections];
    [next[i], next[j]] = [next[j], next[i]];
    setDraft({ ...draft, sections: next });
  }

  function removeSection(i: number) {
    if (!draft) return;
    const s = draft.sections[i];
    if ((s.heading.trim() || s.text.trim()) && !window.confirm(`Remove the section "${s.heading || "untitled"}"?`)) return;
    const next = draft.sections.filter((_, k) => k !== i);
    setDraft({ ...draft, sections: next.length ? next : [{ heading: "", text: "" }] });
  }

  function insertDetail(i: number, key: string) {
    if (!draft || !key) return;
    const el = texts.current[i];
    const token = `[${detailLabel(key)}]`;
    const cur = draft.sections[i].text;
    const start = el?.selectionStart ?? cur.length;
    const end = el?.selectionEnd ?? start;
    setSection(i, { text: cur.slice(0, start) + token + cur.slice(end) });
    window.setTimeout(() => {
      el?.focus();
      el?.setSelectionRange(start + token.length, start + token.length);
    }, 0);
  }

  async function save() {
    if (!draft || !stored) return;
    if (!stored.title.trim()) return setError("Give the template a name.");
    if (!stored.body.trim()) return setError("Write at least one section.");
    setBusy(true);
    setError("");
    try {
      const t =
        draft.id === null
          ? await createTemplate({ kind: draft.kind, title: stored.title, body: stored.body })
          : await updateTemplate(draft.id, stored);
      await load(t.id);
      setNotice(draft.id === null ? "Template added." : `Saved. Agreements already sent keep their own text.`);
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
      const hasText = draft.sections.some((s) => s.heading.trim() || s.text.trim());
      if (hasText && !window.confirm("Replace the current sections with the text from the Word file?")) return;
      setDraft({ ...draft, sections: toSections(text).map((s) => ({ heading: toFriendly(s.heading, known), text: toFriendly(s.text, known) })) });
      setNotice("Word file loaded. Check each section, add details from the menu, then Save.");
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

  function startNew(kind: ContractKind) {
    setSaved(null);
    setVersions(null);
    setNotice("");
    setError("");
    setView("edit");
    setDraft({
      id: null,
      kind,
      title: kind === "vendor" ? "Vendor agreement" : "Client service contract",
      sections: [{ heading: "Parties", text: "" }],
    });
  }

  return (
    <div className="ct-editor">
      <aside className="ct-tlist card">
        <div className="ct-tlist-head">
          <h3>Templates</h3>
        </div>
        {canEdit ? (
          <div className="ct-new">
            {meta.kinds.map((k) => (
              <button key={k.code} type="button" className="secondary" onClick={() => startNew(k.code)}>
                + New {k.label.toLowerCase()}
              </button>
            ))}
          </div>
        ) : null}
        {rows === null ? <p className="muted">Loading…</p> : null}
        <ul>
          {(rows || []).map((t) => (
            <li key={t.id}>
              <button type="button" className={`ct-tbtn${draft?.id === t.id ? " is-on" : ""}`} onClick={() => open(t)}>
                <strong>{t.title}</strong>
                <small>
                  {t.kind_label}
                  {t.archived ? " · archived" : ""}
                  {t.is_placeholder ? " · example text" : ""}
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
            <p className="ct-warn">
              This is example wording. Change it to your own agreement (or load your Word file) before sending it to a real
              vendor or client.
            </p>
          ) : null}

          <label className="ct-title-field">
            Template name
            <input value={draft.title} maxLength={200} disabled={!canEdit} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
          </label>

          <div className="ct-viewtabs" role="tablist" aria-label="Edit or preview">
            <button type="button" role="tab" aria-selected={view === "edit"} className={view === "edit" ? "is-on" : ""} onClick={() => setView("edit")}>
              Edit
            </button>
            <button type="button" role="tab" aria-selected={view === "preview"} className={view === "preview" ? "is-on" : ""} onClick={() => setView("preview")}>
              Preview
            </button>
          </div>

          <div className={`ct-edit-grid is-${view}`}>
            <div className="ct-sections">
              {draft.sections.map((s, i) => (
                <div key={i} className="ct-sec">
                  <div className="ct-sec-head">
                    <span className="ct-sec-n">{i + 1}</span>
                    <input
                      className="ct-sec-title"
                      value={s.heading}
                      disabled={!canEdit}
                      placeholder="Section title, e.g. Fees"
                      aria-label={`Section ${i + 1} title`}
                      onChange={(e) => setSection(i, { heading: e.target.value })}
                    />
                    {canEdit ? (
                      <span className="ct-sec-tools">
                        <button type="button" className="ct-icon" onClick={() => moveSection(i, -1)} disabled={i === 0} aria-label="Move up" title="Move up">
                          ↑
                        </button>
                        <button
                          type="button"
                          className="ct-icon"
                          onClick={() => moveSection(i, 1)}
                          disabled={i === draft.sections.length - 1}
                          aria-label="Move down"
                          title="Move down"
                        >
                          ↓
                        </button>
                        <button type="button" className="ct-icon ct-icon-del" onClick={() => removeSection(i)} aria-label="Remove section" title="Remove section">
                          ✕
                        </button>
                      </span>
                    ) : null}
                  </div>
                  <textarea
                    ref={(el) => {
                      texts.current[i] = el;
                    }}
                    className="ct-sec-text"
                    value={s.text}
                    disabled={!canEdit}
                    spellCheck
                    rows={Math.min(14, Math.max(3, s.text.split("\n").length + 1))}
                    placeholder="Write this part of the agreement…"
                    aria-label={`Section ${i + 1} text`}
                    onChange={(e) => setSection(i, { text: e.target.value })}
                  />
                  {canEdit ? (
                    <div className="ct-sec-foot">
                      <select aria-label="Insert a detail" value="" onChange={(e) => insertDetail(i, e.target.value)}>
                        <option value="">Insert a detail…</option>
                        {details.map((p) => (
                          <option key={p.key} value={p.key}>
                            {detailLabel(p.key)}
                          </option>
                        ))}
                      </select>
                      <button type="button" className="ct-link" onClick={() => addSection(i)}>
                        + Add section below
                      </button>
                    </div>
                  ) : null}
                </div>
              ))}
              {canEdit ? (
                <p className="muted ct-note">
                  Details in [square brackets] are filled in automatically from the vendor or client when you send the agreement.
                </p>
              ) : (
                <p className="muted ct-note">Only an admin can change templates.</p>
              )}
            </div>

            <div className="ct-side">
              <h4>
                Preview <small className="muted">with example details</small>
              </h4>
              <div className="ct-preview">
                <ContractText title={fillPlaceholders(stored?.title || "", SAMPLE, known)} body={fillPlaceholders(stored?.body || "", SAMPLE, known)} />
              </div>
            </div>
          </div>

          {canEdit ? (
            <div className="ct-actions ct-actions-left ct-savebar">
              <button type="button" disabled={busy || !dirty} onClick={() => void save()}>
                {busy ? "Saving…" : draft.id === null ? "Save template" : dirty ? "Save changes" : "Saved"}
              </button>
              <label className="secondary ct-filebtn">
                Load from Word (.docx)
                <input
                  ref={file}
                  type="file"
                  accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={(e) => void onDocx(e.target.files?.[0])}
                />
              </label>
              {saved ? (
                <>
                  <button type="button" className="secondary" onClick={() => void templateVersions(saved.id).then(setVersions)}>
                    History
                  </button>
                  <button type="button" className="secondary" disabled={busy} onClick={() => void toggleArchive()}>
                    {saved.archived ? "Restore" : "Archive"}
                  </button>
                </>
              ) : null}
            </div>
          ) : null}

          {versions ? (
            <div className="ct-versions">
              <h4>History</h4>
              <ul>
                {versions.map((v) => (
                  <li key={v.id}>
                    Version {v.version} · {formatIst(v.created_at)}
                    {v.created_by ? ` · ${v.created_by}` : ""}
                    {v.is_current ? " · in use" : ""}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
