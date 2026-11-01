"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, fetchMe, getStoredAuth, storeAuth } from "@/lib/api";

/** "anita.caregiver@x.com" → "Anita Caregiver" — a long address makes a poor
 *  headline, so the local part becomes the display name and the full address
 *  sits underneath. */
function displayNameFrom(email: string): string {
  const local = (email || "").split("@")[0] || "";
  if (!local) return "Account";
  return local
    .split(/[._-]+/)
    .filter(Boolean)
    .map((w) => w[0]!.toUpperCase() + w.slice(1))
    .join(" ");
}

function initialsFrom(email: string): string {
  const source = (email || "").trim();
  if (!source) return "?";
  const parts = source.split(/[\s.@_-]+/).filter(Boolean);
  return (parts.slice(0, 2).map((p) => p[0]).join("") || source[0]!).toUpperCase();
}

/**
 * Account menu for the staff portal — same shape as the family one, so the two
 * apps behave identically for anyone who uses both.
 */
export function OpsProfileMenu({
  email,
  roleLabel,
  tenantLabel,
  localeSwitcher,
  onLogout,
}: {
  email: string;
  roleLabel: string;
  tenantLabel?: string;
  localeSwitcher?: ReactNode;
  onLogout: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [changing, setChanging] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");
  const wrapRef = useRef<HTMLDivElement>(null);
  // The person's real name for the top bar; the email stays the fallback.
  const [fullName, setFullName] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetchMe()
      .then((me) => {
        const name = `${me.first_name || ""} ${me.last_name || ""}`.trim();
        if (!cancelled) setFullName(name);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [email]);

  const shownName = fullName || email || "Account";
  const initials = fullName ? initialsFrom(fullName) : initialsFrom(email);

  useEffect(() => {
    if (!open) return;
    function onPointer(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
        setChanging(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        setChanging(false);
      }
    }
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function submitPassword() {
    setError("");
    setDone("");
    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("New passwords do not match");
      return;
    }
    setBusy(true);
    try {
      const res = await api<{ access_token?: string; refresh_token?: string }>("/api/v1/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      // Older tokens stop working after a password change; keep this session on the new ones.
      const current = getStoredAuth();
      if (current && res?.access_token) {
        storeAuth({ ...current, access_token: res.access_token, refresh_token: res.refresh_token || current.refresh_token });
      }
      setDone("Password updated.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setChanging(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not change password");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ks-profile" ref={wrapRef}>
      <button
        type="button"
        className="ks-avatar-btn"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="ks-avatar">{initials}</span>
        {/* Initials alone don't tell you whose account is open. */}
        <span className="ks-avatar-name">{shownName}</span>
      </button>

      {open && (
        <div className="ks-menu" role="menu">
          <div className="ks-menu-head">
            <span className="ks-avatar ks-avatar-lg">{initials}</span>
            <div className="ks-menu-id">
              <strong>{fullName || displayNameFrom(email)}</strong>
              <span>{email}</span>
              <span className="ks-chip-sm">
                {roleLabel}
                {tenantLabel ? ` · ${tenantLabel}` : ""}
              </span>
            </div>
          </div>

          {done && <p className="ks-menu-note ks-ok">{done}</p>}

          {!changing ? (
            <>
              {localeSwitcher && <div className="ks-menu-locale">{localeSwitcher}</div>}
              <button
                type="button"
                className="ks-menu-item"
                role="menuitem"
                onClick={() => {
                  setChanging(true);
                  setError("");
                  setDone("");
                }}
              >
                Change password
              </button>
              <div className="ks-menu-sep" />
              <button
                type="button"
                className="ks-menu-item ks-menu-danger"
                role="menuitem"
                onClick={onLogout}
              >
                Sign out
              </button>
            </>
          ) : (
            <div className="ks-pwd">
              <label>
                <span>Current password</span>
                <input
                  type="password"
                  autoComplete="current-password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                />
              </label>
              <label>
                <span>New password</span>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                />
              </label>
              <label>
                <span>Confirm new password</span>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </label>
              {error && <p className="ks-menu-note ks-err">{error}</p>}
              <div className="ks-pwd-actions">
                <button type="button" className="secondary" onClick={() => setChanging(false)}>
                  Cancel
                </button>
                <button type="button" disabled={busy} onClick={() => void submitPassword()}>
                  {busy ? "Saving…" : "Update"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
