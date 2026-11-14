"use client";

import { SITE_URL } from "@/lib/marketing/family-contacts";
import { PublicBrandMark } from "@/components/BrandLogo";
import { PasswordField, looksLikeSignInName, normalizeEmail } from "@/components/PasswordField";
import { publicBrandFamilyLabel, withPublicBrand } from "@/lib/public-brand";
import { familyFont } from "@/components/livewell/family/family-font";
import { DEFAULT_CARE_CONTACT } from "@/components/livewell/family/CareTeamContact";
import type { CareTeamContact } from "@/lib/livewell/familyApi";
import "./login.css";
// Portal styles load with the sign-in page so the first portal screen is
// never shown unstyled (it flashed blank/dark while its CSS downloaded).
import "@/components/ks-shell.css";
import "@/components/livewell/family/family-portal.css";
import { PulseLine } from "@/components/PulseLine";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { FamilyPwaRegister } from "@/components/livewell/family/FamilyPwaRegister";
import { loginElderPortal } from "@/lib/elderPortal";
import { homePathForRole, isElderPortalRole } from "@/lib/auth";
import { getApiUrl, getStoredAuth } from "@/lib/api";
import { familyDashboardPath } from "@/lib/livewell/family-paths";

/** Demo credentials are a local convenience only — never ship them to a real
 *  login page, where anyone could just press Sign in. NODE_ENV is fixed at
 *  build time, so a production build always renders empty fields. */
const DEV_PREFILL = process.env.NODE_ENV === "development";

/**
 * Where the dashboard lives from the browser's point of view: `/dashboard` on
 * family.kushalaya.com, `/kushalaya/family/dashboard` on the ops host (where
 * `/dashboard` is the STAFF dashboard). Resolved per host by the shared helper.
 */
const dashboardPath = familyDashboardPath;

/** Public site, linked from the logo. */
const MARKETING_HOME = SITE_URL;

const HELP_PREFILL = withPublicBrand(
  "Hi LiveWell360 — I use the Family portal and need help signing in.",
);

/* Small inline icons — the page is public and must not depend on the portal
   shell, so it carries its own. */
const Icon = {
  heart: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" />
    </svg>
  ),
  check: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m5 12 4.5 4.5L19 7" />
    </svg>
  ),
  chat: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M21 12a8 8 0 0 1-8 8H7l-4 3V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8z" />
    </svg>
  ),
  phone: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 4h3l2 5-2.5 1.5a11 11 0 0 0 5 5L14 13l5 2v3a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z" />
    </svg>
  ),
  calendar: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M8 3v4M16 3v4M3 11h18" />
    </svg>
  ),
  shield: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3 4 6v6c0 5 3.4 8.4 8 9 4.6-.6 8-4 8-9V6z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  ),
  arrow: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  ),
  mail: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 7 9 6 9-6" />
    </svg>
  ),
  alert: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3 2 20h20z" />
      <path d="M12 9v5M12 17h.01" />
    </svg>
  ),
  pin: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z" />
      <circle cx="12" cy="9.5" r="2.5" />
    </svg>
  ),
  globe: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" />
    </svg>
  ),
  headset: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 14v-2a8 8 0 0 1 16 0v2" />
      <rect x="3" y="13" width="4" height="6" rx="1.5" />
      <rect x="17" y="13" width="4" height="6" rx="1.5" />
      <path d="M19 19a3 3 0 0 1-3 3h-3" />
    </svg>
  ),
  walk: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="13" cy="4" r="1.6" />
      <path d="m9 21 2-6 3 2v4M8 12l3-4 3 1 2 3h3M11 8l-1 5-3 2" />
    </svg>
  ),
};

/* Example stories (illustrative, names changed), rotating on their own loop
   (six seconds each). These are scenarios, not reviews: no ratings. */
