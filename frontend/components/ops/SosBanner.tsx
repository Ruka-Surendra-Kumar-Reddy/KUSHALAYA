"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { acknowledgeIncident, fetchIncidents, type Incident } from "@/lib/livewell/incidentsApi";

const POLL_MS = 10_000;
const CHIME_EVERY_MS = 15_000;
const SOUND_KEY = "ks-sos-sound";

function age(minutes: number) {
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const h = Math.floor(minutes / 60);
  return `${h} h ${minutes % 60} min ago`;
}

/** Two short tones; browsers only allow it after the user has clicked "Turn on sound" once. */
function chime(ctx: AudioContext) {
  [880, 660].forEach((f, i) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.value = f;
    gain.gain.setValueAtTime(0.0001, ctx.currentTime + i * 0.25);
    gain.gain.exponentialRampToValueAtTime(0.3, ctx.currentTime + i * 0.25 + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + i * 0.25 + 0.22);
    osc.connect(gain).connect(ctx.destination);
    osc.start(ctx.currentTime + i * 0.25);
    osc.stop(ctx.currentTime + i * 0.25 + 0.24);
  });
}

/**
 * Red bar on every ops page while an SOS / alert is waiting for someone to acknowledge it.
 * Checks every 10 seconds, chimes until acknowledged, and raises a browser notification for new ones.
 */
export function SosBanner() {
  const onAlerts = (usePathname() ?? "").startsWith("/kushalaya/alerts");
  const [open, setOpen] = useState<Incident[]>([]);
  const [busy, setBusy] = useState<number | null>(null);
  const [soundOn, setSoundOn] = useState(false);
  const audio = useRef<AudioContext | null>(null);
  const seen = useRef<Set<number>>(new Set());

  useEffect(() => {
    try {
      setSoundOn(localStorage.getItem(SOUND_KEY) === "1");
    } catch {
      /* private mode */
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function tick() {
      try {
        const rank = { critical: 0, warning: 1, info: 2 } as const;
        // "escalated" too: an alert nobody acknowledged climbs to escalated — exactly when it matters most.
        const rows = (await fetchIncidents("open,escalated"))
          .filter((i) => i.severity !== "info" && !i.acknowledged_at)
          // Most serious first, then the one waiting longest.
          .sort((a, b) => rank[a.severity] - rank[b.severity] || b.minutes_open - a.minutes_open);
        if (cancelled) return;
        setOpen(rows);
        for (const i of rows) {
          if (seen.current.has(i.id)) continue;
          seen.current.add(i.id);
          try {
            if (typeof Notification !== "undefined" && Notification.permission === "granted") {
              new Notification(`${i.kind_label} — ${i.elder_name ?? "client"}`, {
                body: "Open KushAlaya Ops to acknowledge.",
                tag: `sos-${i.id}`,
              });
            }
          } catch {
            /* Android Chrome only allows notifications from a service worker */
          }
        }
      } catch {
        /* keep the last known list */
      }
    }
    void tick();
    const timer = setInterval(() => void tick(), POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!soundOn || open.length === 0) return;
    if (!audio.current) {
      try {
        audio.current = new AudioContext();
      } catch {
        return;
      }
    }
    const ctx = audio.current;
    chime(ctx);
    const timer = setInterval(() => chime(ctx), CHIME_EVERY_MS);
    return () => clearInterval(timer);
  }, [soundOn, open.length]);

  async function enableSound() {
    try {
      audio.current = audio.current ?? new AudioContext();
      await audio.current.resume();
      localStorage.setItem(SOUND_KEY, "1");
    } catch {
      /* ignore */
    }
    if (typeof Notification !== "undefined" && Notification.permission === "default") {
      await Notification.requestPermission().catch(() => undefined);
    }
    setSoundOn(true);
  }

  function mute() {
    try {
      localStorage.removeItem(SOUND_KEY);
    } catch {
      /* ignore */
    }
    setSoundOn(false);
  }

  async function ack(i: Incident) {
    setBusy(i.id);
    try {
      await acknowledgeIncident(i.id);
      setOpen((list) => list.filter((x) => x.id !== i.id));
    } finally {
      setBusy(null);
    }
  }

  if (open.length === 0) return null;
  const first = open[0];

  return (
    <div className="ks-sos-bar" role="region" aria-label="Unacknowledged alerts">
      <span className="ks-sos-dot" aria-hidden="true" />
      <span className="ks-sos-text">
        <strong aria-live="polite">
          {first.kind_label} — {first.elder_name ?? "a client"}
        </strong>{" "}
        · {age(first.minutes_open)} · not yet acknowledged
        {open.length > 1 ? (
          <Link href="/kushalaya/alerts" className="ks-sos-more">
            {" "}
            (+{open.length - 1} more)
          </Link>
        ) : null}
      </span>
      <span className="ks-sos-actions">
        <button type="button" disabled={busy === first.id} onClick={() => void ack(first)}>
          {busy === first.id ? "Acknowledging…" : "Acknowledge"}
        </button>
        {onAlerts ? null : (
          <Link href="/kushalaya/alerts" className="ks-sos-open">
            Open alerts
          </Link>
        )}
        {soundOn ? (
          <button type="button" className="ks-sos-sound" onClick={mute}>
            Mute
          </button>
        ) : (
          <button type="button" className="ks-sos-sound" onClick={() => void enableSound()}>
            Turn on sound
          </button>
        )}
      </span>
    </div>
  );
}
