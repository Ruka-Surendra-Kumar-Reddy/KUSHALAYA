"use client";

import { useEffect, useRef, useState } from "react";
import type { AssessmentPhoto } from "@/lib/livewell/assessment";
import { ROOM_TYPE_OPTIONS, fetchStaffPhotoBlob } from "@/lib/livewell/aiVisualizations";
import { getPhotoPreviewBlob } from "@/lib/livewell/photoPreviewStore";
import {
  AssessmentHazardSummary,
  HazardCarryOver,
  HazardCheckPanel,
  type ApplyHazard,
} from "@/components/livewell/AiHazardCheck";

/** AI room hazard check wiring (optional; omitted = no AI buttons). */
export type AssessmentPhotosAiCheck = {
  canEdit: boolean;
  elderId?: number | null;
  /** Offer confirmed hazards from earlier client checks (draft reassessments only). */
  allowCarryOver?: boolean;
  onApplied: (items: ApplyHazard[]) => void;
};

function newPhotoId() {
  return `hsp-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

/** Phone / tablet touch — show separate camera vs library actions. */
function useTouchDevice(): boolean {
  const [touch, setTouch] = useState(false);
  useEffect(() => {
    setTouch(window.matchMedia("(pointer: coarse)").matches);
  }, []);
  return touch;
}

export function SyncedPhotoThumb({
  documentId,
  caption,
}: {
  documentId: number;
  caption: string;
}) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    fetchStaffPhotoBlob(documentId)
      .then((url) => {
        if (!cancelled) {
          objectUrl = url;
          setSrc(url);
        }
      })
      .catch(() => {
        if (!cancelled) setSrc(null);
      });
    return () => {
      cancelled = true;
      if (objectUrl?.startsWith("blob:")) URL.revokeObjectURL(objectUrl);
    };
  }, [documentId]);

  if (!src) {
    return <div className="home-safety-family-photo-placeholder">Photo #{documentId}</div>;
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={caption || "Assessment photo"} />
  );
}

function AssessmentPhotoThumb({
  assessmentId,
  photo,
  onDelete,
  disabled,
}: {
  assessmentId: string;
  photo: AssessmentPhoto;
  onDelete: () => void;
  disabled?: boolean;
}) {
  const [src, setSrc] = useState<string | null>(photo.localPreview);
  const objectUrlRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function resolve() {
      if (photo.localPreview) {
        setSrc(photo.localPreview);
        return;
      }
      if (photo.documentId) return;
      if (!photo.hasLocalPreview) return;

      const blob = await getPhotoPreviewBlob(assessmentId, photo.id);
      if (cancelled || !blob) return;
      if (objectUrlRef.current?.startsWith("blob:")) {
        URL.revokeObjectURL(objectUrlRef.current);
      }
      const url = URL.createObjectURL(blob);
      objectUrlRef.current = url;
      setSrc(url);
    }

    void resolve();
    return () => {
      cancelled = true;
    };
  }, [assessmentId, photo.id, photo.localPreview, photo.documentId, photo.hasLocalPreview]);

  useEffect(() => {
    return () => {
      if (objectUrlRef.current?.startsWith("blob:")) {
        URL.revokeObjectURL(objectUrlRef.current);
      }
    };
  }, []);

  if (photo.documentId) {
    return <SyncedPhotoThumb documentId={photo.documentId} caption={photo.caption} />;
  }

  if (src) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={src} alt={photo.caption || "Assessment photo"} />
    );
  }

  return (
    <div className="home-safety-photo-missing">
      <p className="home-safety-photo-missing-text">Image unavailable on this device</p>
      {!disabled && (
        <button type="button" className="secondary danger home-safety-photo-delete" onClick={onDelete}>
          Delete photo
        </button>
      )}
    </div>
  );
}

export function AssessmentPhotos({
  assessmentId,
  photos,
  onChange,
  disabled,
  heading = "Photos",
  uploadingPhotoIds,
  aiCheck,
}: {
  aiCheck?: AssessmentPhotosAiCheck;
  assessmentId: string;
  photos: AssessmentPhoto[];
  onChange: (photos: AssessmentPhoto[]) => void;
  disabled?: boolean;
  heading?: string;
  uploadingPhotoIds?: ReadonlySet<string>;
}) {
  const isTouchDevice = useTouchDevice();
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const libraryInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [aiOpenId, setAiOpenId] = useState<string | null>(null);
  const aiOpenPhoto = aiCheck ? photos.find((p) => p.id === aiOpenId && p.documentId) : undefined;

  function addPhoto(file: File) {
    if (!file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = () => {
      const localPreview = typeof reader.result === "string" ? reader.result : null;
      if (!localPreview) return;
      onChange([
        ...photos,
        {
          id: newPhotoId(),
          caption: "",
          roomType: null,
          localPreview,
          hasLocalPreview: true,
          documentId: null,
          uploadedAt: null,
        },
      ]);
    };
    reader.readAsDataURL(file);
  }

  function updateRoomType(id: string, roomType: string) {
    onChange(
      photos.map((p) => (p.id === id ? { ...p, roomType: roomType || null } : p)),
    );
  }

  function updateCaption(id: string, caption: string) {
    onChange(photos.map((p) => (p.id === id ? { ...p, caption } : p)));
  }

  function deletePhoto(id: string) {
    onChange(photos.filter((p) => p.id !== id));
  }

  function handleFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) addPhoto(file);
    e.target.value = "";
  }

  function photoStatus(p: AssessmentPhoto): string {
    if (p.documentId) return `Synced #${p.documentId}`;
    if (uploadingPhotoIds?.has(p.id)) return "Uploading…";
    if (p.localPreview || p.hasLocalPreview) return "Saved on device";
    return "Upload pending — sign in & add client first name";
  }

  return (
    <section className="card home-safety-section">
      <div className="home-safety-section-panel-head">
        <h2 className="home-safety-section-panel-title">{heading}</h2>
      </div>
      <p className="muted home-safety-section-hint">Add photos and set a room type.</p>
      {aiCheck ? <AssessmentHazardSummary assessmentId={assessmentId} /> : null}
      {aiCheck?.allowCarryOver && aiCheck.elderId ? (
        <HazardCarryOver elderId={aiCheck.elderId} assessmentId={assessmentId} onApplied={aiCheck.onApplied} />
      ) : null}

      {!disabled && isTouchDevice ? (
        <div className="home-safety-photo-add-row">
          <label className="home-safety-photo-add">
            <input
              ref={cameraInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              className="home-safety-photo-input"
              onChange={handleFileInput}
            />
            Take photo
          </label>
          <label className="home-safety-photo-add home-safety-photo-add-library">
            <input
              ref={libraryInputRef}
              type="file"
              accept="image/*"
              className="home-safety-photo-input"
              onChange={handleFileInput}
            />
            Choose from library
          </label>
        </div>
      ) : !disabled ? (
        <label className="home-safety-photo-add">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="home-safety-photo-input"
            onChange={handleFileInput}
          />
          + Add photo
        </label>
      ) : null}

      {photos.length === 0 ? (
        <p className="muted" style={{ fontSize: "0.9rem" }}>
          No photos yet.
        </p>
      ) : (
        <ul className="home-safety-assessor-photo-list">
          {photos.map((p) => (
            <li key={p.id} className="home-safety-assessor-photo">
              <AssessmentPhotoThumb
                assessmentId={assessmentId}
                photo={p}
                disabled={disabled}
                onDelete={() => deletePhoto(p.id)}
              />
              <select
                value={p.roomType || ""}
                onChange={(e) => updateRoomType(p.id, e.target.value)}
                disabled={disabled}
                aria-label="Room type"
              >
                <option value="">Room type…</option>
                {ROOM_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <input
                type="text"
                value={p.caption}
                onChange={(e) => updateCaption(p.id, e.target.value)}
                placeholder="Caption (e.g. Bathroom — missing grab bar)"
                disabled={disabled}
              />
              <div className="home-safety-assessor-photo-meta">
                <span
                  className={
                    p.documentId ? "home-safety-saved-badge" : "home-safety-draft-badge"
                  }
                >
                  {photoStatus(p)}
                </span>
                {!disabled && (
                  <button
                    type="button"
                    className="secondary danger home-safety-photo-delete"
                    onClick={() => deletePhoto(p.id)}
                  >
                    Delete
                  </button>
                )}
              </div>
              {aiCheck && p.documentId ? (
                <button
                  type="button"
                  className={`secondary hz-photo-trigger${aiOpenId === p.id ? " is-open" : ""}`}
                  onClick={() => setAiOpenId((cur) => (cur === p.id ? null : p.id))}
                  aria-expanded={aiOpenId === p.id}
                >
                  {aiCheck.canEdit ? "Check this room with AI" : "AI room check"}
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {aiCheck && aiOpenPhoto?.documentId ? (
        <HazardCheckPanel
          key={aiOpenPhoto.documentId}
          documentId={aiOpenPhoto.documentId}
          roomType={aiOpenPhoto.roomType}
          assessmentId={assessmentId}
          canEdit={aiCheck.canEdit}
          autoStart
          onApplied={aiCheck.onApplied}
        />
      ) : null}
    </section>
  );
}