const QUOTES = [
  {
    initials: "R",
    text: "Ravi lives in Dubai; his mother lives alone in Hyderabad. He gets a KushLife summary after every visit, so he knows how her day went before he sits down for dinner.",
    who: "Ravi",
    role: "Son · Dubai",
  },
  {
    initials: "S",
    text: "Suresh works in Singapore. After the home safety visit flagged the bathroom and the dark corridor, he approved grab bars and night lights for his father from the portal.",
    who: "Suresh",
    role: "Son · Singapore",
  },
  {
    initials: "M",
    text: "Meena is in Bengaluru. She opens the visit report with photos each week to see what the caregiver checked and what needs her attention.",
    who: "Meena",
    role: "Daughter · Bengaluru",
  },
  {
    initials: "L",
    text: "Lakshmi’s mother-in-law has a named Family Partner. Lakshmi messages her from Chennai whenever something about Atha’s routine changes.",
    who: "Lakshmi",
    role: "Daughter-in-law · Chennai",
  },
  {
    initials: "A",
    text: "Arun and Kavya are listed as emergency contacts for their grandmother. If she presses SOS, the care team calls her and then calls them.",
    who: "Arun & Kavya",
    role: "Grandchildren",
  },
  {
    initials: "P",
    text: "Priyanka lives in London. She chose a WhatsApp digest at the end of each day instead of an alert for every small update.",
    who: "Priyanka",
    role: "Daughter · London",
  },
];

const TRUST = [
  { icon: Icon.alert, text: "SOS & emergency contacts" },
  { icon: Icon.pin, text: "Local care team" },
  { icon: Icon.globe, text: "English & Telugu" },
  { icon: Icon.headset, text: "SOS any time" },
];

