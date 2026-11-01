"use client";

import { BackLink } from "@/components/ops/PageActions";
import "@/components/ops/notifications.css";

/** Settings -> Security. Sessions never time out for inactivity (owner, 2026-10-26). */
export default function SecuritySettingsPage() {
  return (
    <div className="ks-frame is-narrow">
      <header className="ks-head">
        <BackLink href="/settings" label="Settings" />
        <h1>Security</h1>
      </header>
      <section className="card">
        <h2>Sign-out</h2>
        <p className="muted">
          Sessions don&apos;t time out for inactivity. People stay signed in until they press Sign out.
        </p>
      </section>
    </div>
  );
}
