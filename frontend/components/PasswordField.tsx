"use client";

import { useState, type ChangeEvent } from "react";

type Props = {
  id: string;
  value: string;
  onChange: (e: ChangeEvent<HTMLInputElement>) => void;
  /** Accessible names for the eye button. */
  showLabel: string;
  hideLabel: string;
  autoComplete?: "current-password" | "new-password";
  invalid?: boolean;
  describedBy?: string;
  className?: string;
};

function EyeIcon({ open }: { open: boolean }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
      {open ? null : <path d="M4 4l16 16" />}
    </svg>
  );
}

/**
 * Password input with a show/hide toggle. The toggle is a real button (not a
 * decorative icon) so it works with keyboards and screen readers, and it is
 * `type="button"` so it never submits the form.
 */
export function PasswordField({
  id,
  value,
  onChange,
  showLabel,
  hideLabel,
  autoComplete = "current-password",
  invalid,
  describedBy,
  className,
}: Props) {
  const [visible, setVisible] = useState(false);
  return (
    <span className={`password-field ${className || ""}`.trim()}>
      <input
        id={id}
        type={visible ? "text" : "password"}
        value={value}
        onChange={onChange}
        autoComplete={autoComplete}
        autoCapitalize="none"
        spellCheck={false}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
      />
      <button
        type="button"
        className="password-toggle"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? hideLabel : showLabel}
        aria-pressed={visible}
        title={visible ? hideLabel : showLabel}
      >
        <EyeIcon open={visible} />
      </button>
    </span>
  );
}

/** Loose shape check — the server is the authority; this only catches typos early. */
/** A mobile number as people type it: +91 98765 43210, 09876543210, 9876543210. */
export function looksLikePhone(value: string): boolean {
  const digits = value.replace(/\D/g, "");
  return /^\+?[0-9 ()-]{6,20}$/.test(value.trim()) && digits.length >= 10 && digits.length <= 13;
}

/** Sign-in name: email or mobile number (both are accepted by /auth/login). */
export function looksLikeSignInName(value: string): boolean {
  return looksLikeEmail(value) || looksLikePhone(value);
}

export function looksLikeEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value);
}

/** What the form sends: trimmed and lower-cased so stray spaces or capitals never fail a login. */
export function normalizeEmail(value: string): string {
  return value.trim().toLowerCase();
}
