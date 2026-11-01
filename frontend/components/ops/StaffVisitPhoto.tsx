"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fetchStaffPhotoBlob } from "@/lib/livewell/aiVisualizations";
import { can } from "@/lib/roles";

type Visibility = { document_id: number; family_hidden: boolean };

const visibilityUrl = (id: number) => `/api/v1/home-safety/photos/${id}/family-visibility`;

/** A visit photo for staff, with a "Hide from family" / "Show to family" switch for the care team. */
export function StaffVisitPhoto({ id }: { id: number }) {
  const [src, setSrc] = useState("");
  const [hidden, setHidden] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const canEdit = can("edit");

  useEffect(() => {
    let url = "";
    fetchStaffPhotoBlob(id)
      .then((u) => {
        url = u;
        setSrc(u);
      })
      .catch(() => setSrc(""));
    api<Visibility>(visibilityUrl(id))
      .then((v) => setHidden(v.family_hidden))
      .catch(() => setHidden(null));
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [id]);

  async function toggle() {
    if (hidden === null) return;
    setBusy(true);
    setError("");
    try {
      const v = await api<Visibility>(visibilityUrl(id), {
        method: "PATCH",
        body: JSON.stringify({ family_hidden: !hidden }),
      });
      setHidden(v.family_hidden);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className={`cp-photo-wrap${hidden ? " is-family-hidden" : ""}`}>
      {src ? (
        <a href={src} target="_blank" rel="noopener noreferrer">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="cp-photo" src={src} alt="Visit photo" />
        </a>
      ) : (
        <span className="cp-photo cp-photo-empty" />
      )}
      {hidden ? <span className="cp-photo-badge">Staff only</span> : null}
      {canEdit && hidden !== null ? (
        <button type="button" className="secondary cp-photo-toggle" disabled={busy} onClick={() => void toggle()}>
          {hidden ? "Show to family" : "Hide from family"}
        </button>
      ) : null}
      {error ? (
        <span className="cp-photo-error" role="alert">
          {error}
        </span>
      ) : null}
    </span>
  );
}
