"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PublicBrandMark } from "@/components/BrandLogo";
import { LiveVisitMap } from "@/components/LiveVisitMap";
import { familyFont } from "@/components/livewell/family/family-font";
import { API_URL } from "@/lib/api";
import { PUBLIC_PHONE } from "@/lib/public-brand";
import type { PublicTrack } from "@/lib/live-location";
import "./track.css";

const POLL_MS = 15_000;

function ago(iso: string | null): string {
  if (!iso) return "";
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return "just now";
  const m = Math.round(s / 60);
  return m < 60 ? `${m} min ago` : `${Math.round(m / 60)} h ago`;
}

/**
 * Live tracking link from the family's "on the way" email / message. No login: the
 * signed link is the key. Shows who is coming, where they are and a rough ETA while
 * they are on the way; "Arrived" after; nothing else about the client.
 */
export default function TrackPage() {
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<PublicTrack | null>(null);
  const [bad, setBad] = useState(false);
  const [road, setRoad] = useState<{ minutes: number; km: number } | null>(null);
  const [, tick] = useState(0);

  useEffect(() => {
    let stop = false;
    async function load() {
      try {
        const res = await fetch(`${API_URL}/api/v1/home-safety/track/${encodeURIComponent(token)}`, { cache: "no-store" });
        if (res.status === 404) {
          if (!stop) setBad(true);
          return;
        }
        if (res.ok && !stop) setData((await res.json()) as PublicTrack);
      } catch {
        /* offline for a moment: keep the last position */
      }
    }
    void load();
    const poll = window.setInterval(() => {
      if (document.visibilityState === "visible") void load();
    }, POLL_MS);
    const clock = window.setInterval(() => tick((n) => n + 1), 30_000); // refresh "x min ago"
    return () => {
      stop = true;
      window.clearInterval(poll);
      window.clearInterval(clock);
    };
  }, [token]);

  const live = data?.state === "on_the_way" ? data : null;

  return (
    <main className={`tk-page ${familyFont.className}`}>
      <header className="tk-head">
        <PublicBrandMark className="tk-logo" />
        <span className="tk-live-tag">{live ? "Live tracking" : "Tracking"}</span>
      </header>

      <section className="tk-card" aria-live="polite">
        {bad ? (
          <>
            <h1>This link has expired</h1>
            <p className="tk-muted">Tracking links work only while the visit is on the way.</p>
          </>
        ) : !data ? (
          <p className="tk-muted">Finding the latest location…</p>
        ) : live ? (
          <>
            <p className="tk-kicker">
              <span className="tk-dot" aria-hidden="true" /> On the way · {live.title}
            </p>
            <h1>{live.name} is on the way</h1>
            {!live.position || live.eta_minutes != null ? (
              <p className="tk-eta">
                {!live.position
                  ? "Waiting for the first location…"
                  : live.eta_minutes === 0
                    ? "Arriving now"
                    : road
                      ? `Arriving in about ${road.minutes} min · ${road.km} km`
                      : live.eta_label.startsWith("about")
                      ? `Arriving in ${live.eta_label}`
                      : live.eta_label[0].toUpperCase() + live.eta_label.slice(1)}
              </p>
            ) : null}
            {live.position ? (
              <>
                <div className="tk-map">
                  <LiveVisitMap caregiver={live.position} home={live.home} caregiverLabel={live.name} onRoute={setRoad} />
                </div>
                <p className="tk-muted">
                  Updated {ago(live.updated_at)}
                  {live.stale ? " · location not updated for a few minutes" : ""}
                </p>
              </>
            ) : (
              <p className="tk-muted">The map appears as soon as their phone shares a location.</p>
            )}
          </>
        ) : data.state === "arrived" ? (
          <>
            <p className="tk-kicker is-done">Arrived · {data.title}</p>
            <h1>{data.name} has arrived</h1>
            <p className="tk-eta">{data.arrived_label}</p>
          </>
        ) : (
          <>
            <h1>This visit is no longer on the way</h1>
            <p className="tk-muted">Tracking stops when the visit is done.</p>
          </>
        )}
      </section>

      <p className="tk-help">
        Questions? Call us on <a href={PUBLIC_PHONE.tel}>{PUBLIC_PHONE.display}</a>
      </p>
    </main>
  );
}
