"use client";

import { useEffect, useState, type ComponentType, type ReactNode } from "react";
import { isNavActive, roleLabelFromKey } from "@workforceos/contracts/shell";
import type { NavGroup, ShellLinkProps, TranslateFn } from "@workforceos/contracts/shell";
import { BRAND_ASSETS, BRAND_ASSET_SIZE } from "@/lib/brand-assets";
import { publicBrandName } from "@/lib/public-brand";
import { portalFont } from "@/components/portal-font";
import { OpsProfileMenu } from "./OpsProfileMenu";
// The account menu keeps its ks-* classes, whose base styles live in the
// shared shell sheet; ops-portal.css re-skins them under .ko-app.
import "@/components/ks-shell.css";
import "./ops-portal.css";
import { can, isMarketing } from "@/lib/roles";

const svg = (body: JSX.Element) => (
  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    {body}
  </svg>
);

/** One icon per destination, looked up by href; unknown routes get a dot. */
const NAV_ICONS: Record<string, JSX.Element> = {
  "/dashboard": svg(<path d="M3 10.5 12 3l9 7.5V21a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" />),
  "/kushalaya/customers": svg(
    <>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3 20a6 6 0 0 1 12 0" />
      <circle cx="17" cy="9" r="2.4" />
      <path d="M15 20a5 5 0 0 1 6-4.6" />
    </>,
  ),
  "/kushalaya/assessments": svg(
    <>
      <rect x="5" y="4" width="14" height="17" rx="2" />
      <path d="M9 4V3h6v1M9 11l2 2 4-4M9 16h6" />
    </>,
  ),
  "/kushalaya/visits": svg(
    <>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M8 3v4M16 3v4M3 11h18" />
    </>,
  ),
  "/kushalaya/activity": svg(
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>,
  ),
  "/kushalaya/partners": svg(
    <path d="M7 12l3 3 4-4M3 8a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v8a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3z" />,
  ),
  "/kushalaya/suppliers": svg(
    <>
      <path d="M3 8l9-5 9 5v8l-9 5-9-5z" />
      <path d="M3 8l9 5 9-5M12 13v8" />
    </>,
  ),
  "/prospects": svg(
    <>
      <circle cx="10" cy="8" r="3.2" />
      <path d="M4 20a6 6 0 0 1 12 0M19 8v6M16 11h6" />
    </>,
  ),
  "/documents": svg(
    <>
      <path d="M5 3h9l5 5v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" />
      <path d="M14 3v5h5M8 13h8M8 17h5" />
    </>,
  ),
  "/users": svg(
    <>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20a7 7 0 0 1 14 0" />
    </>,
  ),
  "/settings": svg(
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
    </>,
  ),
  "/settings/workflows": svg(
    <>
      <circle cx="6" cy="6" r="2.5" />
      <circle cx="18" cy="12" r="2.5" />
      <circle cx="6" cy="18" r="2.5" />
      <path d="M8.5 6h4a3 3 0 0 1 3 3v0M8.5 18h4a3 3 0 0 0 3-3v0" />
    </>,
  ),
  "/tenants": svg(
    <>
      <rect x="4" y="3" width="16" height="18" rx="2" />
      <path d="M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2M10 21v-3h4v3" />
    </>,
  ),
  "/kushalaya/catalog": svg(
    <>
      <rect x="3" y="3" width="8" height="8" rx="2" />
      <rect x="13" y="3" width="8" height="8" rx="2" />
      <rect x="3" y="13" width="8" height="8" rx="2" />
      <rect x="13" y="13" width="8" height="8" rx="2" />
    </>,
  ),
  "/kushalaya/pricing": svg(
    <>
      <path d="M3 12V5a2 2 0 0 1 2-2h7l9 9-9 9z" />
      <circle cx="8" cy="8" r="1.4" />
    </>,
  ),
  "/kushalaya/solutions": svg(
    <>
      <path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z" />
    </>,
  ),
  "/kushalaya/rubric": svg(
    <>
      <path d="M9 6h11M9 12h11M9 18h11" />
      <path d="m3 6 1.5 1.5L7 5M3 12l1.5 1.5L7 11M3 18l1.5 1.5L7 17" />
    </>,
  ),
  "/kushalaya/master-data": svg(
    <>
      <ellipse cx="12" cy="6" rx="8" ry="3" />
      <path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
    </>,
  ),
  "/kushalaya/ai-jobs": svg(
    <>
      <path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z" />
      <path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z" />
    </>,
  ),
  "/kushalaya/alerts": svg(
    <>
      <path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z" />
      <path d="M10 21h4M12 2v1" />
    </>,
  ),
  "/kushalaya/messages": svg(
    <path d="M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9l-5 4V6a1 1 0 0 1 1-1z" />,
  ),
  "/kushalaya/enquiries": svg(
    <>
      <path d="M4 4h16v12H8l-4 4z" />
      <path d="M10 8.5a2 2 0 1 1 2.6 1.9c-.4.2-.6.5-.6.9V12M12 14.2v.1" />
    </>,
  ),
  "/kushalaya/vendors": svg(
    <>
      <path d="M3 8l9-5 9 5v8l-9 5-9-5z" />
      <path d="M3 8l9 5 9-5M12 13v8" />
    </>,
  ),
  "/kushalaya/hiring": svg(
    <>
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M3 13h18" />
    </>,
  ),
  "/kushalaya/owner": svg(
    <>
      <path d="M4 20V4M4 20h16" />
      <path d="M8 16v-4M12 16V8M16 16v-6" />
    </>,
  ),
  "/kushalaya/invoices": svg(
    <>
      <path d="M6 3h12v18l-3-2-3 2-3-2-3 2z" />
      <path d="M9 8h6M9 12h6M9 16h3" />
    </>,
  ),
  "/kushalaya/blog": svg(
    <>
      <path d="M4 4h12l4 4v12H4z" />
      <path d="M8 10h8M8 14h8M8 18h5" />
    </>,
  ),
  "/kushalaya/coupons": svg(
    <>
      <path d="M3 8a1 1 0 0 1 1-1h16a1 1 0 0 1 1 1v2a2 2 0 0 0 0 4v2a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-2a2 2 0 0 0 0-4z" />
      <path d="M14 7v10" strokeDasharray="2 2" />
    </>,
  ),
  // Settings hub tiles share this icon set (app/(app)/settings/page.tsx).
  "/settings/notifications": svg(
    <>
      <path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z" />
      <path d="M10 21h4" />
    </>,
  ),
  "/settings/website": svg(
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3z" />
    </>,
  ),
  "/settings/business": svg(
    <>
      <path d="M4 21V5l8-2v18M12 9h8v12M3 21h18" />
      <path d="M8 8v.01M8 12v.01M8 16v.01M16 13v.01M16 17v.01" />
    </>,
  ),
  "/settings/privacy": svg(
    <>
      <path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z" />
      <path d="M9 12l2 2 4-4" />
    </>,
  ),
  "/settings/security": svg(
    <>
      <rect x="5" y="10" width="14" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3" />
    </>,
  ),
  "/settings/language": svg(
    <>
      <path d="M4 5h9M8.5 3v2M6 5c.5 3 2.5 5.5 5 7M11 5c-.6 3.4-2.9 6.4-6 8" />
      <path d="M12 21l4-9 4 9M13.5 18h5" />
    </>,
  ),
  "/kushalaya/iot-devices": svg(
    <>
      <rect x="7" y="6" width="10" height="12" rx="3" />
      <path d="M9 6V3h6v3M9 18v3h6v-3M12 10v3l2 1" />
    </>,
  ),
};

