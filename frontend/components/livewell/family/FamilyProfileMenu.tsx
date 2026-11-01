"use client";

import { FamilyLink as Link } from "@/components/livewell/family/FamilyLink";
import { useEffect, useRef, useState } from "react";
import { api, clearAuth, endSessionRemote, getStoredAuth, storeAuth } from "@/lib/api";
import { clearBranding } from "@/lib/branding";
import { hasStaffBackup, restoreStaffSession } from "@/lib/staffImpersonation";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import type { CareTeamContact } from "@/lib/livewell/familyApi";
import { CareTeamButtons, EmergencyNumbers } from "./CareTeamContact";

function initialsFrom(name: string, email: string): string {
  const source = (name || email || "").trim();
  if (!source) return "?";
  const parts = source.split(/[\s.@_-]+/).filter(Boolean);
  const letters = parts.slice(0, 2).map((p) => p[0]);
  return letters.join("").toUpperCase() || source[0]!.toUpperCase();
}

export function FamilyProfileMenu({
  name,
  relationship,
  onSignOut,
  contact,
}: {
  name: string;
  relationship?: string;
  onSignOut: () => void;
  /** Care team phone + WhatsApp (agency setting). */
  contact?: CareTeamContact | null;
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

  const email = getStoredAuth()?.email || "";
  const staffView = hasStaffBackup();

  // Close on outside click / Escape — a menu that traps you feels broken.
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
        <span className="ks-avatar">{initialsFrom(name, email)}</span>
        {/* Initials alone don't tell you whose account is open. Hidden on
            narrow screens, where the top bar has no room for it. */}
        <span className="ks-avatar-name">{name || email || "Account"}</span>
      </button>

      {open && (
        <div className="ks-menu" role="menu">
          <div className="ks-menu-head">
            <span className="ks-avatar ks-avatar-lg">{initialsFrom(name, email)}</span>
            <div className="ks-menu-id">
              <strong>{name || "Family member"}</strong>
              {email && <span>{email}</span>}
              {relationship && <span className="ks-chip-sm">{relationship}</span>}
            </div>
          </div>

          {done && <p className="ks-menu-note ks-ok">{done}</p>}

          {!changing ? (
            <>
              <div className="ks-menu-locale">
                <LocaleSwitcher compact />
              </div>
              <div className="ks-menu-locale">
                <CareTeamButtons contact={contact} compact />
                <EmergencyNumbers contact={contact} />
              </div>
              <Link href="/kushalaya/family/details" className="ks-menu-item" role="menuitem">
                My details
              </Link>
              <Link href="/kushalaya/family/circle" className="ks-menu-item" role="menuitem">
                Family members
              </Link>
              <Link href="/kushalaya/family/digests" className="ks-menu-item" role="menuitem">
                Notifications
              </Link>
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
                Password
              </button>
              <div className="ks-menu-sep" />
              <button
                type="button"
                className="ks-menu-item ks-menu-danger"
                role="menuitem"
                onClick={onSignOut}
              >
                {staffView ? "Back to staff view" : "Sign out"}
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

/** Shared sign-out used by the shell and the menu. */
export async function familySignOut(pushLogin: () => void) {
  if (restoreStaffSession()) {
    window.location.href = "/kushalaya/customers";
    return;
  }
  await endSessionRemote();
  clearAuth();
  clearBranding();
  pushLogin();
}
