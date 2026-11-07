"use client";

import { CookieNotice, CookieSettingsLink } from "./CookieNotice";
import { PhoneText } from "./PhoneText";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { MkLink as Link } from "./MkLink";
import { usePathname } from "next/navigation";

import { BRAND_ASSETS, BRAND_ASSET_SIZE } from "@/lib/brand-assets";
import { COMPANY_CIN, COMPANY_GSTIN, LEGAL_ENTITY_NAME, publicBrandName } from "@/lib/public-brand";
import {
  BECOME_A_PARTNER_HREF,
  BROCHURE_HREF,
  CONTACT_HREF,
  EMAILS,
  FAMILY_PORTAL_LOGIN,
  FOUNDER_HREF,
  OPS_PORTAL_LOGIN,
  PACKAGES_HREF,
  PARENT_CARE_CHECK_HREF,
  PARTNERS_HREF,
  SAFE_HOMES_HREF,
  VISION_HREF,
  ABOUT_HREF,
  PRIVACY_HREF,
  REFUND_HREF,
  TERMS_HREF,
  US_PHONE,
} from "@/lib/marketing/family-contacts";
import { captureLead, useSiteConfig, whatsAppHref, type SiteConfig } from "@/lib/marketing/site-config";
import { SeoFooterLinks } from "./SeoFooterLinks";
import { SurendraChat } from "./SurendraChat";
import { ICONS } from "./ui";
import { useMkHref } from "./MkLink";

export type MarketingNavItem = { href: string; label: string };

const NAV: MarketingNavItem[] = [
  { href: "/", label: "Home" },
  { href: "/#how", label: "How it works" },
  { href: "/kushlife", label: "KushLife" },
  { href: SAFE_HOMES_HREF, label: "Home safety" },
  { href: PARTNERS_HREF, label: "Partners" },
  // Founder lives inside About (owner, 11 Oct).
  { href: ABOUT_HREF, label: "About" },
  { href: "/blog", label: "Blog" },
  { href: CONTACT_HREF, label: "Contact" },
];

const PORTALS = [
  { href: FAMILY_PORTAL_LOGIN, title: "Family portal", detail: "Visits, reports, photos and alerts" },
  { href: OPS_PORTAL_LOGIN, title: "Ops portal", detail: "For staff and verified partners" },
] as const;

function Mark({ className }: { className?: string }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={BRAND_ASSETS.header}
      alt={publicBrandName()}
      width={BRAND_ASSET_SIZE.header.width}
      height={BRAND_ASSET_SIZE.header.height}
      className={className}
      fetchPriority="high"
      decoding="sync"
    />
  );
}

