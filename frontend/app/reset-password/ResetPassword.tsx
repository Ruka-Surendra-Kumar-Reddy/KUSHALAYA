"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { getApiUrl } from "@/lib/api";
import { PublicBrandMark } from "@/components/BrandLogo";
import { portalFont } from "@/components/portal-font";
import "../login/login.css";
import "./reset-password.css";

/** FastAPI errors: a string, or (422) a list of {loc, msg}. */
function readableError(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((d) => {
      const field = Array.isArray(d?.loc) ? String(d.loc[d.loc.length - 1]) : "";
      const msg = typeof d?.msg === "string" ? d.msg.replace(/^Value error, /, "") : "";
      if (field === "password") return "Use a password of at least 8 characters.";
      if (field === "email") return "Enter a valid email address.";
      if (field === "token") return "This reset link is invalid or has expired. Ask for a new one.";
      return msg;
    });
    const text = Array.from(new Set(parts.filter(Boolean))).join(" ");
    if (text) return text;
  }
  return "Something went wrong. Please try again.";
}

async function post(path: string, body: unknown): Promise<void> {
  const res = await fetch(`${getApiUrl()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(readableError(data.detail));
  }
}

function ResetPasswordInner() {
  const params = useSearchParams();
  const [token] = useState(() => params.get("token") || "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  // Keep the token out of the address bar, history and any later Referer.
  useEffect(() => {
    if (token && typeof window !== "undefined" && window.location.search.includes("token=")) {
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, [token]);

  async function onRequest(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await post("/api/v1/auth/forgot-password", { email: email.trim().toLowerCase() });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send the link");
    } finally {
      setBusy(false);
    }
  }

  async function onReset(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < 8) return setError("Use a password of at least 8 characters.");
    if (password !== confirm) return setError("The two passwords don't match.");
    setBusy(true);
    try {
      await post("/api/v1/auth/reset-password", { token, password });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reset the password");
    } finally {
      setBusy(false);
    }
  }

  const errorBox = error && (
    <p className="error ko-login-error" role="alert">
      {error}
    </p>
  );

  let body: React.ReactNode;
  if (token && done) {
    body = (
      <>
        <p className="ko-login-title">Password changed</p>
        <p className="muted ko-login-intro">You can now sign in with your new password.</p>
        <Link className="ko-login-btn rp-btn-link" href="/login">Go to sign in</Link>
      </>
    );
  } else if (token) {
    body = (
      <>
        <p className="ko-login-title">Choose a new password</p>
        <p className="muted ko-login-intro">Use at least 8 characters.</p>
        <form onSubmit={onReset} noValidate>
          <div className="ko-field">
            <label htmlFor="rp-new">New password</label>
            <span className="ko-field-input">
              <input
                id="rp-new"
                type={show ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
              />
            </span>
          </div>
          <div className="ko-field">
            <label htmlFor="rp-confirm">Confirm new password</label>
            <span className="ko-field-input">
              <input
                id="rp-confirm"
                type={show ? "text" : "password"}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                autoComplete="new-password"
              />
            </span>
          </div>
          <label className="rp-show">
            <input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} /> Show passwords
          </label>
          {errorBox}
          <button type="submit" className={`ko-login-btn${busy ? " is-busy" : ""}`} disabled={busy}>
            {busy ? "Saving…" : "Save new password"}
          </button>
        </form>
        <Link href="/reset-password" className="rp-link">Link expired? Get a new one</Link>
      </>
    );
  } else if (done) {
    body = (
      <>
        <p className="ko-login-title">Check your email</p>
        <p className="muted ko-login-intro">
          If that email has an account, a reset link is on its way. It can take a minute — check spam too.
        </p>
        <Link className="rp-link" href="/login">Back to sign in</Link>
      </>
    );
  } else {
    body = (
      <>
        <p className="ko-login-title">Forgot your password?</p>
        <p className="muted ko-login-intro">Enter the email you sign in with and we&rsquo;ll send you a reset link.</p>
        <form onSubmit={onRequest} noValidate>
          <div className="ko-field">
            <label htmlFor="rp-email">Email</label>
            <span className="ko-field-input">
              <input
                id="rp-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                inputMode="email"
                required
              />
            </span>
          </div>
          {errorBox}
          <button type="submit" className={`ko-login-btn${busy ? " is-busy" : ""}`} disabled={busy || !email.trim()}>
            {busy ? "Sending…" : "Send reset link"}
          </button>
        </form>
        <Link className="rp-link" href="/login">Back to sign in</Link>
      </>
    );
  }

  return (
    <main className={`auth-page ko-login ${portalFont.variable}`}>
      <div className="ko-login-wrap rp-wrap">
        <div className="card auth-card ko-login-card">
          <PublicBrandMark variant="lockup" className="auth-brand-lockup ko-login-logo rp-logo" />
          {body}
        </div>
      </div>
    </main>
  );
}

/** Forgot password (no token: ask for the email) and reset (token from the emailed link). */
export default function ResetPassword() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordInner />
    </Suspense>
  );
}
