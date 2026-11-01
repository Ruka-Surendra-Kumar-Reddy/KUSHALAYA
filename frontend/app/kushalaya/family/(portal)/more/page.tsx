"use client";

import { useEffect, useState } from "react";
import { fetchFamilyReferral } from "@/lib/livewell/familyApi";
import { publicBrandName, publicSafetyScoreName } from "@/lib/public-brand";
import { FamilyLink as Link } from "@/components/livewell/family/FamilyLink";
import { FamilyShell } from "@/components/livewell/family/FamilyShell";
import { NAV_ICONS } from "@/components/livewell/family/FamilyNav";

type Tile = {
  href: string;
  title: string;
  blurb: string;
  icon: JSX.Element;
  tone?: "urgent" | "green" | "gold";
};

type Group = { title: string; tiles: Tile[] };

const GROUPS: Group[] = [
  {
    title: "Care and money",
    tiles: [
      {
        href: "/kushalaya/family/safety",
        title: "Score & plan",
        blurb: `${publicSafetyScoreName()}, what we found, fixes and photos`,
        icon: NAV_ICONS.score,
        tone: "gold",
      },
      {
        href: "/kushalaya/family/messages",
        title: "Messages",
        blurb: "Write to the care team",
        icon: NAV_ICONS.messages,
      },
      {
        href: "/kushalaya/family/wallet",
        title: "Wallet & receipts",
        blurb: "Balance, add money, receipts",
        icon: NAV_ICONS.wallet,
        tone: "green",
      },
      {
        href: "/kushalaya/family/documents",
        title: "Documents",
        blurb: "Care papers and records you share with the care team",
        icon: NAV_ICONS.documents,
      },
      {
        href: "/kushalaya/family/contacts",
        title: "Emergency contacts",
        blurb: "Local people to call, one tap",
        icon: NAV_ICONS.contacts,
        tone: "urgent",
      },
    ],
  },
  {
    title: "You and your family",
    tiles: [
      {
        href: "/kushalaya/family/circle",
        title: "Family members",
        blurb: "Who else can see updates",
        icon: NAV_ICONS.circle,
      },
      {
        href: "/kushalaya/family/digests",
        title: "Notifications",
        blurb: "What we tell you about, emails and digests",
        icon: NAV_ICONS.digests,
      },
      {
        href: "/kushalaya/family/details",
        title: "My details",
        blurb: "Your phone, where you live and health details",
        icon: NAV_ICONS.person,
      },
      {
        href: "/kushalaya/family/privacy",
        title: "Privacy & your data",
        blurb: "Your consent choices, download your data, delete your account",
        icon: NAV_ICONS.shield,
      },
    ],
  },
];

/** Share-a-link referral (FIX 108): a friend's enquiry arrives with this family as referrer. */
function ReferralCard() {
  const [ref, setRef] = useState<{ code: string; link: string } | null>(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    // No link (referrals not set up on the server) → no card, rather than a broken link.
    fetchFamilyReferral()
      .then((r) => setRef(r.code && r.link ? { code: r.code, link: r.link } : null))
      .catch(() => setRef(null));
  }, []);
  if (!ref) return null;
  const text = `We use ${publicBrandName()} for care visits for our parents. Have a look: ${ref.link}`;
  return (
    <section aria-label="Recommend us" className="card" style={{ marginTop: "1.25rem" }}>
      <h2 style={{ marginTop: 0 }}>Know a family who could use us?</h2>
      <p className="muted">
        Share your link. When they get in touch through it, we&rsquo;ll know you sent them.
      </p>
      <p className="fh-ref-link">{ref.link}</p>
      <div className="fh-ref-actions">
        <button
          type="button"
          className="fh-ref-btn"
          onClick={() => {
            void navigator.clipboard?.writeText(ref.link).then(() => setCopied(true));
          }}
        >
          {copied ? "Link copied" : "Copy link"}
        </button>
        <a
          className="button fh-ref-btn"
          href={`https://wa.me/?text=${encodeURIComponent(text)}`}
          target="_blank"
          rel="noopener noreferrer"
        >
          Share on WhatsApp
        </a>
      </div>
    </section>
  );
}

export default function FamilyMorePage() {
  return (
    <FamilyShell
      title="More"
      subtitle="Every page of your family portal, in one place"
    >
      {GROUPS.map((group) => (
        <section key={group.title} aria-label={group.title}>
          <div className="fh-section-title">
            <h2>{group.title}</h2>
          </div>
          <ul className="fh-tiles">
            {group.tiles.map((tile) => (
              <li key={tile.href}>
                <Link
                  href={tile.href}
                  className={`fh-tile${tile.tone === "urgent" ? " is-urgent" : ""}`}
                >
                  <span
                    className={`fh-tile-ico${
                      tile.tone === "green" ? " is-green" : tile.tone === "gold" ? " is-gold" : ""
                    }`}
                  >
                    {tile.icon}
                  </span>
                  <strong>{tile.title}</strong>
                  <span>{tile.blurb}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
      <ReferralCard />
    </FamilyShell>
  );
}
