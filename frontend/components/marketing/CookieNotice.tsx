"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import {
  COOKIE_SETTINGS_EVENT,
  getConsent,
  loadTrackers,
  setConsent,
  track,
  trackPage,
  trackingConfigured,
  type Consent,
} from "@/lib/marketing/tracking";

/** Accept / Decline for ads cookies. Shows nothing until tracking IDs are configured. */
export function CookieNotice() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!trackingConfigured()) return;
    if (getConsent() === null) setOpen(true);
    loadTrackers();
    setReady(true);
    const reopen = () => setOpen(true);
    window.addEventListener(COOKIE_SETTINGS_EVENT, reopen);
    // Call and WhatsApp buttons live all over the site, so listen once here.
    const onClick = (e: MouseEvent) => {
      const link = (e.target as HTMLElement | null)?.closest?.("a");
      const href = link?.getAttribute("href") || "";
      if (href.startsWith("tel:") || href.includes("wa.me/") || href.includes("whatsapp.com/")) track("contact");
    };
    document.addEventListener("click", onClick);
    return () => {
      window.removeEventListener(COOKIE_SETTINGS_EVENT, reopen);
      document.removeEventListener("click", onClick);
    };
  }, []);

  useEffect(() => {
    if (!ready) return;
    trackPage(pathname);
    if (pathname === "/packages") track("view_plans");
  }, [pathname, ready]);

  function choose(value: Consent) {
    const wasAccepted = getConsent() === "accepted";
    setConsent(value);
    setOpen(false);
    if (value === "declined" && wasAccepted) {
      window.location.reload(); // the trackers are already running; a reload stops them
      return;
    }
    if (value === "accepted") {
      loadTrackers();
      trackPage(pathname);
    }
  }

  if (!open) return null;
  return (
    <div className="mk-cookie" role="region" aria-label="Cookie choice">
      <p>
        We use cookies to show you relevant KushAlaya ads and see which ones help. <a href="/privacy">Privacy policy</a>
      </p>
      <div className="mk-cookie-acts">
        <button type="button" className="mk-btn mk-btn-outline" onClick={() => choose("declined")}>
          Decline
        </button>
        <button type="button" className="mk-btn mk-btn-primary" onClick={() => choose("accepted")}>
          Accept
        </button>
      </div>
    </div>
  );
}

/** Footer link so a visitor can change their mind. Hidden until tracking is configured. */
export function CookieSettingsLink() {
  const [show, setShow] = useState(false);
  useEffect(() => setShow(trackingConfigured()), []);
  if (!show) return null;
  return (
    <button type="button" className="mk-cookie-link" onClick={() => window.dispatchEvent(new Event(COOKIE_SETTINGS_EVENT))}>
      Cookie settings
    </button>
  );
}
