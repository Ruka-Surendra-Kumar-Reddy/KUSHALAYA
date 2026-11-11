"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";

type WatchSettings = {
  immobility_enabled: boolean;
  immobility_minutes: number;
  offline_enabled: boolean;
  offline_seconds: number;
  active_hours_start: number;
  active_hours_end: number;
  dedupe_seconds: number;
};

/** Wearables → Band alerts: when a band raises "not moving" and "offline" alerts. */
export function BandAlertSettings() {
  const [s, setS] = useState<WatchSettings | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api<WatchSettings>("/api/v1/iot/watch-settings")
      .then(setS)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  function set<K extends keyof WatchSettings>(key: K, value: WatchSettings[K]) {
    setS((cur) => (cur ? { ...cur, [key]: value } : cur));
    setMsg("");
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!s) return;
    setBusy(true);
    setError("");
    try {
      setS(await api<WatchSettings>("/api/v1/iot/watch-settings", { method: "PUT", body: JSON.stringify(s) }));
      setMsg("Saved. Bands use the new settings within a minute.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  const hour = (h: number) => `${String(h).padStart(2, "0")}:00`;

  return (
    <section className="card iot-alerts" aria-labelledby="iot-alerts-title">
      <h2 id="iot-alerts-title">Band alerts</h2>
      {!s ? (
        <p className="muted">{error || "Loading…"}</p>
      ) : (
        <form onSubmit={save}>
          <div className="iot-alert-row">
            <strong>SOS button</strong>
            <span className="muted">Always on. A second press within {s.dedupe_seconds} seconds counts as the same alert.</span>
          </div>
          <div className="iot-alert-row">
            <label className="iot-alert-switch">
              <input
                type="checkbox"
                checked={s.immobility_enabled}
                onChange={(e) => set("immobility_enabled", e.target.checked)}
              />
              <strong>Not moving</strong>
            </label>
            {s.immobility_enabled ? (
              <div className="iot-alert-fields">
                <label>
                  Alert after (minutes)
                  <input
                    type="number"
                    min={1}
                    max={1440}
                    value={s.immobility_minutes}
                    onChange={(e) => set("immobility_minutes", Number(e.target.value))}
                  />
                </label>
                <label>
                  From
                  <select value={s.active_hours_start} onChange={(e) => set("active_hours_start", Number(e.target.value))}>
                    {Array.from({ length: 24 }, (_, h) => (
                      <option key={h} value={h}>
                        {hour(h)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Until
                  <select value={s.active_hours_end} onChange={(e) => set("active_hours_end", Number(e.target.value))}>
                    {Array.from({ length: 24 }, (_, h) => (
                      <option key={h} value={h}>
                        {hour(h)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            ) : null}
            <span className="muted">Only during these hours, so sleeping at night does not raise alerts.</span>
          </div>
          <div className="iot-alert-row">
            <label className="iot-alert-switch">
              <input type="checkbox" checked={s.offline_enabled} onChange={(e) => set("offline_enabled", e.target.checked)} />
              <strong>Band offline</strong>
            </label>
            {s.offline_enabled ? (
              <div className="iot-alert-fields">
                <label>
                  Alert after (minutes)
                  <input
                    type="number"
                    min={1}
                    max={60}
                    value={Math.round(s.offline_seconds / 60)}
                    onChange={(e) => set("offline_seconds", Number(e.target.value) * 60)}
                  />
                </label>
              </div>
            ) : null}
            <span className="muted">The gateway has not heard the band (out of range, flat battery, gateway off).</span>
          </div>
          {error ? (
            <p className="error" role="alert">
              {error}
            </p>
          ) : null}
          <div className="iot-alert-actions">
            {msg ? <span className="muted">{msg}</span> : null}
            <button type="submit" disabled={busy}>
              {busy ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
