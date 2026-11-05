"use client";


import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";

import {
  augmentNavGroupsForRole,
  isNavItemEnabled,
  type ShellLinkProps,
} from "@workforceos/contracts/shell";
import { OpsShell } from "./ops/OpsShell";
import { clearAuth, endSessionRemote, getStoredAuth } from "@/lib/api";
import { badgeText, navBadgeFor, useNavCounts, type NavCounts } from "@/lib/nav-counts";
import {
  canAccessSettings,
  canManageTenants,
  canManageUsers,
  canViewTeam,
} from "@/lib/auth";
import { clearBranding } from "@/lib/branding";
import { useTranslation } from "@/lib/i18n/context";
import { buildAdminNavGroups, filterNavGroupsForLiveWellRole, withoutRetiredOpsNav } from "@/lib/i18n/nav";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { SosBanner } from "@/components/ops/SosBanner";
import { VisitLocationAlerts } from "@/components/ops/VisitLocationAlerts";
import { SosSiren } from "@/components/SosSiren";
import { HeaderSos } from "@/components/ops/HeaderSos";
import { MARKETING_HOME, can, canOpen, isMarketing } from "@/lib/roles";
import { useBranding } from "./BrandingProvider";

/** Staff-side portal name, distinct from the family "Care Hub". */
export const OPS_PORTAL_TITLE = "KushAlaya Ops";

const PendingNavContext = createContext<(href: string) => void>(() => {});
const PendingHrefContext = createContext<string | null>(null);

/** Sidebar badge counts (lib/nav-counts.ts); null until the first poll answers. */
const NavCountsContext = createContext<NavCounts | null>(null);

function NextShellLink({ href, className, onClick, children }: ShellLinkProps) {
  const router = useRouter();
  const setPending = useContext(PendingNavContext);
  const pendingHref = useContext(PendingHrefContext);
  const counts = useContext(NavCountsContext);
  // Menu items only: the logo also links to /dashboard.
  const badge = className?.includes("ko-nav-link") ? navBadgeFor(href, counts) : null;
  const isPending = pendingHref === href;
  const mergedClass =
    isPending && !className?.includes("active")
      ? `${className ?? ""} active`.trim()
      : className;

  return (
    <Link
      href={href}
      className={mergedClass}
      // Prefetch on hover only: prefetching all 14 menu pages at sign-in queued
      // ahead of the dashboard's own data on slow connections.
      prefetch={false}
      onMouseEnter={() => {
        router.prefetch(href);
      }}
      onTouchStart={() => {
        router.prefetch(href);
      }}
      onClick={() => {
        setPending(href);
        onClick?.();
      }}
    >
      {children}
      {badge ? (
        // Right end of the row (ops-portal.css). Screen readers hear "Enquiries, 13 new enquiries" once.
        <span className={`ko-nav-badge is-${badge.tone}`}>
          <span aria-hidden="true">{badgeText(badge.count)}</span>
          <span className="sr-only">, {badge.label}</span>
        </span>
      ) : null}
    </Link>
  );
}

async function unregisterPortalServiceWorkers() {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
  const flag = "lw-admin-sw-cleared-v1";
  try {
    if (sessionStorage.getItem(flag) === "1") return;
  } catch {
    /* ignore */
  }

  const regs = await navigator.serviceWorker.getRegistrations();
  let removed = false;
  for (const reg of regs) {
    const script =
      reg.active?.scriptURL ||
      reg.waiting?.scriptURL ||
      reg.installing?.scriptURL ||
      "";
    if (
      script.includes("kushalaya-sw.js") ||
      script.includes("kushalaya-family-sw.js")
    ) {
      removed = (await reg.unregister()) || removed;
    }
  }
  if ("caches" in window) {
    const keys = await caches.keys();
    await Promise.all(
      keys
        .filter((key) => key.startsWith("livewell-"))
        .map((key) => caches.delete(key)),
    );
  }
  if (removed) {
    try {
      sessionStorage.setItem(flag, "1");
    } catch {
      /* ignore */
    }
    window.location.reload();
  }
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const auth = getStoredAuth();
  const { t } = useTranslation();
  const branding = useBranding();
  const [pendingHref, setPendingHref] = useState<string | null>(null);
  const navCounts = useNavCounts(Boolean(auth));

  useEffect(() => {
    void unregisterPortalServiceWorkers();
  }, []);

  useEffect(() => {
    setPendingHref(null);
  }, [pathname]);

  useEffect(() => {
    if (isMarketing() && !canOpen(pathname)) router.replace(MARKETING_HOME);
  }, [pathname, router]);

  if (!auth) return null;

  const vertical = "LIVEWELL360";
  const allNavGroups = withoutRetiredOpsNav(filterNavGroupsForLiveWellRole(
    augmentNavGroupsForRole({
      groups: buildAdminNavGroups(t, vertical, branding.market),
      t,
      role: auth.role,
      vertical,
      canAccessSettings,
      canViewTeam,
      canManageUsers,
      canManageTenants,
      isNavItemEnabled,
    }),
    auth.role,
    t,
  ));
  const navGroups = isMarketing()
    ? allNavGroups.map((g) => ({ ...g, items: g.items.filter((i) => canOpen(i.href)) })).filter((g) => g.items.length)
    : allNavGroups;

  async function logout() {
    await endSessionRemote();
    clearAuth();
    clearBranding();
    router.replace("/login");
  }

  // The staff portal is named for what it is, so it is not confused with the
  // family-facing Care Hub. The brand name stays as the vertical label.
  const portalTitle = OPS_PORTAL_TITLE;

  return (
    <PendingNavContext.Provider value={setPendingHref}>
      <PendingHrefContext.Provider value={pendingHref}>
        <NavCountsContext.Provider value={navCounts}>
          {pendingHref ? (
            <div className="nav-pending-bar" role="progressbar" aria-label="Loading page" />
          ) : null}
          <OpsShell
            pathname={pathname}
            auth={auth}
            navGroups={navGroups}
            portalTitle={OPS_PORTAL_TITLE}
            onLogout={logout}
            t={t}
            Link={NextShellLink}
            localeSwitcher={<LocaleSwitcher compact market={branding.market} />}
            menuBadge={navCounts?.alerts ?? 0}
            topbarAction={auth && can("edit") && !isMarketing() ? <HeaderSos /> : null}
          >
            {auth ? <SosBanner /> : null}
            {auth ? <VisitLocationAlerts /> : null}
            {/* Alerts page lists the SOS itself: keep the sound, skip the card there. */}
            {auth ? <SosSiren cards={!(pathname ?? "").startsWith("/kushalaya/alerts")} /> : null}
            {children}
          </OpsShell>
        </NavCountsContext.Provider>
      </PendingHrefContext.Provider>
    </PendingNavContext.Provider>
  );
}
