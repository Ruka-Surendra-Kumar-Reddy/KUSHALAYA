"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/** GET /api/v1/dashboard/nav-counts (team scoped, small integers). */
export type NavCounts = {
  alerts: number;
  messages: number;
  requests: number;
  visits_today: number;
  missed: number;
  questions: number;
  incidents: number;
  handovers: number;
  risks: number;
  care_reviews: number;
  enquiries: number;
  approvals: number;
};

export type NavBadge = { count: number; tone: "red" | "blue" | "gold"; label: string };

const NAV_POLL_MS = 60_000;

function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** The badge for one menu item, or null (zero is never shown). */
export function navBadgeFor(href: string, c: NavCounts | null): NavBadge | null {
  if (!c) return null;
  let b: NavBadge | null = null;
  switch (href) {
    // The open-alerts badge sits on Alerts & SOS, not the Dashboard (FIX 110).
    case "/kushalaya/alerts":
      b = { count: c.alerts, tone: "red", label: plural(c.alerts, "open alert") };
      break;
    case "/kushalaya/messages":
      b = { count: c.messages, tone: "blue", label: plural(c.messages, "unread message") };
      break;
    case "/kushalaya/visits": {
      const n = c.missed + c.requests;
      const parts = [c.missed ? plural(c.missed, "missed visit") : "", c.requests ? plural(c.requests, "request") + " to schedule" : ""];
      b = { count: n, tone: c.missed ? "red" : "gold", label: parts.filter(Boolean).join(", ") };
      break;
    }
    case "/kushalaya/customers": {
      const n = c.questions + c.incidents + c.handovers + c.risks + c.care_reviews;
      b = { count: n, tone: c.incidents ? "red" : "gold", label: plural(n, "client follow-up") };
      break;
    }
    case "/kushalaya/enquiries":
      b = { count: c.enquiries, tone: "gold", label: plural(c.enquiries, "new enquiry", "new enquiries") };
      break;
    case "/kushalaya/orders":
      b = { count: c.approvals, tone: "gold", label: plural(c.approvals, "order", "orders") + " to approve" };
      break;
  }
  return b && b.count > 0 ? b : null;
}

export function badgeText(count: number): string {
  return count > 99 ? "99+" : String(count);
}

/**
 * Polls the badge counts every minute while the tab is visible, and once more
 * when it comes back. Failures keep the last value: a badge is a hint.
 */
export function useNavCounts(enabled: boolean): NavCounts | null {
  const [counts, setCounts] = useState<NavCounts | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let timer: number | undefined;
    async function tick() {
      try {
        const c = await api<NavCounts>("/api/v1/dashboard/nav-counts");
        if (!cancelled) setCounts(c);
      } catch {
        /* keep the last known value */
      }
    }
    function start() {
      if (timer !== undefined || document.visibilityState === "hidden") return;
      void tick();
      timer = window.setInterval(() => void tick(), NAV_POLL_MS);
    }
    function stop() {
      if (timer !== undefined) window.clearInterval(timer);
      timer = undefined;
    }
    const onVisibility = () => (document.visibilityState === "hidden" ? stop() : start());
    // Actions elsewhere (acknowledge, mark read) can ask for a fresh count.
    const onRefresh = () => void tick();
    start();
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("ks:nav-counts", onRefresh);
    return () => {
      cancelled = true;
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("ks:nav-counts", onRefresh);
    };
  }, [enabled]);
  return counts;
}

/** Ask the sidebar to re-count now (after an action on the dashboard). */
export function refreshNavCounts(): void {
  if (typeof window !== "undefined") window.dispatchEvent(new Event("ks:nav-counts"));
}
