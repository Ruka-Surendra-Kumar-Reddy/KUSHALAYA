"use client";

import { useEffect, useState, type ReactNode } from "react";
import { isMarketingHost } from "@/lib/hosts";

/** Same name as PORTAL_COOKIE in lib/portal-cookie.ts. */
const PORTAL_COOKIE = "ks_portal";

/**
 * Picks the 404 variant in the browser. Reading headers()/cookies() in
 * app/not-found.tsx made every route in the app dynamic (no page could be
 * prerendered), so each page load waited on a full server render.
 */
export function NotFoundSwitch({ marketing, staff, other }: { marketing: ReactNode; staff: ReactNode; other: ReactNode }) {
  const [which, setWhich] = useState<"marketing" | "staff" | "other" | null>(null);
  useEffect(() => {
    if (isMarketingHost(window.location.host)) setWhich("marketing");
    else if (document.cookie.split("; ").includes(`${PORTAL_COOKIE}=staff`)) setWhich("staff");
    else setWhich("other");
  }, []);
  if (which === "marketing") return <>{marketing}</>;
  if (which === "staff") return <>{staff}</>;
  if (which === "other") return <>{other}</>;
  return <main className="not-found" aria-busy="true" />;
}
