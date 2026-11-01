"use client";

import { useEffect, useState } from "react";
import { LiveVisitMap, MapAppButtons } from "@/components/LiveVisitMap";
import { useFamilyTimezone } from "@/lib/family-zone";
import {
  caregiverLocationLinks,
  fetchFamilyLiveVisit,
  liveHeadline,
  SHARE_EVERY_MS,
  type LiveVisit,
} from "@/lib/live-location";

/**
 * "Ravi is on the way — about 12 min away" with a small map, while the
 * caregiver is on the way to this family's parent. After arrival it shows
 * "Arrived at 10:02" with no map. Renders nothing otherwise.
 * Polls every 30 s while a visit is on the way (and every 2 min otherwise).
 */
/** "just now", "1 min ago", "25 min ago", then a clock time in the family's own zone. */
function ago(iso: string | null | undefined, tz: string | null, now: number): string {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const min = Math.max(0, Math.round((now - t) / 60000));
  if (min < 1) return "just now";
  if (min < 60) return `${min} min ago`;
  return `at ${new Date(t).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: tz || "Asia/Kolkata" })}`;
}

export function FamilyLiveVisit({ className = "fh-home-card" }: { className?: string }) {
  const [live, setLive] = useState<LiveVisit | null>(null);
  const tz = useFamilyTimezone();
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let onTheWay = false;
    let inFlight = false;
    const hidden = () => typeof document !== "undefined" && document.hidden;
    const tick = () => {
      timer = null;
      if (!alive || inFlight) return;
      if (hidden()) return; // paused while the tab is in the background; resumes on visibilitychange
      inFlight = true;
      fetchFamilyLiveVisit()
        .then((r) => {
          onTheWay = r.live?.state === "on_the_way";
          if (alive) setLive(r.live);
        })
        .catch(() => undefined)
        .finally(() => {
          inFlight = false;
          if (alive && !hidden()) timer = setTimeout(tick, onTheWay ? SHARE_EVERY_MS : 120_000);
        });
    };
    const onVisibility = () => {
      if (hidden()) {
        if (timer) clearTimeout(timer);
        timer = null;
      } else if (!timer) {
        tick(); // back in view: refresh straight away
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    tick();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  if (!live) return null;

  if (live.state === "arrived") {
    return (
      <section className={`${className} lv-card`} aria-label="Visit in progress">
        <p className="lv-head">
          {live.caregiver_first_name} has arrived
        </p>
        <p className="lv-sub">
          {live.arrived_label} · {live.title}
        </p>
      </section>
    );
  }

  const name = live.caregiver_first_name;
  const updated = ago(live.updated_at, tz, now);
  return (
    <section className={`${className} lv-card`} aria-label="Caregiver on the way" aria-live="polite">
      <p className="lv-head">{liveHeadline(live)}</p>
      {live.position ? (
        <>
          <LiveVisitMap
            caregiver={{ lat: live.position.lat, lng: live.position.lng }}
            home={live.home}
            caregiverLabel={name}
          />
          <p className="lv-key" aria-hidden="true">
            <span className="lv-key-cg">●</span> {name} <span className="lv-key-home">○</span> Home
          </p>
          <p className="lv-sub">
            {live.stale ? `Last location ${updated} — ${name} may be out of signal.` : `Updated ${updated}`}
            {" · "}Rough estimate for city traffic.
          </p>
          <MapAppButtons links={caregiverLocationLinks(live)} lead={`See ${name} in`} />
        </>
      ) : (
        <p className="lv-sub">The location will show here once {name}&apos;s phone shares it.</p>
      )}
    </section>
  );
}
