"use client";

import { FamilyLink as Link } from "@/components/livewell/family/FamilyLink";

export type NavLink = { href: string; label: string; icon: JSX.Element; urgent?: boolean };
export type NavGroup = { title: string; links: NavLink[] };

const svg = (body: JSX.Element) => (
  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    {body}
  </svg>
);

/** Icons shared by the sidebar, the drawer, the phone tab bar and the home tiles. */
export const NAV_ICONS = {
  // My details: a person (Emergency contacts keeps the phone).
  person: svg(
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </>,
  ),
  // Privacy: a shield (Documents keeps the page).
  shield: svg(<path d="M12 3 4 6v6c0 4.5 3.4 8.4 8 9 4.6-.6 8-4.5 8-9V6z" />),
  home: svg(<path d="M3 10.5 12 3l9 7.5V21a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" />),
  updates: svg(
    <>
      <path d="M4 5h16v11H7l-3 3z" />
      <path d="M8 9h8M8 12h5" />
    </>,
  ),
  schedule: svg(
    <>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M8 3v4M16 3v4M3 11h18" />
    </>,
  ),
  alerts: svg(
    <>
      <path d="M12 3 2 20h20z" />
      <path d="M12 9v5M12 17h.01" />
    </>,
  ),
  services: svg(
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v8M8 12h8" />
    </>,
  ),
  wallet: svg(
    <>
      <path d="M3 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v1h1a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <circle cx="17" cy="12" r="1.2" />
    </>,
  ),
  messages: svg(<path d="M21 12a8 8 0 0 1-8 8H7l-4 3V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8z" />),
  documents: svg(
    <>
      <path d="M5 3h9l5 5v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" />
      <path d="M14 3v5h5" />
    </>,
  ),
  more: svg(
    <>
      <circle cx="5" cy="12" r="1.6" />
      <circle cx="12" cy="12" r="1.6" />
      <circle cx="19" cy="12" r="1.6" />
    </>,
  ),
  score: svg(
    <>
      <path d="M12 3l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.4 6.8 19.1l1-5.8L3.5 9.2l5.9-.9z" />
    </>,
  ),
  plan: svg(
    <>
      <path d="M9 5h6M9 12h6M9 19h6" />
      <path d="M4 5h.01M4 12h.01M4 19h.01" />
    </>,
  ),
  photos: svg(
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <circle cx="9" cy="10" r="1.6" />
      <path d="m21 16-5-5-8 8" />
    </>,
  ),
  wellness: svg(
    <path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" />,
  ),
  visits: svg(
    <>
      <path d="M4 20a8 8 0 0 1 16 0" />
      <circle cx="12" cy="8" r="4" />
    </>,
  ),
  contacts: svg(
    <path d="M5 4h3l2 5-2.5 1.5a11 11 0 0 0 5 5L14 13l5 2v3a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z" />,
  ),
  circle: svg(
    <>
      <circle cx="9" cy="8" r="3" />
      <circle cx="17" cy="9" r="2.4" />
      <path d="M3 20a6 6 0 0 1 12 0M14 20a5 5 0 0 1 7-4.6" />
    </>,
  ),
  digests: svg(
    <>
      <path d="M6 8a6 6 0 0 1 12 0v5l2 3H4l2-3z" />
      <path d="M10 20a2 2 0 0 0 4 0" />
    </>,
  ),
  call: svg(
    <path d="M5 4h3l2 5-2.5 1.5a11 11 0 0 0 5 5L14 13l5 2v3a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z" />,
  ),
  sos: svg(
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v4M12 16h.01" />
    </>,
  ),
} as const;

/**
 * Five tabs (Home · Updates · Requests · Alerts · More) plus the "More" pages.
 *
 * Merged away (old URLs redirect in middleware.ts):
 *   Visits, Wellness → Updates · Schedule → Requests · Photos → Score & plan ·
 *   Receipts → Wallet.
 * Family members, Notifications and Password live in the profile menu.
 */
