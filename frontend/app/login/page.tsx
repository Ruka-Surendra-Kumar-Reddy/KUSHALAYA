"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AdminLocaleProvider } from "@/components/AdminLocaleProvider";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { clearAuth, login, getStoredAuth } from "@/lib/api";
import { applyTheme } from "@/lib/branding";
import {
  homePathForRole,
  isCaregiverRole,
  isElderPortalRole,
  isStaffRole,
} from "@/lib/auth";
import { PublicBrandMark } from "@/components/BrandLogo";
import { PasswordField, looksLikeSignInName, normalizeEmail } from "@/components/PasswordField";
import { publicBrandName, publicSafetyScoreName } from "@/lib/public-brand";
import { useTranslation } from "@/lib/i18n/context";
import { portalFont } from "@/components/portal-font";
import { isCaregiverHost } from "@/lib/hosts";
import "./login.css";
// See the family sign-in page: load the portal's styles up front so the
// dashboard never flashes unstyled after sign-in.
import "@/components/ks-shell.css";
import "@/components/ops/ops-portal.css";

const Icon = {
  mail: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 7 9 6 9-6" />
    </svg>
  ),
  arrow: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  ),
  calendar: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M8 3v4M16 3v4M3 11h18" />
    </svg>
  ),
  clipboard: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="5" y="4" width="14" height="17" rx="2" />
      <path d="M9 4V3h6v1M9 11l2 2 4-4M9 16h6" />
    </svg>
  ),
  tool: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M14.7 6.3a4 4 0 0 0 4.9 4.9l2.4 2.4-2.8 2.8-2.4-2.4a4 4 0 0 0-4.9-4.9L9.5 6.7 6.7 9.5 4 6.8 6.8 4l2.7 2.7z" />
      <path d="m3 21 6-6" />
    </svg>
  ),
  shield: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3 4 6v6c0 5 3.4 8.4 8 9 4.6-.6 8-4 8-9V6z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  ),
  clock: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </svg>
  ),
  globe: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" />
    </svg>
  ),
  offline: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="6" y="2" width="12" height="20" rx="2.5" />
      <path d="M11 18h2M9 9l6 6M15 9l-6 6" />
    </svg>
  ),
  check: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m5 12 4.5 4.5L19 7" />
    </svg>
  ),
};

/* Three "today" boards the panel flips through: the day as the team sees it. */
const DECK = [
  {
    tone: "",
    kicker: "Example \u00b7 Today",
    title: "6 visits scheduled",
    sub: "2 wellness \u00b7 3 physio \u00b7 1 install",
    icon: Icon.calendar,
    rows: [
      { text: "Lakshmi Reddy \u00b7 Wellness \u00b7 10:00 am", state: "Priya", ok: true },
      { text: "Venkat Rao \u00b7 Physio \u00b7 4:30 pm", state: "Dr. Sanjay", ok: false },
    ],
  },
  {
    tone: "is-green",
    kicker: "Example · Assessment review",
    title: "2 reports awaiting sign-off",
    sub: `${publicSafetyScoreName()} drafts from yesterday`,
    icon: Icon.clipboard,
    rows: [
      { text: "Saraswati Devi \u00b7 74 \u00b7 3 recommendations", state: "Review", ok: false },
      { text: "Padmaja Posa \u00b7 68 \u00b7 5 recommendations", state: "Review", ok: false },
    ],
  },
  {
    tone: "is-gold",
    kicker: "Example · Home installs",
    title: "Grab bars \u00b7 Reddy residence",
    sub: "Installer confirmed for Thursday",
    icon: Icon.tool,
    rows: [
      { text: "Quote approved by family \u00b7 \u20b94,800", state: "Paid", ok: true },
      { text: "Photos due after install", state: "Pending", ok: false },
    ],
  },
];

const TRUST = [
  { icon: Icon.shield, text: "Role-based access" },
  { icon: Icon.clock, text: "Full activity log" },
  { icon: Icon.globe, text: "English & Telugu" },
  { icon: Icon.offline, text: "Assessor app works offline" },
];

