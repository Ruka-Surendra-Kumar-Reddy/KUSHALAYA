"use client";

import { FamilyLink as Link } from "@/components/livewell/family/FamilyLink";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import { BRAND_ASSETS, BRAND_ASSET_SIZE } from "@/lib/brand-assets";
import { publicBrandFamilyLabel, publicBrandName } from "@/lib/public-brand";
import {
  fetchFamilyDashboard,
  fetchFamilyWallet,
  setActiveFamilyElder,
  type CareTeamContact,
  type FamilyLinkedElder,
} from "@/lib/livewell/familyApi";
import { hasStaffBackup, restoreStaffSession } from "@/lib/staffImpersonation";
import { familyLoginPath } from "@/lib/livewell/family-paths";
import { FamilyProfileMenu, familySignOut } from "./FamilyProfileMenu";
import { FamilyNavList, FamilyTabBar, NAV_ICONS } from "./FamilyNav";
import { FAMILY_HELP_TOGGLE, FamilyHelpChat } from "./FamilyHelpChat";
import { CareTeamButtons, EmergencyNumbers } from "./CareTeamContact";
import { inr } from "@/lib/business";
// The account menu keeps its ks-* classes, whose base styles live in the
// shared shell sheet; family-portal.css re-skins them under .fh-app.
import "@/components/ks-shell.css";
import "./family-portal.css";

/** Shown next to the logo so the header is never just a bare image. */
export const PORTAL_TITLE = "KushAlaya Family";
/** Was the narrow-phone title; phones now show the brand name (Phase 2E audit). */
export const PORTAL_TITLE_SHORT = "Care Hub";

