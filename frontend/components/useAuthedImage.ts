"use client";

import { useEffect, useState } from "react";
import { fetchFamilyPhotoBlob } from "@/lib/livewell/photos";

/** Loads an authed image (photo endpoints need the bearer token) as an object URL. */
export function useAuthedImage(url: string | null | undefined): string | null {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    let obj: string | null = null;
    setSrc(null);
    if (!url) return;
    fetchFamilyPhotoBlob(url)
      .then((s) => {
        if (!alive) {
          if (s.startsWith("blob:")) URL.revokeObjectURL(s);
          return;
        }
        obj = s.startsWith("blob:") ? s : null;
        setSrc(s);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
      if (obj) URL.revokeObjectURL(obj);
    };
  }, [url]);
  return src;
}
