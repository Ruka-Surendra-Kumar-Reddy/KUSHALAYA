"use client";

import { FormEvent, useRef, useState } from "react";
import { api, getApiUrl, getStoredAuth, postFormData } from "@/lib/api";
import { can, isAdmin as isAdminUser } from "@/lib/roles";
import { stripAssessmentIdSuffix } from "@/lib/livewell/assessmentDisplay";
import { useAuthedImage } from "@/components/useAuthedImage";

type Doc = {
  id: number;
  document_type: string;
  name: string;
  mime_type: string | null;
  uploaded_at: string | null;
  is_photo: boolean;
};

/** Vault categories. Everything except "Staff only" also shows in the family portal. */
const KINDS: { code: string; label: string; family: boolean }[] = [
  { code: "LW_FAMILY_MEDICAL", label: "Medical record / report", family: true },
  { code: "LW_FAMILY_PRESCRIPTION", label: "Prescription", family: true },
  { code: "LW_FAMILY_INSURANCE", label: "Insurance", family: true },
  { code: "LW_FAMILY_IDENTITY", label: "ID proof", family: true },
  { code: "LW_SERVICE_AGREEMENT", label: "Service agreement (signed)", family: true },
  { code: "LW_QUOTE_ACCEPTANCE", label: "Quote acceptance", family: true },
  { code: "LW_WORK_COMPLETION_CERT", label: "Work completion certificate", family: true },
  { code: "LW_EMERGENCY_INFO_SHEET", label: "Emergency info sheet", family: true },
  { code: "LW_FAMILY_OTHER", label: "Other — shared with family", family: true },
  { code: "LW_STAFF_ONLY", label: "Staff only (family can’t see)", family: false },
];
const LABEL = Object.fromEntries(KINDS.map((k) => [k.code, k.label]));
const FAMILY_SEES = new Set(
  KINDS.filter((k) => k.family).map((k) => k.code).concat(["HOME_SAFETY_SIGNED_DOC", "LW_PRIVACY_DPDP_CONSENT",
    "LW_PHOTO_VIDEO_AI_CONSENT", "LW_HEALTH_EMERGENCY_AUTH", "LW_HOME_ASSESSMENT_CONSENT"]),
);
const MAX_MB = 10;

function niceType(code: string) {
  if (LABEL[code]) return LABEL[code];
  const t = code.replace(/^LW_|^HOME_SAFETY_/, "").replace(/_/g, " ").toLowerCase();
  return (t.charAt(0).toUpperCase() + t.slice(1)).replace(/^Ai\b/, "AI");
}

/** A real thumbnail for photos (loaded with the sign-in token), a file badge otherwise. */
function DocThumb({ d }: { d: Doc }) {
  const src = useAuthedImage(d.is_photo ? `/api/v1/documents/${d.id}/download` : null);
  if (d.is_photo && src) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img className="cd-thumb" src={src} alt="" loading="lazy" />;
  }
  const ext = (d.name.split(".").pop() || "").slice(0, 4).toUpperCase();
  return (
    <span className={`cd-ico${d.is_photo ? " is-photo" : ""}`} aria-hidden="true">
      {d.is_photo ? "" : ext && ext.length <= 4 && ext !== d.name.toUpperCase() ? ext : "DOC"}
    </span>
  );
}

