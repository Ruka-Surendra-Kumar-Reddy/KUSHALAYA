"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { familyLoginPath } from "@/lib/livewell/family-paths";
import { familySignOut } from "./FamilyProfileMenu";
import "./privacy.css";
import { withPublicBrand } from "@/lib/public-brand";
import {
  fetchConsentStatus,
  fetchPrivacyNotice,
  type ConsentStatus,
  type PrivacyNotice,
} from "@/lib/livewell/privacyApi";
import { PrivacyConsentForm } from "./PrivacyConsentForm";
import { careContactOrDefault } from "./CareTeamContact";
import { FamilyLink } from "./FamilyLink";
import { fetchPublicCareTeamContact, type CareTeamContact } from "@/lib/livewell/familyApi";

/**
 * DPDP (#104): asks for consent on first sign-in, and again whenever the
 * privacy notice version changes. Fails open (no overlay) if the API errors,
 * so a hiccup never locks families out of SOS and visit updates.
 *
 * Help stays reachable while it is open: Call care team, SOS (the Alerts page
 * is never gated) and 112 / 108.
 */
export function PrivacyConsentGate() {
  const [status, setStatus] = useState<ConsentStatus | null>(null);
  const [notice, setNotice] = useState<PrivacyNotice | null>(null);
  const [contact, setContact] = useState<CareTeamContact | null>(null);
  const router = useRouter();
  const pathname = usePathname() || "";

  useEffect(() => {
    let live = true;
    fetchConsentStatus()
      .then(async (s) => {
        if (!live || !s.needs_consent) return;
        const n = await fetchPrivacyNotice();
        if (live) {
          setNotice(n);
          setStatus(s);
        }
        fetchPublicCareTeamContact()
          .then((c) => live && setContact(c))
          .catch(() => undefined);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);

  if (!status || !notice || !status.needs_consent) return null;
  // SOS must never sit behind the consent form.
  if (/\/alerts\/?$/.test(pathname)) return null;
  const updated = !!status.consent;
  const c = careContactOrDefault(contact);

  return (
    <div className="fp-gate" role="dialog" aria-modal="true" aria-labelledby="fp-gate-title">
      <div className="fp-gate-card">
        <h2 id="fp-gate-title">{updated ? "Our privacy notice has changed" : "Your privacy"}</h2>
        <div className="fp-gate-help" role="group" aria-label="Need help now?">
          <a href={`tel:${c.phone_tel}`} className="fp-gate-btn is-call">
            Call care team
          </a>
          <FamilyLink href="/kushalaya/family/alerts#sos" className="fp-gate-btn is-sos">
            SOS
          </FamilyLink>
          {c.emergency.map((e) => (
            <a key={e.number} href={`tel:${e.number}`} className="fp-gate-btn is-emergency">
              <strong>{e.number}</strong> {e.label}
            </a>
          ))}
        </div>
        <p>
          Before you continue, please read how we use your family&rsquo;s information and choose what you agree
          to. Version {notice.version}.
        </p>
        <div className="fp-notice-scroll">
          {notice.sections.map((s) => (
            <section key={s.heading}>
              <h3>{s.heading}</h3>
              <p>{withPublicBrand(s.body)}</p>
            </section>
          ))}
          <p>
            <strong>Grievance Officer:</strong> {notice.grievance_officer.name} ·{" "}
            <a href={`mailto:${notice.grievance_officer.email}`}>{notice.grievance_officer.email}</a> ·{" "}
            <a href={`tel:${notice.grievance_officer.phone.replace(/\s/g, "")}`}>{notice.grievance_officer.phone}</a>
          </p>
        </div>
        <PrivacyConsentForm notice={notice} status={status} onSaved={setStatus} submitLabel="I agree — continue" />
        <p className="fp-gate-out">
          Not now?{" "}
          <button type="button" className="fp-link-btn" onClick={() => void familySignOut(() => router.push(familyLoginPath()))}>
            Sign out
          </button>
        </p>
      </div>
    </div>
  );
}
