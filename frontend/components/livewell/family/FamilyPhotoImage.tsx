"use client";

import { useEffect, useState } from "react";
import { fetchFamilyPhotoBlob } from "@/lib/livewell/photos";

export function FamilyPhotoImage({
  url,
  alt,
  className,
}: {
  url: string;
  alt: string;
  className?: string;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    setSrc(null);
    setFailed(false);

    (async () => {
      try {
        const resolved = await fetchFamilyPhotoBlob(url);
        if (cancelled) return;
        objectUrl = resolved.startsWith("blob:") ? resolved : null;
        setSrc(resolved);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);

  if (failed) {
    return (
      <div
        className="home-safety-family-photo-placeholder"
        role="img"
        aria-label={`${alt} — image unavailable`}
      >
        Unavailable
      </div>
    );
  }
  if (!src) {
    return (
      <div
        className="home-safety-family-photo-placeholder"
        role="status"
        aria-live="polite"
        aria-busy="true"
        aria-label={`Loading ${alt}`}
      >
        Loading…
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} className={className} loading="lazy" decoding="async" />
  );
}
