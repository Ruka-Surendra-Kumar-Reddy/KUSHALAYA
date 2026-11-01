"use client";

import { useEffect, useState } from "react";
import { fetchBackupStatus, type BackupStatus } from "@/lib/livewell/privacyApi";
import { DISMISS_DAYS, useDismissed } from "@/lib/dismissed";

function ist(iso?: string | null) {
  return iso
    ? new Date(iso).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", dateStyle: "medium", timeStyle: "short" })
    : "";
}

/**
 * "Last backup: <time> ✓" for admins (#105). Reads the status file the nightly
 * backup script writes; renders nothing for non-admins (the API returns 403).
 */
export function BackupStatusBadge({ detailed = false }: { detailed?: boolean }) {
  const [s, setS] = useState<BackupStatus | null>(null);
  useEffect(() => {
    fetchBackupStatus().then(setS).catch(() => setS(null));
  }, []);
  if (!s) return null;
  // Not set up is a to-do, not a failure: amber with a next step, never red.
  const color = !s.configured ? "#8a5a00" : s.ok ? "#047857" : "#b91c1c";
  const label = !s.configured
    ? "Backups: not set up yet"
    : s.ok
      ? `Last backup: ${ist(s.last_success_at)} ✓`
      : s.last_success_at
        ? `Last backup: ${ist(s.last_success_at)} — ${s.stale ? "overdue" : "last run failed"} ✗`
        : "Last backup: none succeeded ✗";
  return (
    <div style={{ color }} title={s.message || undefined}>
      <strong>{label}</strong>
      {detailed && !s.configured ? (
        <p className="muted" style={{ color: "#4b5b70", fontSize: "0.9em", margin: "4px 0 0" }}>
          Next step (owner): ask your developer to run the backup setup on the server (the nightly backup and its
          off-server storage). This line turns green after the first successful run.
        </p>
      ) : null}
      {detailed && s.configured ? (
        // Only the headline goes red when overdue; the details stay plain unless the restore test failed.
        <div className="muted" style={{ color: s.restore_test_at && s.restore_test_status !== "ok" ? "#b91c1c" : "#4b5b70", fontSize: "0.9em", marginTop: 4 }}>
          {s.remote ? <>Stored off-server at {s.remote}. </> : null}
          {s.restore_test_at ? (
            <>
              Restore test {ist(s.restore_test_at)}: {s.restore_test_status === "ok" ? "passed ✓" : "FAILED ✗"}
              {s.restore_test_detail ? ` (${s.restore_test_detail})` : ""}
            </>
          ) : (
            "No restore test yet."
          )}
        </div>
      ) : null}
    </div>
  );
}

/**
 * Owner dashboard warning (owner/admin only — the API refuses everyone else,
 * so nothing renders for them): backups not set up, failing or overdue.
 */
export function BackupWarning() {
  const [s, setS] = useState<BackupStatus | null>(null);
  useEffect(() => {
    fetchBackupStatus().then(setS).catch(() => setS(null));
  }, []);
  const [hidden, close] = useDismissed("backup-warn");
  if (!s || (s.configured && s.ok) || hidden) return null;
  return (
    <p className="ko-backup-warn" role="status">
      <strong>{!s.configured ? "Backups: not set up" : "Backups: the last run failed or is overdue"}</strong>
      <span>Client records are not copied off the server.</span>
      <a href="/settings/privacy">See backup status</a>
      <button type="button" className="ko-banner-close" onClick={close} aria-label={`Close for ${DISMISS_DAYS} days`} title={`Close for ${DISMISS_DAYS} days`}>
        ✕
      </button>
    </p>
  );
}