/**
 * Read `?redirect=` straight from the URL rather than from the router hook.
 *
 * Reading search params through next/navigation opts the whole tree out of
 * server rendering, so this page's HTML was nothing but "Loading…" — the logo
 * was not in the markup, could not be preloaded, and only appeared once React
 * had downloaded and hydrated. Both callers below run after mount, where
 * window.location carries the same value.
 */
function redirectParam(): string | null {
  if (typeof window === "undefined") return null;
  const value = new URLSearchParams(window.location.search).get("redirect");
  return value && value.startsWith("/") ? value : null;
}

function LoginForm() {
  const router = useRouter();
  const { t } = useTranslation();
  // Local convenience only — a production build renders empty fields, so the
  // public login page never ships working credentials.
  const devPrefill = process.env.NODE_ENV === "development";
  const [email, setEmail] = useState(devPrefill ? "manager@sunrise-care.example" : "");
  const [password, setPassword] = useState(devPrefill ? "demo1234" : "");
  const [emailError, setEmailError] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  // caregiver.kushalaya.com: the same sign-in, worded for caregivers.
  const [caregiverHost, setCaregiverHost] = useState(false);
  useEffect(() => setCaregiverHost(isCaregiverHost(window.location.host)), []);

  useEffect(() => {
    applyTheme("classic");
    const auth = getStoredAuth();
    if (auth && isStaffRole(auth.role)) {
      router.replace(redirectParam() ?? homePathForRole(auth.role));
      return;
    }
    // Warm the portal while the user types: the (app) layout chunk, its CSS
    // and the dashboard RSC payload are what stood between a successful login
    // and any visible change (~1.5–2s on 4G).
    router.prefetch(redirectParam() ?? "/dashboard");
  }, [router]);

  function validate(): boolean {
    const ident = normalizeEmail(email);
    let ok = true;
    if (!ident) {
      setEmailError(t("auth.emailRequired"));
      ok = false;
    } else if (!looksLikeSignInName(ident)) {
      setEmailError(t("auth.emailInvalid"));
      ok = false;
    } else {
      setEmailError("");
    }
    if (!password) {
      setPasswordError(t("auth.passwordRequired"));
      ok = false;
    } else {
      setPasswordError("");
    }
    return ok;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!validate()) return;
    setSubmitting(true);
    try {
      const auth = await login(normalizeEmail(email), password);
      if (isCaregiverRole(auth.role)) {
        // Caregivers sign in here too and land on their own day view.
        router.push(homePathForRole(auth.role));
        return;
      }
      if (!isStaffRole(auth.role)) {
        clearAuth();
        if (isElderPortalRole(auth.role)) {
          setError(t("auth.useFamilyPortal"));
        } else {
          setError(t("auth.staffOnlyLogin"));
        }
        return;
      }
      // Leave the button in its "Signing in…" state: this component is
      // unmounted by the navigation, and re-enabling it first invites a
      // second click while the dashboard is still loading.
      router.push(redirectParam() ?? homePathForRole(auth.role));
      return;
    } catch (err) {
      const message = err instanceof Error ? err.message : "";
      // The API answers a wrong email or password with a bare
      // "Invalid credentials"; say it in the user's language instead.
      setError(
        /invalid credentials/i.test(message)
          ? t("auth.invalidCredentials")
          : /too many sign-in attempts/i.test(message)
            ? t("auth.tooManyAttempts")
            : message || t("auth.loginFailed"),
      );
    }
    setSubmitting(false);
  }

  return (
    // `auth-page` is load-bearing: globals.css pins the copyright footer below
    // the form via `.site-frame:has(> .auth-page)`. Keep it; add, never replace.
    <main className={`auth-page ko-login ${portalFont.variable}`}>
      <div className="ko-login-wrap">
        <section className="ko-login-brand" aria-label={publicBrandName()}>
          <span className="ko-login-blob ko-login-blob-a" aria-hidden="true" />
          <span className="ko-login-blob ko-login-blob-b" aria-hidden="true" />
          <span className="ko-login-grid" aria-hidden="true" />
          <div className="ko-login-brand-inner">
            <div className="ko-login-brand-head">
              <p className="ko-login-brand-eyebrow">
                <i className="ko-login-live" />
                {caregiverHost ? "KushAlaya Caregiver" : "KushAlaya Ops"}
              </p>
              {caregiverHost ? (
                <>
                  <h2>Your visits, your clients, one tap away.</h2>
                  <p className="ko-login-brand-lead">
                    See today&apos;s visits, check in, write the visit report and raise an SOS, from your phone.
                  </p>
                </>
              ) : (
                <>
                  <h2>Run every care day with confidence.</h2>
                  <p className="ko-login-brand-lead">
                    Clients, assessments and visits for the KushAlaya team, in one place, on any
                    device.
                  </p>
                </>
              )}
            </div>

            {caregiverHost ? (
              /* Caregivers see their own day, not manager/owner work or made-up clients. */
              <div className="ko-cg-panel">
                <svg className="ko-cg-art" viewBox="0 0 160 120" aria-hidden="true">
                  <rect x="52" y="8" width="56" height="104" rx="10" fill="rgba(255,255,255,0.14)" stroke="rgba(255,255,255,0.55)" strokeWidth="2" />
                  <rect x="60" y="22" width="40" height="10" rx="3" fill="rgba(255,255,255,0.5)" />
                  <rect x="60" y="40" width="40" height="22" rx="4" fill="rgba(138,184,62,0.85)" />
                  <path d="m71 51 5 5 10-10" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                  <rect x="60" y="70" width="40" height="8" rx="3" fill="rgba(255,255,255,0.35)" />
                  <rect x="60" y="84" width="28" height="8" rx="3" fill="rgba(255,255,255,0.35)" />
                  <circle cx="30" cy="70" r="12" fill="rgba(255,255,255,0.22)" />
                  <path d="M14 108c2-14 10-22 16-22s14 8 16 22" fill="rgba(255,255,255,0.22)" />
                  <circle cx="132" cy="38" r="9" fill="rgba(255,255,255,0.18)" />
                  <path d="M132 33v10M127 38h10" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" />
                </svg>
                <ul className="ko-cg-benefits">
                  <li>
                    <span className="ko-login-trust-ico">{Icon.calendar}</span>
                    Today&apos;s visits with the address, directions and a call button
                  </li>
                  <li>
                    <span className="ko-login-trust-ico">{Icon.check}</span>
                    Check in, tick the checklist and send the visit report in a few taps
                  </li>
                  <li>
                    <span className="ko-login-trust-ico">{Icon.shield}</span>
                    One button for an emergency — your manager is told straight away
                  </li>
                </ul>
              </div>
            ) : (
            <>
            {/* Decorative deck, hidden from assistive tech and from phones. */}
              <div className="ko-deck" aria-hidden="true">
                {DECK.map((c, i) => (
                  <div key={c.kicker} className="ko-live" style={{ ["--i" as string]: i }}>
                    <div className="ko-live-head">
                      <span className={`ko-live-ico ${c.tone}`}>{c.icon}</span>
                      <span className="ko-live-text">
                        <small>{c.kicker}</small>
                        <strong>{c.title}</strong>
                        <span>{c.sub}</span>
                      </span>
                    </div>
                    <ul className="ko-live-rows">
                      {c.rows.map((r) => (
                        <li key={r.text}>
                          <span className={`ko-live-dot${r.ok ? " is-ok" : ""}`}>
                            {r.ok ? Icon.check : null}
                          </span>
                          <span className="ko-live-row-text">{r.text}</span>
                          <span className={`ko-live-state${r.ok ? " is-ok" : ""}`}>{r.state}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
              <div className="ko-deck-dots" aria-hidden="true">
                {DECK.map((c, i) => (
                  <span key={c.kicker} style={{ ["--i" as string]: i }} />
                ))}
              </div>
              <div className="ko-week" aria-hidden="true">
                <p>Example week</p>
                <ul>
                  <li><strong>28</strong><span>visits</span></li>
                  <li><strong>5</strong><span>assessments</span></li>
                  <li><strong>96%</strong><span>on time</span></li>
                </ul>
              </div>
  
              <ul className="ko-login-trust">
                {TRUST.map((x) => (
                  <li key={x.text}>
                    <span className="ko-login-trust-ico">{x.icon}</span>
                    {x.text}
                  </li>
                ))}
              </ul>
            </>
            )}
          </div>
        </section>

        <div className="card auth-card ko-login-card">
          <div className="ko-login-locale">
            <LocaleSwitcher compact />
          </div>
          <PublicBrandMark variant="lockup" className="auth-brand-lockup ko-login-logo" />
          <h1 className="sr-only">{publicBrandName()}</h1>
          <p className="ko-login-eyebrow">{t("auth.loginSubtitle")}</p>
          <p className="ko-login-title">Welcome back</p>
          <p className="muted ko-login-intro">
            Sign in to see today&rsquo;s visits, assessments and client updates.
          </p>
          <form onSubmit={onSubmit} noValidate>
            <div className={`ko-field${emailError ? " has-error" : ""}`}>
              <label htmlFor="email">{t("common.email")}</label>
              <span className="ko-field-input">
                <span className="ko-field-ico">{Icon.mail}</span>
                <input
                  id="email"
                  type="text"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (emailError) setEmailError("");
                  }}
                  autoComplete="username"
                  autoCapitalize="none"
                  spellCheck={false}
                  inputMode="email"
                  aria-invalid={emailError ? true : undefined}
                  aria-describedby={emailError ? "email-error" : undefined}
                />
              </span>
              {emailError && (
                <p id="email-error" className="field-error">
                  {emailError}
                </p>
              )}
            </div>
            <div className={`ko-field${passwordError ? " has-error" : ""}`}>
              <label htmlFor="password">{t("common.password")}</label>
              <PasswordField
                id="password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (passwordError) setPasswordError("");
                }}
                showLabel={t("auth.showPassword")}
                hideLabel={t("auth.hidePassword")}
                invalid={Boolean(passwordError)}
                describedBy={passwordError ? "password-error" : undefined}
              />
              {passwordError && (
                <p id="password-error" className="field-error">
                  {passwordError}
                </p>
              )}
            </div>
            {error && (
              <p className="error ko-login-error" role="alert">
                {error}
              </p>
            )}
            <button
              type="submit"
              className={`ko-login-btn${submitting ? " is-busy" : ""}`}
              disabled={submitting}
            >
              {submitting ? (
                <>
                  <span className="ko-spinner" aria-hidden="true" />
                  {t("auth.signingIn")}
                </>
              ) : (
                <>
                  {t("auth.signIn")}
                  <span className="ko-login-btn-arrow" aria-hidden="true">
                    {Icon.arrow}
                  </span>
                </>
              )}
            </button>
            <p className="ko-login-forgot" style={{ margin: "0.5rem 0 0", textAlign: "center", fontSize: "0.9rem" }}>
              <Link href="/reset-password" style={{ display: "inline-flex", alignItems: "center", minHeight: 44, padding: "0 0.75rem" }}>Forgot password?</Link>
            </p>
          </form>
          <p className="ko-login-alt">
            {/* Plain anchor on purpose: this path redirects to the family host,
                and a Next <Link> prefetch of a cross-origin redirect logs a CORS
                error on every visit to this page. */}
            Family member? <a href="/kushalaya/family/login">{t("auth.familyPortal")}</a>
          </p>
          {devPrefill && (
            /* Working demo logins, including a super admin. Local only — a
               production build must never print credentials on a public page. */
            <p className="muted ko-login-demo">
              {t("auth.demoHint")}
              <br />
              {t("auth.demoHintSuper")}
            </p>
          )}
        </div>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <AdminLocaleProvider>
      <LoginForm />
    </AdminLocaleProvider>
  );
}
