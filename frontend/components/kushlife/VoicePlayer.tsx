"use client";

import { useEffect, useState } from "react";
import { authedObjectUrl } from "@/lib/kushlife-quality";

/** A visit voice note: fetched with the login (an <audio src> can't send it), then played inline. */
export function VoicePlayer({ note }: { note: { url: string; duration_s: number | null } }) {
  const [src, setSrc] = useState("");
  const [err, setErr] = useState("");
  useEffect(() => () => { if (src) URL.revokeObjectURL(src); }, [src]);
  if (src) return <audio controls autoPlay src={src} />;
  return (
    <>
      <button type="button" className="secondary" onClick={() => authedObjectUrl(note.url).then(setSrc).catch((e) => setErr(e.message))}>
        ▶ Play voice note{note.duration_s ? ` (${note.duration_s}s)` : ""}
      </button>
      {err ? <small role="alert">{err}</small> : null}
    </>
  );
}
