"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { can } from "@/lib/roles";
import { DISMISS_DAYS, useDismissed } from "@/lib/dismissed";

/**
 * Red warning while SMS (MSG91) is not connected: SOS escalation steps 1–2
 * text people, and without a connection those texts are only recorded.
 * Renders nothing until the status is known, or when SMS is connected.
 */
export function SmsOffBanner() {
  const [off, setOff] = useState(false);
  useEffect(() => {
    api<{ sms_connected: boolean }>("/api/v1/team/channels/status")
      .then((s) => setOff(!s.sms_connected))
      .catch(() => setOff(false));
  }, []);
  const [hidden, close] = useDismissed("sms-off");
  if (!off || hidden) return null;
  return (
    <p className="ko-sms-off" role="alert">
      <strong>SOS SMS are off.</strong> Texts are recorded, not sent. Call the family and caregiver by phone for every SOS.
      {can("admin") ? <Link href="/settings/notifications">Connect SMS</Link> : <span> Ask the owner to connect SMS.</span>}
      <button type="button" className="ko-banner-close" onClick={close} aria-label={`Close for ${DISMISS_DAYS} days`} title={`Close for ${DISMISS_DAYS} days`}>
        ✕
      </button>
    </p>
  );
}
