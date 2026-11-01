"use client";

import { FOUNDER, founderWhatsAppHref } from "@/lib/marketing/founder";
import type { CareTeamContact } from "@/lib/livewell/familyApi";
import { FamilyLink } from "./FamilyLink";
import { NAV_ICONS } from "./FamilyNav";

/** Used until the dashboard answers (or if it fails): the founder's public number. */
export const DEFAULT_CARE_CONTACT: CareTeamContact = {
  phone: FOUNDER.phoneDisplay,
  whatsapp: FOUNDER.phoneDisplay,
  phone_tel: FOUNDER.phoneTel.replace(/^tel:/, ""),
  whatsapp_link: founderWhatsAppHref(),
  emergency: [
    { number: "112", label: "All emergencies" },
    { number: "108", label: "Ambulance" },
  ],
};

export function careContactOrDefault(c?: CareTeamContact | null): CareTeamContact {
  return c && c.phone_tel ? c : DEFAULT_CARE_CONTACT;
}

const WA_ICON = (
  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path d="M4 20l1.3-3.8A8 8 0 1 1 8 19z" />
    <path d="M9 9.5c.5 2 2 3.6 4 4.3l1.2-1.1 2 .8-.4 1.7c-3.6.2-7.6-3.6-7.6-7.3l1.7-.4.8 2z" />
  </svg>
);

/** Two big buttons: Call care team · WhatsApp (optionally + Message). */
export function CareTeamButtons({
  contact,
  messageHref,
  compact = false,
}: {
  contact?: CareTeamContact | null;
  messageHref?: string;
  compact?: boolean;
}) {
  const c = careContactOrDefault(contact);
  return (
    <div className={`fh-care-call${compact ? " is-compact" : ""}`}>
      <a href={`tel:${c.phone_tel}`} className="fh-care-call-btn is-call">
        {NAV_ICONS.call}
        <span>Call care team</span>
      </a>
      <a
        href={c.whatsapp_link}
        target="_blank"
        rel="noopener noreferrer"
        className="fh-care-call-btn is-wa"
      >
        {WA_ICON}
        <span>WhatsApp</span>
      </a>
      {messageHref ? (
        <FamilyLink href={messageHref} className="fh-care-call-btn is-msg">
          {NAV_ICONS.messages}
          <span>Message</span>
        </FamilyLink>
      ) : null}
    </div>
  );
}

/** Emergency numbers as big tap-to-call buttons ("112 · All emergencies"). */
export function EmergencyNumbers({ contact }: { contact?: CareTeamContact | null }) {
  const c = careContactOrDefault(contact);
  return (
    <div className="fh-emergency-line" role="group" aria-label="Emergency numbers">
      {c.emergency.map((e) => (
        <a key={e.number} href={`tel:${e.number}`} className="fh-emergency-btn">
          <strong>{e.number}</strong>
          <span>{e.label}</span>
        </a>
      ))}
    </div>
  );
}
