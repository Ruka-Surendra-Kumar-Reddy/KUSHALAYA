"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { fieldJobBase, isFieldStaff, uploadFieldPhoto, type CareJob } from "@/lib/jobs";
import { KushLifeCaptureForm } from "@/components/KushLifeCapture";
import { VoiceNoteRecorder } from "@/components/kushlife/VoiceNoteRecorder";
import { emptyCapture, missingAnswers, toPayload } from "@/lib/kushlife";
import { optionalLocation, requireLocation, type LocationPayload } from "@/lib/visit-location";
import { LocationNeeded } from "./LocationNeeded";
import "./caregiver.css";

/**
 * Finishing a visit or install: the KushLife check, a note for the family,
 * photos, and an optional new hazard (which goes to the manager as "spotted").
 */
export function VisitReportSheet({ job, onDone, onClose }: { job: CareJob; onDone: (msg: string) => void; onClose: () => void }) {
  const [kl, setKl] = useState(emptyCapture);
  const [note, setNote] = useState("");
  const [photos, setPhotos] = useState(0);
  const [hazardOn, setHazardOn] = useState(false);
  const [hazardNote, setHazardNote] = useState("");
  const [hazardProduct, setHazardProduct] = useState("");
  const [products, setProducts] = useState<{ id: number; name: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // Per-client checklist (#99): id → done / not done + reason.
  const [ticks, setTicks] = useState<Record<string, { done: boolean; reason: string }>>({});
  const checklist = job.checklist ?? [];
  // Unticked checklist items waiting for "Finish anyway?" (in the sheet, not a browser dialog).
  const [unticked, setUnticked] = useState<string[] | null>(null);
  const [leaving, setLeaving] = useState(false);
  const [locNeed, setLocNeed] = useState(false);
  const camera = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api<{ id: number; name: string }[]>(isFieldStaff() ? "/api/v1/products" : "/api/v1/caregiver-portal/products")
      .then((rows) => setProducts(rows.map((r) => ({ id: r.id, name: r.name }))))
      .catch(() => undefined);
  }, []);

  async function addPhoto(file?: File) {
    if (!file) return;
    try {
      const r = await uploadFieldPhoto(job.id, file, "visit");
      setPhotos(r.count);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Photo upload failed");
    } finally {
      if (camera.current) camera.current.value = "";
    }
  }

  async function submit(anyway = false) {
    const missing = missingAnswers(kl);
    if (missing.length) {
      setError(`Please answer: ${missing.join(", ")}.`);
      return;
    }
    // Unticked checklist items: ask, don't block (KushLife is the hard requirement).
    const open = checklist.filter((i) => !ticks[i.id]);
    if (open.length && !anyway) {
      setUnticked(open.map((i) => i.label));
      return;
    }
    setUnticked(null);
    setBusy(true);
    setError("");
    setLocNeed(false);
    // Where the visit was finished: required in the caregiver app; ops staff send it if the browser gives one.
    let where: LocationPayload | null = null;
    if (isFieldStaff()) {
      where = await optionalLocation();
    } else {
      try {
        where = await requireLocation();
      } catch {
        setLocNeed(true);
        setBusy(false);
        return;
      }
    }
    try {
      await api(`${fieldJobBase(job.id)}/report`, {
        method: "POST",
        body: JSON.stringify({
          ...where,
          kushlife: toPayload(kl),
          checklist: ticks,
          note,
          hazard: hazardOn ? { note: hazardNote, product_id: hazardProduct ? Number(hazardProduct) : null } : null,
        }),
      });
      onDone(
        `${job.title} completed. The family has the KushLife report${hazardOn ? "; the hazard is on the client's list" : ""}.`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not finish the visit");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="cg-app cg-sheet" role="dialog" aria-label="Visit report">
      <div className="cg-sheet-card">
        <div className="cg-sheet-head">
          <strong>{job.elder_name}</strong>
          <button
            type="button"
            className="cg-sheet-x"
            onClick={() => setLeaving(true)}
            aria-label="Close"
          >
            ×
          </button>
        </div>
        {leaving ? (
          <div className="cg-confirm is-sticky" role="alertdialog" aria-label="Leave without finishing?">
            <p>Leave without finishing? The visit stays open until the report is sent.</p>
            <div className="cg-confirm-btns">
              <button type="button" className="cg-btn is-ghost" onClick={() => setLeaving(false)}>
                Stay
              </button>
              <button type="button" className="cg-btn is-out" onClick={onClose}>
                Leave
              </button>
            </div>
          </div>
        ) : null}
        <KushLifeCaptureForm value={kl} onChange={setKl} />
        {checklist.length ? (
          <fieldset className="cg-checklist">
            <legend>Visit checklist</legend>
            {checklist.map((item) => {
              const t = ticks[item.id];
              const set = (v: { done: boolean; reason: string } | null) =>
                setTicks((cur) => {
                  const next = { ...cur };
                  if (v) next[item.id] = v;
                  else delete next[item.id];
                  return next;
                });
              return (
                <div key={item.id} className="cg-check-row">
                  <span>{item.label}</span>
                  <div className="cg-check-btns">
                    <button
                      type="button"
                      className={`cg-btn ${t?.done === true ? "is-out" : "is-ghost"}`}
                      aria-pressed={t?.done === true}
                      onClick={() => set(t?.done === true ? null : { done: true, reason: "" })}
                    >
                      Done
                    </button>
                    <button
                      type="button"
                      className={`cg-btn ${t?.done === false ? "is-notdone" : "is-ghost"}`}
                      aria-pressed={t?.done === false}
                      onClick={() => set(t?.done === false ? null : { done: false, reason: "" })}
                    >
                      Not done
                    </button>
                  </div>
                  {t?.done === false ? (
                    <input
                      value={t.reason}
                      maxLength={300}
                      placeholder="Why not? e.g. she was asleep"
                      onChange={(e) => set({ done: false, reason: e.target.value })}
                    />
                  ) : null}
                </div>
              );
            })}
          </fieldset>
        ) : null}
        <label className="cg-field">
          Note for the family
          <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="How was the visit? Anything they should know?" />
        </label>
        <div className="cg-row">
          <input ref={camera} type="file" accept="image/*" capture="environment" hidden onChange={(e) => void addPhoto(e.target.files?.[0])} />
          <button type="button" className="cg-btn is-ghost" onClick={() => camera.current?.click()}>
            📷 Add photo
          </button>
          {photos ? <small className="cg-ok">{photos} photo{photos === 1 ? "" : "s"}</small> : null}
        </div>
        <VoiceNoteRecorder jobId={job.id} />
        <label className="cg-toggle">
          <input type="checkbox" checked={hazardOn} onChange={(e) => setHazardOn(e.target.checked)} />
          Spotted a new home safety hazard?
        </label>
        {hazardOn ? (
          <div className="cg-hazard">
            <input value={hazardNote} onChange={(e) => setHazardNote(e.target.value)} placeholder="What and where, e.g. no grab bar by the toilet" />
            <select value={hazardProduct} onChange={(e) => setHazardProduct(e.target.value)}>
              <option value="">Product that would fix it (optional)</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
        ) : null}
        {error ? <p className="cg-note is-warn">{error}</p> : null}
        {locNeed ? <LocationNeeded action="completed" busy={busy} onRetry={() => void submit(true)} /> : null}
        {unticked ? (
          <div className="cg-confirm" role="alertdialog" aria-label="Finish anyway?">
            <p>
              Not ticked yet: <strong>{unticked.join(", ")}</strong>. Finish anyway?
            </p>
            <div className="cg-confirm-btns">
              <button type="button" className="cg-btn is-ghost" onClick={() => setUnticked(null)}>
                Go back
              </button>
              <button type="button" className="cg-btn is-out" disabled={busy} onClick={() => void submit(true)}>
                Finish anyway
              </button>
            </div>
          </div>
        ) : (
          <button type="button" className="cg-btn is-out cg-sheet-submit" disabled={busy} onClick={() => void submit()}>
            {busy ? "Sending…" : "Complete and send report"}
          </button>
        )}
      </div>
    </div>
  );
}