const DEFAULT_ICON = svg(
  <>
    <circle cx="12" cy="12" r="8" />
    <circle cx="12" cy="12" r="2" />
  </>,
);

export function navIcon(href: string): JSX.Element {
  if (NAV_ICONS[href]) return NAV_ICONS[href];
  const key = Object.keys(NAV_ICONS).find((k) => k !== "/dashboard" && href.startsWith(k));
  return key ? NAV_ICONS[key] : DEFAULT_ICON;
}

function todayLabel(): string {
  return new Date().toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });
}

/** Sub-pages that are not menu items, most specific first. */
const SUB_PAGE_TITLES: [string, string][] = [
  ["/kushalaya/visits/roster", "Roster"],
  ["/kushalaya/visits/leave", "Leave and cover"],
  ["/kushalaya/customers/", "Client"],
  ["/kushalaya/assessments/", "Assessment"],
  ["/settings/security", "Security"],
  ["/settings/notifications", "Notifications"],
  ["/settings/background-jobs", "Background jobs"],
  ["/settings/business", "Business details"],
  ["/settings/privacy", "Privacy"],
  ["/settings/subscription", "Subscription"],
  ["/settings/website", "Website"],
  ["/settings/workflows", "Workflows"],
  ["/unauthorized", "Access denied"],
];