export const NAV_GROUPS: NavGroup[] = [
  {
    title: "Overview",
    links: [
      { href: "/kushalaya/family/dashboard", label: "Home", icon: NAV_ICONS.home },
      { href: "/kushalaya/family/updates", label: "Updates", icon: NAV_ICONS.updates },
      { href: "/kushalaya/family/services", label: "Requests", icon: NAV_ICONS.services },
      {
        href: "/kushalaya/family/alerts",
        label: "Alerts & SOS",
        urgent: true,
        icon: NAV_ICONS.alerts,
      },
    ],
  },
  {
    title: "More",
    links: [
      { href: "/kushalaya/family/safety", label: "Score & plan", icon: NAV_ICONS.score },
      { href: "/kushalaya/family/messages", label: "Messages", icon: NAV_ICONS.messages },
      { href: "/kushalaya/family/wallet", label: "Wallet & receipts", icon: NAV_ICONS.wallet },
      { href: "/kushalaya/family/documents", label: "Documents", icon: NAV_ICONS.documents },
      { href: "/kushalaya/family/contacts", label: "Emergency contacts", icon: NAV_ICONS.contacts },
    ],
  },
  {
    title: "You",
    links: [
      { href: "/kushalaya/family/circle", label: "Family members", icon: NAV_ICONS.circle },
      { href: "/kushalaya/family/details", label: "My details", icon: NAV_ICONS.person },
      { href: "/kushalaya/family/digests", label: "Notifications", icon: NAV_ICONS.digests },
      { href: "/kushalaya/family/privacy", label: "Privacy & your data", icon: NAV_ICONS.shield },
    ],
  },
];

export const ALL_NAV_LINKS: NavLink[] = NAV_GROUPS.flatMap((g) => g.links);

/** Five thumb-reachable tabs on phones; "More" carries the rest. */
export const TAB_LINKS: NavLink[] = [
  { href: "/kushalaya/family/dashboard", label: "Home", icon: NAV_ICONS.home },
  { href: "/kushalaya/family/updates", label: "Updates", icon: NAV_ICONS.updates },
  { href: "/kushalaya/family/services", label: "Requests", icon: NAV_ICONS.services },
  { href: "/kushalaya/family/alerts", label: "Alerts", icon: NAV_ICONS.alerts, urgent: true },
  { href: "/kushalaya/family/more", label: "More", icon: NAV_ICONS.more },
];

export function isNavActive(pathname: string, href: string): boolean {
  if (pathname === href) return true;
  if (href === "/kushalaya/family/dashboard") return false;
  return pathname.startsWith(href + "/") || pathname.startsWith(href);
}

export function FamilyNavList({
  pathname,
  unread,
  onNavigate,
}: {
  pathname: string;
  unread: number;
  onNavigate?: () => void;
}) {
  return (
    <nav className="fh-nav" aria-label="Family portal">
      {NAV_GROUPS.map((group) => (
        <div key={group.title} className="fh-nav-group">
          <p className="fh-nav-title">{group.title}</p>
          {group.links.map((link) => {
            const active = isNavActive(pathname, link.href);
            const badge = link.href === "/kushalaya/family/alerts" && unread > 0 ? unread : null;
            return (
              <Link
                key={link.href}
                href={link.href}
                // The five tab-bar destinations are prefetched already; prefetching
                // every sidebar route on top competed with the page's own data
                // on phone connections.
                prefetch={false}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={`fh-nav-link${active ? " is-active" : ""}${
                  link.urgent ? " is-urgent" : ""
                }`}
              >
                <span className="fh-nav-ico">{link.icon}</span>
                <span className="fh-nav-label">{link.label}</span>
                {badge != null && <span className="fh-nav-count">{badge > 9 ? "9+" : badge}</span>}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

export function FamilyTabBar({ pathname, unread }: { pathname: string; unread: number }) {
  return (
    <nav className="fh-tabbar" aria-label="Family portal quick tabs">
      {TAB_LINKS.map((link) => {
        const active = isNavActive(pathname, link.href);
        const badge = link.href === "/kushalaya/family/alerts" && unread > 0 ? unread : null;
        return (
          <Link
            key={link.href}
            href={link.href}
            // Loaded on tap; preloading all tabs at sign-in delayed the home page.
            prefetch={false}
            aria-current={active ? "page" : undefined}
            className={`fh-tab${active ? " is-active" : ""}${link.urgent ? " is-urgent" : ""}`}
          >
            <span className="fh-tab-ico">
              {link.icon}
              {badge != null && <span className="fh-tab-count">{badge > 9 ? "9+" : badge}</span>}
            </span>
            <span className="fh-tab-label">{link.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
