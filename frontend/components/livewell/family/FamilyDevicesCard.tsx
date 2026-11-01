"use client";

import { useEffect, useState } from "react";
import { fetchFamilyDevices, type FamilyDevice } from "@/lib/livewell/familyApi";

function ago(value: string | null): string {
  if (!value) return "never";
  const mins = Math.round((Date.now() - new Date(value).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

/** This client's watches, sensors and home gateway. Renders nothing when none is assigned. */
export function FamilyDevicesCard() {
  const [devices, setDevices] = useState<FamilyDevice[] | null>(null);

  useEffect(() => {
    fetchFamilyDevices()
      .then(setDevices)
      .catch(() => setDevices([]));
  }, []);

  if (!devices || devices.length === 0) return null;

  return (
    <section className="card fh-devices">
      <div className="home-safety-family-report-top">
        <h2>Devices</h2>
        {/* Never "0 of 1 online" beside "Not set up yet". */}
        <span className="muted">
          {devices.every((d) => !d.online && !d.last_seen_at)
            ? "Not set up yet"
            : `${devices.filter((d) => d.online).length} of ${devices.length} online`}
        </span>
      </div>
      <ul className="fh-devices-list">
        {devices.map((d) => (
          <li key={d.id}>
            <span className={`fh-device-dot ${d.online ? "is-on" : "is-off"}`} aria-hidden />
            <div>
              <strong>{d.label}</strong>
              {!d.online && !d.last_seen_at ? (
                <p className="muted">Not set up yet — we&apos;ll connect it at the next visit.</p>
              ) : (
                <p className="muted">
                  {d.online ? "Online" : "Offline"}
                  {d.battery_level != null ? ` · battery ${d.battery_level}%` : ""}
                  {d.last_seen_at ? ` · last seen ${ago(d.last_seen_at)}` : ""}
                  {d.hub_label ? ` · gateway ${d.hub_online ? "online" : "offline"}` : ""}
                </p>
              )}
            </div>
          </li>
        ))}
      </ul>
      {devices.some((d) => !d.online && d.last_seen_at) ? (
        <p className="muted fh-devices-hint">
          Offline usually means the watch is out of range of the gateway, or needs charging.
        </p>
      ) : null}
    </section>
  );
}
