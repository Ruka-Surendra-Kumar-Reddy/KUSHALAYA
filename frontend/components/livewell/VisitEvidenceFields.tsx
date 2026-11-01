"use client";

import { useEffect, useRef, useState } from "react";
import { VisitMap } from "@/components/livewell/VisitMap";
import {
  captureLocation,
  reverseGeocode,
  uploadVisitPhoto,
  type CapturedLocation,
} from "@/lib/livewell/clientProfileApi";

/**
 * Proof that a visit happened: where the staff member was, and photos.
 * Location is captured once when the form opens for a client (and again on
 * request); photos upload straight away so a dropped connection loses nothing.
 */
export function VisitEvidenceFields({
  elderId,
  location,
  onLocation,
  photoIds,
  onPhotoIds,
  autoCapture = true,
}: {
  elderId: number | null;
  location: CapturedLocation | null;
  onLocation: (loc: CapturedLocation | null) => void;
  photoIds: number[];
  onPhotoIds: (ids: number[]) => void;
  autoCapture?: boolean;
}) {
  const [locating, setLocating] = useState(false);
  const [locError, setLocError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [photoError, setPhotoError] = useState("");
  const tried = useRef<number | null>(null);
  const [address, setAddress] = useState("");

  useEffect(() => {
    setAddress("");
    if (!location) return;
    let live = true;
    void reverseGeocode(location.lat, location.lng).then((a) => {
      if (live) setAddress(a);
    });
    return () => {
      live = false;
    };
  }, [location]);

  async function locate() {
    setLocating(true);
    setLocError("");
    try {
      onLocation(await captureLocation());
    } catch (e) {
      onLocation(null);
      setLocError(e instanceof Error ? e.message : "Could not get location");
    } finally {
      setLocating(false);
    }
  }

  useEffect(() => {
    if (!autoCapture || !elderId || tried.current === elderId) return;
    tried.current = elderId;
    void locate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [elderId, autoCapture]);

  async function addPhotos(files: FileList | null) {
    if (!files || !elderId) return;
    setUploading(true);
    setPhotoError("");
    const added: number[] = [];
    try {
      for (const file of Array.from(files).slice(0, 10)) {
        added.push(await uploadVisitPhoto(elderId, file));
      }
    } catch (e) {
      setPhotoError(e instanceof Error ? e.message : "Photo upload failed");
    } finally {
      if (added.length) onPhotoIds([...photoIds, ...added]);
      setUploading(false);
    }
  }

  return (
    <div className="visit-evidence">
      <div className="visit-evidence-row">
        <div>
          <strong>Visit location</strong>
          {location ? (
            <p className="muted">
              {address || "Location captured"}
              {location.accuracy_m != null ? ` (±${location.accuracy_m} m)` : ""}
            </p>
          ) : (
            <p className="muted">{locating ? "Getting location…" : "Not captured yet."}</p>
          )}
          {locError ? <p className="error-text">{locError}</p> : null}
        </div>
        <button type="button" className="secondary" onClick={() => void locate()} disabled={locating}>
          {location ? "Update location" : "Capture location"}
        </button>
      </div>

      {location ? (
        <VisitMap
          height={200}
          pins={[
            {
              id: "here",
              lat: location.lat,
              lng: location.lng,
              lines: ["You are logging this visit from here", address].filter(Boolean),
            },
          ]}
        />
      ) : null}

      <div className="visit-evidence-row">
        <div>
          <strong>Visit photos</strong>
          <p className="muted">
            {photoIds.length
              ? `${photoIds.length} photo${photoIds.length === 1 ? "" : "s"} attached`
              : "Add photos taken during the visit."}
            {uploading ? " Uploading…" : ""}
          </p>
          {photoError ? <p className="error-text">{photoError}</p> : null}
        </div>
        <label className={`secondary visit-evidence-upload${!elderId || uploading ? " is-disabled" : ""}`}>
          Add photos
          <input
            type="file"
            accept="image/*"
            multiple
            hidden
            disabled={!elderId || uploading}
            onChange={(e) => {
              void addPhotos(e.target.files);
              e.target.value = "";
            }}
          />
        </label>
      </div>
    </div>
  );
}