export function initialsOf(name: string): string {
  const parts = (name || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "•";
  return parts
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("");
}

export type FamilyShellContext = {
  parentName: string;
  seniorName: string;
  seniorAddress: string | null;
  unread: number;
  balance: string | null;
  /** Rendered "Viewing" dropdown when more than one senior is linked, else null. */
  switcher: React.ReactNode;
  /** Care team phone + WhatsApp (agency setting); null until loaded. */
  contact: CareTeamContact | null;
};

export function FamilyShell({
  title,
  docTitle,
  subtitle,
  hero,
  back,
  children,
}: {
  title: string;
  /** Back link shown above the heading ("← All updates"), 44px tall. */
  back?: { href: string; label: string };
  /** Browser tab title when it should differ from the heading ("Dashboard"). */
  docTitle?: string;
  subtitle?: string;
  /**
   * Home renders its own greeting banner instead of the plain page heading.
   * The shell hands over what it already knows (names, unread count, the
   * senior switcher) so the page does not fetch it twice.
   */
  hero?: (ctx: FamilyShellContext) => React.ReactNode;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [unread, setUnread] = useState(0);
  const [elders, setElders] = useState<FamilyLinkedElder[]>([]);
  const [activeElderId, setActiveElderId] = useState<number | null>(null);
  const [parentName, setParentName] = useState("");
  const [seniorName, setSeniorName] = useState("");
  const [seniorAddress, setSeniorAddress] = useState<string | null>(null);
  const [balance, setBalance] = useState<string | null>(null);
  const [contact, setContact] = useState<CareTeamContact | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [pending, startTransition] = useTransition();
  const [staffView, setStaffView] = useState(false);
  // Each page gets its own tab title: "Updates · KushAlaya Family".
  useEffect(() => {
    document.title = `${docTitle || title} · ${publicBrandFamilyLabel()}`;
  }, [docTitle, title]);

  useEffect(() => {
    setStaffView(hasStaffBackup());
  }, []);

  useEffect(() => {
    fetchFamilyDashboard()
      .then((d) => {
        setUnread(d.unread_alerts);
        setElders(d.elders ?? []);
        setActiveElderId(d.active_elder_id ?? null);
        setParentName(d.parent_name || "");
        setSeniorName(d.senior_name || "");
        setSeniorAddress(d.senior_address ?? null);
        setContact(d.care_team_contact ?? null);
      })
      .catch(() => {
        setUnread(0);
        setElders([]);
      });
  }, [pathname]);

  useEffect(() => {
    // Convenience only — stay quiet if the wallet call fails.
    fetchFamilyWallet()
      // Same format as the Wallet page: "₹200", paise only when there are some.
      .then((w) => setBalance(inr(w.balance_minor)))
      .catch(() => setBalance(null));
  }, [pathname]);

  // Route change closes the drawer; leaving it open over new content feels broken.
  useEffect(() => {
    setDrawerOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!drawerOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setDrawerOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  function onElderChange(nextId: number) {
    if (!nextId || nextId === activeElderId) return;
    startTransition(async () => {
      try {
        await setActiveFamilyElder(nextId);
        window.location.assign(pathname || "/kushalaya/family/dashboard");
      } catch {
        /* keep prior selection */
      }
    });
  }

  const activeElder =
    elders.find((e) => e.id === activeElderId) ?? elders.find((e) => e.is_active) ?? elders[0];
  const shownSenior = activeElder?.name || seniorName;
  const shownAddress = activeElder?.address ?? seniorAddress;

  const switcher =
    elders.length > 1 ? (
      <label className="fh-elder-switch">
        <span>Viewing</span>
        <select
          value={activeElderId ?? elders[0]?.id ?? ""}
          disabled={pending}
          aria-label="Select senior"
          onChange={(e) => onElderChange(Number(e.target.value))}
        >
          {elders.map((e) => (
            <option key={e.id} value={e.id}>
              {e.name}
            </option>
          ))}
        </select>
      </label>
    ) : null;

  // The senior's name and address are shown by the top bar's account menu and
  // the Home hero, so the sidebar carries only the menu and the help card.

  const helpCard = (
    <div className="fh-side-help is-slim">
      <div className="fh-side-help-head">
        <strong>Need help?</strong>
        <button
          type="button"
          className="fh-side-help-ask"
          onClick={() => {
            setDrawerOpen(false);
            window.dispatchEvent(new Event(FAMILY_HELP_TOGGLE));
          }}
        >
          ? Ask us
        </button>
      </div>
      {/* One row: Call · WhatsApp · SOS, so the card doesn't push the menu away. */}
      <div className="fh-side-help-row">
        <CareTeamButtons contact={contact} compact />
        <div className="fh-side-help-actions">
          <Link href="/kushalaya/family/alerts" className="is-sos" aria-label="SOS — raise an alert">
            {NAV_ICONS.sos}
            SOS
          </Link>
        </div>
      </div>
      <EmergencyNumbers contact={contact} />
    </div>
  );

  return (
    <div className="fh-app">
      {staffView && (
        <div className="fh-staff-banner">
          <span>Viewing as family</span>
          <button
            type="button"
            onClick={() => restoreStaffSession() && (window.location.href = "/kushalaya/customers")}
          >
            Back to staff
          </button>
        </div>
      )}

      <header className="fh-topbar">
        <div className="fh-topbar-left">
          <button
            type="button"
            className="fh-burger"
            aria-label="Open menu"
            aria-expanded={drawerOpen}
            onClick={() => setDrawerOpen(true)}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 7h16M4 12h16M4 17h16" />
            </svg>
          </button>
          <Link href="/kushalaya/family/dashboard" className="fh-logo-link">
            {/* One square mark at every width (it used to be a <picture> that
                swapped a wide wordmark for the emblem below 900px; the brand
                is a single square mark now). The portal layout preloads it. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={BRAND_ASSETS.header}
              alt={publicBrandName()}
              width={BRAND_ASSET_SIZE.header.width}
              height={BRAND_ASSET_SIZE.header.height}
              fetchPriority="high"
              decoding="sync"
              className="fh-logo"
            />
            {/* Brand name beside the mark on laptop-size screens only. */}
            <span className="fh-logo-text">{publicBrandName()}</span>
          </Link>
        </div>

        {/* Direct child of the grid so it centres against the bar, not the logo. */}
        <span className="fh-portal-title">
          <span className="is-long">{PORTAL_TITLE}</span>
          {/* Phones: the logo already says KushAlaya, so just the app name (owner, 28 Oct). */}
          <span className="is-short" aria-hidden="true">
            Family
          </span>
        </span>

        <div className="fh-topbar-right">
          {balance && (
            <Link href="/kushalaya/family/wallet" className="fh-wallet-chip" title="Wallet balance">
              {NAV_ICONS.wallet}
              <span>{balance}</span>
            </Link>
          )}
          <Link
            href="/kushalaya/family/alerts"
            className="fh-bell"
            aria-label={unread > 0 ? `Alerts, ${unread} unread` : "Alerts"}
            title="Alerts"
          >
            {NAV_ICONS.digests}
            {unread > 0 && <span className="fh-bell-count">{unread > 9 ? "9+" : unread}</span>}
          </Link>
          {/* Phones: help opens from the header, so no floating button covers the page.
              Desktop uses the sidebar's "? Ask us". */}
          <button
            type="button"
            className="fh-bell fh-help-btn"
            aria-label="Help"
            title="Help"
            onClick={() => window.dispatchEvent(new Event(FAMILY_HELP_TOGGLE))}
          >
            ?
          </button>
          <FamilyProfileMenu
            name={parentName}
            relationship="Family"
            contact={contact}
            // Host-aware: on family.kushalaya.com this is /login, not the internal path.
            onSignOut={() => void familySignOut(() => router.push(familyLoginPath()))}
          />
        </div>
      </header>

      <div className="fh-body">
        <aside className="fh-sidebar">
          <FamilyNavList pathname={pathname} unread={unread} />
          {helpCard}
        </aside>

        {drawerOpen && (
          <>
            <div className="fh-scrim" role="presentation" onClick={() => setDrawerOpen(false)} />
            <aside className="fh-drawer" role="dialog" aria-label="Menu">
              <div className="fh-drawer-head">
                <span>{PORTAL_TITLE}</span>
                <button type="button" aria-label="Close menu" onClick={() => setDrawerOpen(false)}>
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M6 6l12 12M18 6L6 18" />
                  </svg>
                </button>
              </div>
              <FamilyNavList
                pathname={pathname}
                unread={unread}
                onNavigate={() => setDrawerOpen(false)}
              />
              {helpCard}
            </aside>
          </>
        )}

        <main className="fh-content">
          {hero ? (
            hero({
              parentName,
              seniorName: shownSenior,
              seniorAddress: shownAddress ?? null,
              unread,
              balance,
              switcher,
              contact,
            })
          ) : (
            <div className="fh-pagehead">
              <div className="fh-pagehead-text">
                {back ? (
                  <Link href={back.href} className="fh-pagehead-back">
                    {back.label}
                  </Link>
                ) : null}
                <h1>{title}</h1>
                {subtitle && <p>{subtitle}</p>}
              </div>
              {switcher}
            </div>
          )}
          {/* Not .home-safety-main — that carries overflow-y:auto and a
              max-width:28rem meant for the old fixed-height shell. */}
          <div className="fh-main">{children}</div>
        </main>
      </div>

      <FamilyTabBar pathname={pathname} unread={unread} />
      <FamilyHelpChat />
    </div>
  );
}
