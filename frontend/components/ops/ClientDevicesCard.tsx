"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { canOpen } from "@/lib/roles";

export type ClientDevice = {
  id: number; // gateways come back as -hub id
  label: string;
  device_type: string;
  kind?: string;
  battery_level: number | null;
  online: boolean;
  last_seen_at: string | null;
};

type FreeOption = { value: string; label: string };

/** Same device name as Wearables: model codes (B7, MG7) hidden. */
function deviceName(d: ClientDevice): string {
  const rest = (d.label || "").replace(/\b(MG7|B7|G1|MG3)\b/gi, "").replace(/\s+/g, " ").trim();
  if (rest && !/^(band|hub|home hub|gateway|watch)$/i.test(rest)) return rest;
  return d.kind === "gateway" ? "Home gateway" : d.kind === "sensor" ? "Sensor" : "SOS watch";
}

function assignPath(value: string): string {
  const [kind, id] = value.split(":");
  return kind === "hub" ? `/api/v1/iot/hubs/${id}/assign` : `/api/v1/iot/devices/${id}/assign`;
}

/** Devices card on the client page: shows this client's devices; assign / unassign them here. */
export function ClientDevicesCard({
  elderId,
  devices,
  formatSeen,
  onChanged,
}: {
  elderId: number;
  devices: ClientDevice[];
  formatSeen: (iso: string) => string;
  onChanged: () => void;
}) {
  const [picking, setPicking] = useState(false);
  const [free, setFree] = useState<FreeOption[] | null>(null);
  const [choice, setChoice] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function openPicker() {
    setPicking(true);
    setError(null);
    setMsg(null);
    setFree(null);
    try {
      const [devs, hubs] = await Promise.all([
        api<{ id: number; label: string; mac_address: string; elder_id: number | null; kind?: string }[]>(
          "/api/v1/iot/devices",
        ),
        api<{ id: number; label: string; mac_address?: string | null; elder_id?: number | null }[]>("/api/v1/iot/hubs"),
      ]);
      const opts: FreeOption[] = [
        ...devs
          .filter((d) => d.elder_id == null)
          .map((d) => ({
            value: `dev:${d.id}`,
            label: `${d.kind === "sensor" ? "Sensor" : "SOS watch"} · ${d.label} · ${d.mac_address}`,
          })),
        ...hubs
          .filter((h) => h.elder_id == null && h.mac_address)
          .map((h) => ({ value: `hub:${h.id}`, label: `Gateway · ${h.label} · ${h.mac_address}` })),
      ];
      setFree(opts);
      setChoice(opts[0]?.value || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function put(path: string, nextElder: number | null, done: string) {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      await api(path, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ elder_id: nextElder }),
      });
      setMsg(done);
      setPicking(false);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function unassign(d: ClientDevice) {
    const name = deviceName(d);
    if (!window.confirm(`Take ${name} away from this client? It will stop alerting anyone.`)) return;
    const path = d.id < 0 ? `/api/v1/iot/hubs/${-d.id}/assign` : `/api/v1/iot/devices/${d.id}/assign`;
    put(path, null, `${name} removed from this client.`);
  }

  return (
    <section className="card">
      <h2>Devices</h2>
      {devices.length === 0 ? <p className="muted">No devices yet.</p> : null}
      <ul className="cp-list">
        {devices.map((d) => (
          <li key={d.id}>
            <strong>{deviceName(d)}</strong>
            {/* Same words as Wearables: "Not heard yet" until the device first reports. */}
            <span className={`cp-pill ${d.online ? "cp-pill-completed" : "cp-pill-open"}`}>
              {d.online ? "Online" : d.last_seen_at ? "Offline" : "Not heard yet"}
            </span>
            <span className="muted">
              {d.battery_level != null ? `Battery ${d.battery_level}% · ` : ""}
              {d.last_seen_at ? `last seen ${formatSeen(d.last_seen_at)}` : "check the gateway is plugged in and the watch is charged"}
            </span>
            <button type="button" className="secondary cp-inline-btn" disabled={busy} onClick={() => unassign(d)}>
              Unassign
            </button>
          </li>
        ))}
      </ul>
      {picking ? (
        <div className="cp-device-pick">
          {free == null && !error ? <span className="muted">Loading…</span> : null}
          {free && free.length === 0 ? (
            <span className="muted">
              No free devices.{" "}
              {canOpen("/kushalaya/iot-devices") ? <Link href="/kushalaya/iot-devices">Add one on Wearables</Link> : null}
            </span>
          ) : null}
          {free && free.length > 0 ? (
            <>
              <select aria-label="Device" value={choice} onChange={(e) => setChoice(e.target.value)}>
                {free.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                disabled={busy || !choice}
                onClick={() => put(assignPath(choice), elderId, "Device given to this client.")}
              >
                {busy ? "Saving…" : "Assign"}
              </button>
            </>
          ) : null}
          <button type="button" className="secondary" disabled={busy} onClick={() => setPicking(false)}>
            Cancel
          </button>
        </div>
      ) : (
        <p>
          <button type="button" className="secondary cp-inline-btn" onClick={openPicker}>
            + Assign a device
          </button>
        </p>
      )}
      {msg ? <p className="muted" role="status">{msg}</p> : null}
      {error ? <p className="cm-error" role="alert">{error}</p> : null}
    </section>
  );
}
