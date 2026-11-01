"use client";

/**
 * Client page "Check a room": upload or pick a room photo, run the AI hazard check,
 * confirm hazards. Saved against the client; confirmed ones are offered on the next
 * reassessment ("Add to this assessment").
 */
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { can } from "@/lib/roles";
import { ROOM_TYPE_OPTIONS } from "@/lib/livewell/aiVisualizations";
import {
  listHazardChecks,
  uploadAndCheckRoom,
  type HazardCheck,
  type HazardSummary,
} from "@/lib/livewell/aiHazardCheck";
import { HAZARDS_CHANGED_EVENT, HazardCheckPanel, RoomHazardChips } from "@/components/livewell/AiHazardCheck";

type Doc = { id: number; document_type: string; document_name: string | null; file_name: string; uploaded_at: string };

export function ClientRoomCheck({ elderId }: { elderId: number }) {
  const canEdit = can("edit");
  const [summary, setSummary] = useState<HazardSummary | null>(null);
  const [checks, setChecks] = useState<HazardCheck[]>([]);
  const [photos, setPhotos] = useState<Doc[]>([]);
  const [room, setRoom] = useState("");
  const [open, setOpen] = useState<{ docId: number; room: string | null; check?: HazardCheck } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    listHazardChecks({ elderId })
      .then((r) => {
        setSummary(r.summary);
        setChecks(r.checks);
      })
      .catch(() => undefined);
  }, [elderId]);

  useEffect(() => {
    load();
    api<Doc[]>(`/api/v1/documents/entity/elder/${elderId}`)
      .then((docs) => setPhotos(docs.filter((d) => d.document_type === "HOME_SAFETY_PHOTO").slice(0, 12)))
      .catch(() => setPhotos([]));
  }, [elderId, load]);

  useEffect(() => {
    window.addEventListener(HAZARDS_CHANGED_EVENT, load);
    return () => window.removeEventListener(HAZARDS_CHANGED_EVENT, load);
  }, [load]);

  async function onFile(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const c = await uploadAndCheckRoom(elderId, file, room || null);
      setOpen({ docId: c.document_id, room: c.room_type, check: c });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not check this photo.");
    } finally {
      setBusy(false);
    }
  }

  const checkByDoc = new Map(checks.map((c) => [c.document_id, c]));

  return (
    <section className="card hz-client">
      <p className="ap-client-eyebrow">AI · hazard check</p>
      <h2 style={{ margin: "0.1rem 0 0.25rem" }}>Check a room for hazards</h2>
      <p className="muted" style={{ marginTop: 0 }}>
        Take or choose a photo of a room. AI finds hazards from our checklist in seconds; you confirm each one before
        it counts.
      </p>
      {summary && summary.total_confirmed ? (
        <p>
          <strong>{summary.total_confirmed}</strong> confirmed hazard{summary.total_confirmed === 1 ? "" : "s"}
          {summary.total_urgent ? ` · ${summary.total_urgent} urgent` : ""}
        </p>
      ) : null}
      <RoomHazardChips summary={summary} />

      {canEdit ? (
        <div className="hz-client-tools">
          <select value={room} onChange={(e) => setRoom(e.target.value)} aria-label="Room">
            <option value="">Which room?</option>
            {ROOM_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <label className="hz-file">
            <input
              type="file"
              accept="image/*"
              capture="environment"
              disabled={busy}
              onChange={(e) => {
                void onFile(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
            {busy ? "Uploading…" : "Check a room"}
          </label>
        </div>
      ) : null}
      {error ? <p className="hz-error">{error}</p> : null}

      {photos.length ? (
        <>
          <p className="muted" style={{ margin: "0.6rem 0 0" }}>
            Or pick an earlier photo:
          </p>
          <ul className="hz-earlier">
            {photos.map((d) => {
              const c = checkByDoc.get(d.id);
              const confirmed = c?.hazards.filter((h) => h.decision === "confirmed").length ?? 0;
              return (
                <li key={d.id}>
                  <button
                    type="button"
                    className={`secondary${open?.docId === d.id ? " is-open" : ""}`}
                    onClick={() => setOpen(open?.docId === d.id ? null : { docId: d.id, room: c?.room_type ?? null })}
                  >
                    {c?.room_type
                      ? `${c.room_type.replace(/_/g, " ").replace(/^./, (x) => x.toUpperCase())} photo`
                      : (d.document_name || d.file_name).replace(/\s*\(.*\)$/, "")}
                    {c ? ` · ${confirmed} confirmed` : " · not checked yet"}
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      ) : null}

      {open ? (
        <HazardCheckPanel
          key={open.docId}
          documentId={open.docId}
          roomType={open.room || room || null}
          canEdit={canEdit}
          initialCheck={open.check ?? checkByDoc.get(open.docId) ?? null}
        />
      ) : null}
    </section>
  );
}
