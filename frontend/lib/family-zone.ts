"use client";

import { useEffect, useState } from "react";
import { fetchMyDetails } from "@/lib/family-money";

let cached: Promise<string | null> | null = null;

/** The signed-in family member's own timezone from My details (null until loaded or if unknown). */
export function useFamilyTimezone(): string | null {
  const [tz, setTz] = useState<string | null>(null);
  useEffect(() => {
    cached ??= fetchMyDetails()
      .then((d) => d.timezone || null)
      .catch(() => {
        cached = null;
        return null;
      });
    let live = true;
    void cached.then((z) => live && setTz(z));
    return () => {
      live = false;
    };
  }, []);
  return tz;
}

/** Forget the cached zone (after My details is saved). */
export function resetFamilyTimezone() {
  cached = null;
}