function SignInMenu() {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  return (
    <div className="mk-signin" ref={rootRef}>
      <button
        type="button"
        className="mk-btn mk-btn-outline mk-signin-btn"
        aria-expanded={open}
        aria-controls="mk-signin-panel"
        onClick={() => setOpen((o) => !o)}
      >
        Sign in
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>
      {open ? (
        <div id="mk-signin-panel" className="mk-signin-panel">
          {PORTALS.map((p) => (
            <a key={p.title} className="mk-signin-item" href={p.href}>
              <strong>{p.title}</strong>
              <span>{p.detail}</span>
            </a>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/** Registered address and CIN; GSTIN and grievance contact only once set in Settings → Website. */
function CompanyDetails({ company }: { company: SiteConfig["company"] }) {
  const grievance = [company.grievance_name, company.grievance_email, company.grievance_phone].filter(Boolean);
  const gstin = company.gstin || COMPANY_GSTIN;
  return (
    <span className="mk-footer-company">
      {company.address ? <span>Registered office: {company.address}</span> : null}
      <span>CIN {COMPANY_CIN}</span>
      <span>GSTIN {gstin}</span>
      {grievance.length ? (
        <span>
          Grievance officer:{" "}
          {company.grievance_name ? `${company.grievance_name}` : null}
          {company.grievance_email ? (
            <>
              {company.grievance_name ? " · " : ""}
              <a href={`mailto:${company.grievance_email}`}>{company.grievance_email}</a>
            </>
          ) : null}
          {company.grievance_phone ? (
            <>
              {" · "}
              <a href={`tel:${company.grievance_phone.replace(/[^\d+]/g, "")}`}>{company.grievance_phone}</a>
            </>
          ) : null}
        </span>
      ) : null}
    </span>
  );
}

export function MarketingShell({
  children,
  primaryCtaHref = PARENT_CARE_CHECK_HREF,
  primaryCtaLabel = "Book assessment",
}: {
  children: ReactNode;
  primaryCtaHref?: string;
  primaryCtaLabel?: string;
}) {
  const pathname = usePathname() || "/";
  const [menuOpen, setMenuOpen] = useState(false);
  const drawerRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const menuBtnRef = useRef<HTMLButtonElement>(null);
  const site = useSiteConfig();
  const waHref = whatsAppHref(site, "Hi, I'd like to know about care for my parents.");

  // First-touch lead tracking (UTM, referrer, landing page, referral code) — FIX 107.
  useEffect(() => {
    captureLead();
  }, []);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  // Modal drawer: focus the close button on open, keep Tab inside, and give
  // focus back to the menu button when it closes.
  useEffect(() => {
    if (!menuOpen) return;
    const opener = (document.activeElement as HTMLElement | null) ?? menuBtnRef.current;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMenuOpen(false);
        return;
      }
      if (e.key !== "Tab" || !drawerRef.current) return;
      const items = Array.from(
        drawerRef.current.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'),
      );
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || !drawerRef.current.contains(active))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (active === last || !drawerRef.current.contains(active))) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
      (opener && document.contains(opener) ? opener : menuBtnRef.current)?.focus();
    };
  }, [menuOpen]);

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/" || pathname === "/marketing";
    if (href.startsWith("/#")) return false;
    if (href === "/blog") return /^\/(marketing\/)?blog(\/|$)/.test(pathname);
    return pathname === href || pathname === `/marketing${href}`;
  };

  const mkHref = useMkHref();
  const primaryIsExternal = /^https?:\/\//i.test(primaryCtaHref);
  const primaryProps = primaryIsExternal
    ? { href: primaryCtaHref, target: "_blank" as const, rel: "noopener noreferrer" }
    : { href: mkHref(primaryCtaHref) };

  return (
    <div className="mk-page">
      <a className="mk-skip" href="#main">
        Skip to content
      </a>

      <header className={`mk-header${scrolled ? " is-scrolled" : ""}`}>
        <div className="mk-header-inner">
          <Link className="mk-logo" href="/" aria-label={`${publicBrandName()} home`}>
            <Mark className="mk-logo-img" />
            <span className="mk-logo-text">{publicBrandName()}</span>
          </Link>

          <nav className="mk-nav" aria-label="Primary">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={isActive(item.href) ? "is-active" : undefined}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="mk-header-ctas">
            <Link className="mk-btn mk-btn-ghost" href={mkHref(PACKAGES_HREF)}>
              Plans
            </Link>
            <a className="mk-btn mk-btn-primary" {...primaryProps}>
              {primaryCtaLabel}
            </a>
            <SignInMenu />
          </div>

          <button
            type="button"
            className="mk-menu-btn"
            ref={menuBtnRef}
            aria-label="Open menu"
            aria-expanded={menuOpen}
            aria-controls="mk-drawer"
            onClick={() => setMenuOpen(true)}
          >
            {ICONS.menu}
          </button>
        </div>
      </header>

      {menuOpen ? (
        <>
          <div className="mk-scrim" role="presentation" onClick={() => setMenuOpen(false)} />
          <aside className="mk-drawer" id="mk-drawer" role="dialog" aria-modal="true" aria-label="Menu" ref={drawerRef}>
            <div className="mk-drawer-head">
              <Mark />
              <button type="button" aria-label="Close menu" ref={closeRef} onClick={() => setMenuOpen(false)}>
                {ICONS.close}
              </button>
            </div>
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`mk-drawer-link${isActive(item.href) ? " is-active" : ""}`}
                onClick={() => setMenuOpen(false)}
              >
                {item.label}
              </Link>
            ))}
            <Link
              href={PACKAGES_HREF}
              className={`mk-drawer-link${isActive(PACKAGES_HREF) ? " is-active" : ""}`}
              onClick={() => setMenuOpen(false)}
            >
              Plans &amp; pricing
            </Link>
            <p className="mk-drawer-title">Sign in</p>
            {PORTALS.map((p) => (
              <a key={p.title} className="mk-signin-item" href={p.href}>
                <strong>{p.title}</strong>
                <span>{p.detail}</span>
              </a>
            ))}
            <div className="mk-drawer-cta">
              <a className="mk-btn mk-btn-white" {...primaryProps}>
                {primaryCtaLabel}
              </a>
              <a className="mk-btn mk-btn-glass" href={`tel:${site.phone_tel}`}>
                {ICONS.phone}
                Call <PhoneText value={site.phone} />
              </a>
            </div>
          </aside>
        </>
      ) : null}

      {site.trial.enabled && site.trial.text ? (
        <div className="mk-trial-banner" role="note">
          <div className="mk-wrap">
            {site.trial.text}{" "}
            <Link href={PARENT_CARE_CHECK_HREF}>Start with KushCare Discovery →</Link>
          </div>
        </div>
      ) : null}

      <main id="main" className="mk-main">
        {children}
      </main>

      <SurendraChat />
      <CookieNotice />

      {/* Phone-only sticky bar: the header CTAs are hidden below 1100px. */}
      <div className="mk-mobile-cta" role="region" aria-label="Quick contact">
        <a className="mk-btn mk-btn-primary" {...primaryProps}>
          {primaryCtaLabel}
        </a>
        <a
          className="mk-btn mk-btn-green"
          href={waHref}
          target="_blank"
          rel="noopener noreferrer"
        >
          {ICONS.whatsapp}
          WhatsApp
        </a>
      </div>

      <footer className="mk-footer">
        <div className="mk-wrap mk-footer-grid">
          <div>
            <div className="mk-footer-brand">
              {/* Full logo with "Safe. Comfortable. Dignified. At home." (owner, 2 Nov 2026). */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                className="mk-footer-lockup"
                src={BRAND_ASSETS.lockup}
                width={BRAND_ASSET_SIZE.lockup.width}
                height={BRAND_ASSET_SIZE.lockup.height}
                alt={`${publicBrandName()}: safe, comfortable, dignified, at home`}
                loading="lazy"
              />
            </div>
            <p>
              Senior home safety and family support. Safe homes. Independent lives. Care that
              protects dignity.
            </p>
          </div>
          <div className="mk-footer-col">
            <p className="mk-footer-label">Explore</p>
            <Link href="/#how">How it works</Link>
            <Link href="/kushlife">KushLife visits</Link>
            <Link href={PACKAGES_HREF}>Plans &amp; pricing</Link>
            <Link href={SAFE_HOMES_HREF}>Why safe homes matter</Link>
            <Link href={FOUNDER_HREF}>From the founder</Link>
            <Link href="/blog">Blog</Link>
            <Link href={VISION_HREF}>Vision sheet</Link>
            <Link href={BROCHURE_HREF}>Brochure</Link>
            <CookieSettingsLink />
          </div>
          <div className="mk-footer-col">
            <p className="mk-footer-label">Families</p>
            <Link href={PARENT_CARE_CHECK_HREF}>KushCare Discovery</Link>
            <Link href={CONTACT_HREF}>Contact us</Link>
            <a href={FAMILY_PORTAL_LOGIN}>Family portal login</a>
            {/* Settings care-team number (defaults to the founder's), so one number shows everywhere. */}
            <a href={`tel:${site.phone_tel}`}>Call <PhoneText value={site.phone} /></a>
            <a href={US_PHONE.tel}>US &amp; Canada: {US_PHONE.display}</a>
            <a href={`mailto:${EMAILS.contact}`}>{EMAILS.contact}</a>
            <Link href={ABOUT_HREF}>About us</Link>
          </div>
          <div className="mk-footer-col">
            <p className="mk-footer-label">Partners</p>
            <Link href={PARTNERS_HREF}>Trusted Partner Network</Link>
            <Link href={BECOME_A_PARTNER_HREF}>Become a partner</Link>
            <a href={`mailto:${EMAILS.sales}`}>{EMAILS.sales}</a>
          </div>
          <SeoFooterLinks />
        </div>
        <div className="mk-wrap mk-footer-copy">
          <span>
            © {new Date().getFullYear()} {site.company.legal_name || LEGAL_ENTITY_NAME}. All rights reserved.
          </span>
          <CompanyDetails company={site.company} />
          <nav className="mk-footer-legal" aria-label="Legal">
            <Link href={PRIVACY_HREF}>Privacy</Link>
            <Link href={TERMS_HREF}>Terms</Link>
            <Link href={REFUND_HREF}>Refunds &amp; cancellation</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