export default function FamilyLoginPage() {
  // On family.kushalaya.com "/login" is this page; staff sign in on the ops host.
  const [opsLoginHref, setOpsLoginHref] = useState("/login");
  useEffect(() => {
    document.title = `Sign in · ${publicBrandFamilyLabel()}`;
    const { protocol, hostname, port } = window.location;
    if (hostname.startsWith("family.")) {
      setOpsLoginHref(`${protocol}//ops.${hostname.slice("family.".length)}${port ? `:${port}` : ""}/login`);
    }
  }, []);

  const router = useRouter();
  const [email, setEmail] = useState(
    DEV_PREFILL ? "lakshmi.family@sunrise-care.example" : "",
  );
  const [password, setPassword] = useState(DEV_PREFILL ? "demo1234" : "");
  const [emailError, setEmailError] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const helpCloseRef = useRef<HTMLButtonElement>(null);
  // The care team's public phone / WhatsApp (falls back to the founder's number).
  const [careContact, setCareContact] = useState<CareTeamContact>(DEFAULT_CARE_CONTACT);
  useEffect(() => {
    let live = true;
    fetch(`${getApiUrl()}/api/v1/home-safety/family/public/care-team-contact`)
      .then((r) => (r.ok ? r.json() : null))
      .then((c: CareTeamContact | null) => {
        if (live && c?.phone_tel) setCareContact(c);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);

  // Support popup: focus its close button, close on Escape.
  useEffect(() => {
    if (!helpOpen) return;
    helpCloseRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setHelpOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [helpOpen]);

  useEffect(() => {
    const stored = getStoredAuth();
    if (stored && isElderPortalRole(stored.role)) {
      router.replace(dashboardPath());
      return;
    }
    // Warm the portal shell + dashboard while the user types (see /login).
    router.prefetch(dashboardPath());
  }, [router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setEmailError("");
    setPasswordError("");
    const ident = normalizeEmail(email);
    let bad = false;
    if (!ident) {
      setEmailError("Enter your email or mobile number.");
      bad = true;
    } else if (!looksLikeSignInName(ident)) {
      setEmailError("Enter a valid email address or mobile number.");
      bad = true;
    }
    if (!password) {
      setPasswordError("Enter your password.");
      bad = true;
    }
    if (bad) return;
    setSubmitting(true);
    try {
      const auth = await loginElderPortal(ident, password);
      // Keep "Signing in…" up until the navigation unmounts this page.
      if (!isElderPortalRole(auth.role)) {
        router.push(homePathForRole(auth.role));
        return;
      }
      router.push(dashboardPath());
      return;
    } catch (err) {
      const message = err instanceof Error ? err.message : "";
      setError(
        /invalid credentials/i.test(message)
          ? "Email, mobile number or password is incorrect. Please try again."
          : /too many sign-in attempts/i.test(message)
            ? "Too many sign-in attempts. Try again in 15 minutes, or reset your password using “Forgot password?” below."
            : message || "Login failed",
      );
    }
    setSubmitting(false);
  }

  // Shown inside the popup only when a number is configured for this build.
  const help = careContact;
  const helpWa = `${help.whatsapp_link}?text=${encodeURIComponent(HELP_PREFILL)}`;

  return (
    // The four home-safety-* classes are load-bearing: globals.css keys the
    // sticky copyright footer and the frame height off `home-safety-family-login`
    // as a direct child of .site-frame. Keep them; add, never replace.
    <main
      className={`home-safety-app home-safety-family home-safety-family-portal home-safety-family-login fh-login ${familyFont.variable}`}
    >
      <FamilyPwaRegister />
      <div className="fh-login-wrap">
        {/* Brand panel: the pitch plus a looping "live flow" of a care day.
            Decorative — hidden from assistive tech, compact on phones. The
            page's one logo is in the sign-in card. */}
        <section className="fh-login-brand" aria-label={withPublicBrand("About LiveWell360 Family")}>
          <span className="fh-login-blob fh-login-blob-a" aria-hidden="true" />
          <span className="fh-login-blob fh-login-blob-b" aria-hidden="true" />
          <span className="fh-login-grid" aria-hidden="true" />
          <div className="fh-login-brand-inner">
            <div className="fh-login-brand-head">
              <p className="fh-login-brand-eyebrow">
                Family portal
              </p>
              <h2>Peace of mind, wherever you are.</h2>
              <p className="fh-login-brand-lead">
                Follow your parents&rsquo; care at home, from the next room or the
                other side of the world.
              </p>
            </div>

            <PulseLine
              title="KushLife pulse"
              value="58"
              status="Thriving"
              caption="Every visit, four checks. Here is how Lakshmi is doing today."
              items={[
                { label: "Safe", note: "Night light fixed, grab bars checked" },
                { label: "Steady", note: "Walked to the park" },
                { label: "Settled", note: "Sleeping well, meals on time" },
                { label: "Connected", note: "Video call with her son" },
              ]}
            />
            <div className="fh-login-stories-head">
              <h3>How families use KushAlaya</h3>
              <p>Example stories &middot; names changed, illustrative</p>
            </div>
            <div className="fh-login-quotes">
              {QUOTES.map((q, i) => (
                <figure
                  key={q.initials}
                  className="fh-login-quote"
                  style={{ ["--i" as string]: i }}
                >
                  <p className="fh-login-quote-text">{q.text}</p>
                  <figcaption>
                    <span className="fh-login-quote-avatar">{q.initials}</span>
                    <span>
                      <strong>{q.who}</strong>
                      <small>{q.role}</small>
                    </span>
                  </figcaption>
                </figure>
              ))}
            </div>

            <ul className="fh-login-trust">
              {TRUST.map((t) => (
                <li key={t.text}>
                  <span className="fh-login-trust-ico">{t.icon}</span>
                  {t.text}
                </li>
              ))}
            </ul>
          </div>
        </section>

        <div className="card home-safety-family-login-card fh-login-card">
          <a href={MARKETING_HOME} className="fh-login-logo-link" aria-label="KushAlaya website">
            <PublicBrandMark variant="lockup" className="fh-login-logo" />
          </a>
          <p className="fh-login-eyebrow">Welcome back</p>
          <h1>Sign in to your family portal</h1>
          <p className="muted fh-login-intro">
            See how your loved one is doing, book visits, and reach the care team.
          </p>

          <form onSubmit={(e) => void onSubmit(e)} noValidate>
            <label
              className={`home-safety-field fh-field${emailError ? " has-error" : ""}`}
              htmlFor="family-email"
            >
              <span className="fh-field-label">Email or mobile number</span>
              <span className="fh-field-input">
                <span className="fh-field-ico">{Icon.mail}</span>
                <input
                  id="family-email"
                  type="text"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (emailError) setEmailError("");
                  }}
                  autoComplete="username"
                  autoCapitalize="none"
                  spellCheck={false}
                  aria-invalid={emailError ? true : undefined}
                  aria-describedby={emailError ? "family-email-error" : undefined}
                />
              </span>
              {emailError && (
                <span id="family-email-error" className="fh-field-error" role="alert">
                  {emailError}
                </span>
              )}
            </label>

            <label
              className={`home-safety-field fh-field${passwordError ? " has-error" : ""}`}
              htmlFor="family-password"
            >
              <span className="fh-field-label">Password</span>
              <PasswordField
                id="family-password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (passwordError) setPasswordError("");
                }}
                showLabel="Show password"
                hideLabel="Hide password"
                invalid={Boolean(passwordError)}
                describedBy={passwordError ? "family-password-error" : undefined}
              />
              {passwordError && (
                <span id="family-password-error" className="fh-field-error" role="alert">
                  {passwordError}
                </span>
              )}
            </label>

            {error && (
              <p className="error-text fh-login-error" role="alert">
                {error}
              </p>
            )}

            <button
              type="submit"
              className={`primary home-safety-family-login-btn fh-login-btn${
                submitting ? " is-busy" : ""
              }`}
              disabled={submitting}
            >
              {submitting ? (
                <>
                  <span className="fh-spinner" aria-hidden="true" />
                  Signing in…
                </>
              ) : (
                <>
                  Sign in
                  <span className="fh-login-btn-arrow" aria-hidden="true">
                    {Icon.arrow}
                  </span>
                </>
              )}
            </button>
            <p className="fh-login-forgot" style={{ margin: "0.5rem 0 0", textAlign: "center", fontSize: "0.9rem" }}>
              <Link href="/reset-password" style={{ display: "inline-flex", alignItems: "center", minHeight: 44, padding: "0 0.75rem" }}>Forgot password?</Link>
            </p>
          </form>

          <p className="fh-login-trouble-row">
            <button
              type="button"
              className="fh-login-trouble"
              onClick={() => setHelpOpen(true)}
              aria-haspopup="dialog"
              aria-expanded={helpOpen}
            >
              Trouble signing in?
            </button>
          </p>

          <p className="fh-login-alt">
            Staff member? <a href={opsLoginHref}>Sign in to KushAlaya Ops</a>
          </p>
        </div>
      </div>

      {helpOpen && (
        <div className="fh-modal-scrim" role="presentation" onClick={() => setHelpOpen(false)}>
          <div
            className="fh-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="fh-help-title"
            onClick={(e) => e.stopPropagation()}
          >
            <span className="fh-modal-ico" aria-hidden="true">
              {Icon.phone}
            </span>
            <h2 id="fh-help-title">Contact your Family Partner</h2>
            <p>
              For sign-in help, a forgotten password, or a new device, please contact your Care
              Manager for support. They will sort it out in minutes.
            </p>
            <a href={`tel:${help.phone_tel}`} className="fh-modal-action">
              {Icon.phone}
              Call {help.phone}
            </a>
            <a href={helpWa} className="fh-modal-action" target="_blank" rel="noopener noreferrer">
              {Icon.chat}
              WhatsApp {help.whatsapp}
            </a>
            <button
              type="button"
              className="fh-modal-close"
              ref={helpCloseRef}
              onClick={() => setHelpOpen(false)}
            >
              Got it
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
