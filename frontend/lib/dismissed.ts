"use client";

import { useCallback, useEffect, useState } from "react";

/** How long a closed reminder banner stays hidden on this device before it comes back. */
export const DISMISS_DAYS = 7;
const DAY_MS = 24 * 60 * 60 * 1000;

/** Pure: still hidden if it was closed less than `days` ago. */
export function isDismissed(closedAt: number | null, now: number, days: number = DISMISS_DAYS): boolean {
  return closedAt !== null && now - closedAt >= 0 && now - closedAt < days * DAY_MS;
}

function storageKey(key: string) {
  return `ks-dismissed:${key}`;
}

/**
 * Reminder banners (SMS off, backups not set up) can be closed per device; they come
 * back after DISMISS_DAYS so the to-do is not forgotten. Never use for live SOS alerts.
 * Starts hidden until storage is read, so a closed banner never flashes on load.
 */
export function useDismissed(key: string): [boolean, () => void] {
  const [hidden, setHidden] = useState(true);
  useEffect(() => {
    let closedAt: number | null = null;
    try {
      const v = Number(window.localStorage.getItem(storageKey(key)));
      closedAt = Number.isFinite(v) && v > 0 ? v : null;
    } catch {
      /* storage blocked: always show */
    }
    setHidden(isDismissed(closedAt, Date.now()));
  }, [key]);
  const close = useCallback(() => {
    try {
      window.localStorage.setItem(storageKey(key), String(Date.now()));
    } catch {
      /* storage blocked: hidden until the page reloads */
    }
    setHidden(true);
  }, [key]);
  return [hidden, close];
}