/** The page's name for the browser tab: a known sub-page, else the menu item that is active. */
export function opsPageTitle(pathname: string, groups: NavGroup[]): string {
  const sub = SUB_PAGE_TITLES.find(([prefix]) =>
    prefix.endsWith("/") ? pathname.startsWith(prefix) : pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
  if (sub) return sub[1];
  let best: { href: string; label: string } | null = null;
  for (const g of groups) {
    for (const item of g.items) {
      if (isNavActive(pathname, item.href) && (!best || item.href.length > best.href.length)) best = item;
    }
  }
  return best?.label || "Dashboard";
}

/**
 * Staff portal shell: navy side navigation with icons (persistent on desktop,
 * drawer on phones), white top bar with the mark, the portal name and the
 * account menu, and an "apps" card pinned to the bottom of the sidebar.
 *
 * Deliberately app-local rather than a change to AdminAppShell in
 * workforceos-core — that shell is shared with ElderCareOps and
 * HousekeepingOps, which should not inherit Kushalaya's styling.
 */
export function OpsShell({
  children,
  pathname,
  auth,
  navGroups,
  portalTitle,
  onLogout,
  t,
  Link,
  localeSwitcher,
  tenantLabel,
  menuBadge = 0,
  topbarAction,
}: {
  children: ReactNode;
  pathname: string;
  auth: { email: string; role: string };
  navGroups: NavGroup[];
  portalTitle: string;
  onLogout: () => void;
  t: TranslateFn;
  Link: ComponentType<ShellLinkProps>;
  localeSwitcher?: ReactNode;
  tenantLabel?: string;
  /** Open alerts: a red dot on the phone menu button, since the badges are in the drawer. */
  menuBadge?: number;
  /** Always-visible action at the start of the top bar's right side (the SOS button). */
  topbarAction?: ReactNode;
}) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [today, setToday] = useState("");

  useEffect(() => {
    setDrawerOpen(false);
  }, [pathname]);

  // Browser tab: "<Page> · KushAlaya Ops" for every ops page (#13).
  useEffect(() => {
    const title = `${opsPageTitle(pathname, navGroups)} · ${publicBrandName()} Ops`;
    document.title = title;
    // Next may write the root metadata title after this effect on a client navigation.
    const t = window.setTimeout(() => {
      document.title = title;
    }, 50);
    return () => window.clearTimeout(t);
  }, [pathname, navGroups]);

  // Rendered after mount so the server HTML never carries a server-side date.
  useEffect(() => {
    setToday(todayLabel());
  }, []);

  useEffect(() => {
    if (!drawerOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setDrawerOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  const nav = (
    <nav className="ko-nav" aria-label={portalTitle}>
      {navGroups.map((group) => (
        <div key={group.title} className="ko-nav-group">
          <p className="ko-nav-title">{group.title}</p>
          {group.items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`ko-nav-link${isNavActive(pathname, item.href) ? " is-active" : ""}`}
              onClick={() => setDrawerOpen(false)}
            >
              <span className="ko-nav-ico">{navIcon(item.href)}</span>
              <span className="ko-nav-label">{item.label}</span>
            </Link>
          ))}
        </div>
      ))}
    </nav>
  );

  // The assessor app records assessments, so view-only staff don't get it.
  const assessor = can("edit", auth.role) && !isMarketing();
  const apps = (
    <div className="ko-side-apps">
      <strong>{t("dashboard.apps")}</strong>
      <p>{assessor ? "Assessor app for field visits; the family portal as your clients see it." : "The family portal as your clients see it."}</p>
      <div className="ko-side-apps-actions">
        {/* Plain anchors: both open a different app in a new tab. */}
        {assessor ? (
        <a href="/kushalaya" target="_blank" rel="noopener noreferrer">
          {svg(
            <>
              <rect x="6" y="2" width="12" height="20" rx="2.5" />
              <path d="M11 18h2" />
            </>,
          )}
          Assessor
        </a>
        ) : null}
        <a href="/kushalaya/family/login" target="_blank" rel="noopener noreferrer" className="is-alt">
          {svg(<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" />)}
          Family
        </a>
      </div>
    </div>
  );

  return (
    // `ks-ops` stays on the root: components/ks-shell.css keys the frame's
    // height and overflow off `.site-frame:has(.ks-ops)`.
    <div className={`ks-ops ko-app ${portalFont.variable}`}>
      <header className="ko-topbar">
        <div className="ko-topbar-left">
          <button
            type="button"
            className="ko-burger"
            aria-label="Open menu"
            aria-expanded={drawerOpen}
            aria-controls="ops-drawer"
            onClick={() => setDrawerOpen(true)}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 7h16M4 12h16M4 17h16" />
            </svg>
            {menuBadge > 0 ? (
              <span className="ko-burger-badge">
                <span aria-hidden="true">{menuBadge > 99 ? "99+" : menuBadge}</span>
                <span className="sr-only">{`${menuBadge} open alert${menuBadge === 1 ? "" : "s"}`}</span>
              </span>
            ) : null}
          </button>
          <Link href="/dashboard" className="ko-logo-link">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            {/* One square mark at every width (sized in ops-portal.css). */}
            <img
              src={BRAND_ASSETS.header}
              alt={publicBrandName()}
              width={BRAND_ASSET_SIZE.header.width}
              height={BRAND_ASSET_SIZE.header.height}
              fetchPriority="high"
              decoding="sync"
              className="ko-logo"
            />
          </Link>
        </div>

        <span className="ko-portal-title">
          <span className="is-long">{portalTitle}</span>
          {/* Phones: the logo already says KushAlaya, so just the app name. */}
          <span className="is-short" aria-hidden="true">
            {portalTitle.replace(/^KushAlaya\s+/i, "")}
          </span>
          {tenantLabel && <span className="ko-portal-tenant">{tenantLabel}</span>}
        </span>

        <div className="ko-topbar-right">
          {topbarAction}
          {today && (
            <span className="ko-today" aria-label={`Today, ${today}`}>
              {svg(
                <>
                  <rect x="3" y="5" width="18" height="16" rx="2" />
                  <path d="M8 3v4M16 3v4M3 11h18" />
                </>,
              )}
              {today}
            </span>
          )}
          <OpsProfileMenu
            email={auth.email}
            roleLabel={roleLabelFromKey(auth.role, t)}
            tenantLabel={tenantLabel}
            localeSwitcher={localeSwitcher}
            onLogout={onLogout}
          />
        </div>
      </header>

      <div className="ko-body">
        <aside className="ko-sidebar">
          {nav}
          {apps}
        </aside>

        {drawerOpen && (
          <>
            <div className="ko-scrim" role="presentation" onClick={() => setDrawerOpen(false)} />
            <aside className="ko-drawer" id="ops-drawer" role="dialog" aria-label="Menu">
              <div className="ko-drawer-head">
                {/* The same square mark as the bar, on a white tile. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={BRAND_ASSETS.header}
                  alt={publicBrandName()}
                  width={BRAND_ASSET_SIZE.header.width}
                  height={BRAND_ASSET_SIZE.header.height}
                  className="ko-drawer-logo"
                />
                <button type="button" aria-label="Close menu" onClick={() => setDrawerOpen(false)}>
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M6 6l12 12M18 6L6 18" />
                  </svg>
                </button>
              </div>
              {nav}
              {apps}
            </aside>
          </>
        )}

        <main className="ko-content">
          <div className="ko-main">{children}</div>
        </main>
      </div>
    </div>
  );
}