/** File name without the storage ids: "12_9f3c2a1b_report.pdf" → "report.pdf", "lwa-1712345678-x.pdf" → "x.pdf". */
export function niceDocName(name: string): string {
  const cleaned = stripAssessmentIdSuffix(name || "")
    .replace(/^(?:(?:\d+|[0-9a-f]{8,}(?:-[0-9a-f]{4,})*|lwa[-_][0-9a-z]+)[-_ ]+)+/i, "")
    .replace(/[-_ ]+(?:[0-9a-f]{8,}(?:-[0-9a-f]{4,})*|\d{10,})(?=\.[a-z0-9]+$|$)/i, "")
    .replace(/\s*#\d+\b/g, "")
    .trim()
    .replace(/^ai\b/i, "AI");
  return cleaned || name;
}

/** Client profile → Documents: the client's vault (upload, download, delete). */
export function ClientDocuments({
  elderId,
  docs,
  onChanged,
  day,
}: {
  elderId: number;
  docs: Doc[];
  onChanged: () => void;
  day: (iso?: string | null) => string;
}) {
  const isAdmin = isAdminUser();
  const fileRef = useRef<HTMLInputElement>(null);
  const [kind, setKind] = useState(KINDS[0].code);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const all = docs.filter((d) => d.document_type !== "HOME_SAFETY_PHOTO");
  // Re-runs (same name, type and day — e.g. four identical AI concepts) show once, newest first.
  const [showRepeats, setShowRepeats] = useState(false);
  const repeatsOf = new Map<number, number>();
  const seen = new Map<string, number>();
  const newestFirst = [...all].sort((a, b) => String(b.uploaded_at || "").localeCompare(String(a.uploaded_at || "")));
  const files = newestFirst.filter((d) => {
    const key = `${niceDocName(d.name)}|${d.document_type}|${day(d.uploaded_at)}`;
    const keeper = seen.get(key);
    if (keeper === undefined) {
      seen.set(key, d.id);
      return true;
    }
    repeatsOf.set(keeper, (repeatsOf.get(keeper) || 0) + 1);
    return showRepeats;
  });
  const repeatCount = Array.from(repeatsOf.values()).reduce((n, v) => n + v, 0);

  async function upload(e: FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return setMsg({ ok: false, text: "Choose a file first." });
    if (file.size > MAX_MB * 1024 * 1024) return setMsg({ ok: false, text: `Files up to ${MAX_MB} MB.` });
    const fd = new FormData();
    fd.append("entity_type", "elder");
    fd.append("entity_id", String(elderId));
    fd.append("document_type", kind);
    fd.append("file", file);
    setBusy(true);
    try {
      await postFormData("/api/v1/documents/upload", fd);
      setMsg({ ok: true, text: `${file.name} saved${FAMILY_SEES.has(kind) ? " — the family can see it" : " — staff only"}.` });
      if (fileRef.current) fileRef.current.value = "";
      onChanged();
    } catch (err) {
      setMsg({ ok: false, text: err instanceof Error ? err.message : "Upload failed" });
    } finally {
      setBusy(false);
    }
  }

  async function download(d: Doc) {
    const auth = getStoredAuth();
    const res = await fetch(`${getApiUrl()}/api/v1/documents/${d.id}/download`, {
      headers: auth?.access_token ? { Authorization: `Bearer ${auth.access_token}` } : {},
    });
    if (!res.ok) return setMsg({ ok: false, text: "Could not download" });
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = d.name || "document";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  async function remove(d: Doc) {
    if (!window.confirm(`Delete ${d.name}? This can’t be undone.`)) return;
    try {
      await api(`/api/v1/documents/${d.id}`, { method: "DELETE" });
      setMsg({ ok: true, text: `${d.name} deleted.` });
      onChanged();
    } catch (err) {
      setMsg({ ok: false, text: err instanceof Error ? err.message : "Could not delete" });
    }
  }

  return (
    <div className="cd-vault">
      {can("edit") ? (
      <form className="cd-upload" onSubmit={(e) => void upload(e)}>
        <label>
          File (PDF or photo, up to {MAX_MB} MB)
          <input ref={fileRef} type="file" accept="application/pdf,image/jpeg,image/png,image/webp" />
        </label>
        <label>
          What is it?
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            {KINDS.map((k) => (
              <option key={k.code} value={k.code}>
                {k.label}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={busy}>
          {busy ? "Uploading…" : "Upload"}
        </button>
      </form>
      ) : null}
      {msg && <p className={`cd-msg${msg.ok ? " is-ok" : " is-bad"}`}>{msg.text}</p>}

      {repeatCount ? (
        <button type="button" className="cp-linkbtn cd-repeats" onClick={() => setShowRepeats((v) => !v)}>
          {showRepeats ? "Hide earlier versions" : `Show ${repeatCount} earlier version${repeatCount === 1 ? "" : "s"}`}
        </button>
      ) : null}
      {files.length === 0 ? (
        <p className="muted">No documents yet. Signed agreements, prescriptions and reports go here.</p>
      ) : (
        <ul className="cd-list">
          {files.map((d) => (
            <li key={d.id}>
              <DocThumb d={d} />
              <span className="cd-name">
                <strong title={d.name}>{niceDocName(d.name)}</strong>
                <small>
                  {niceType(d.document_type)} · {day(d.uploaded_at)}
                  {!showRepeats && repeatsOf.get(d.id) ? ` · +${repeatsOf.get(d.id)} earlier version${repeatsOf.get(d.id) === 1 ? "" : "s"}` : ""}
                </small>
              </span>
              <span className={`cd-seen${FAMILY_SEES.has(d.document_type) ? " is-family" : ""}`}>
                {FAMILY_SEES.has(d.document_type) ? "Family can see" : "Staff only"}
              </span>
              <button type="button" className="secondary cp-inline-btn" onClick={() => void download(d)}>
                Download
              </button>
              {isAdmin && (
                <button type="button" className="secondary cp-inline-btn cd-del" onClick={() => void remove(d)}>
                  Delete
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
