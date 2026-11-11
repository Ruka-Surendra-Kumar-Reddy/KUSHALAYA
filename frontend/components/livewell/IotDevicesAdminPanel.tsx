"use client";

import { FormEvent, useCallback, useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { BandAlertSettings } from "@/components/livewell/BandAlertSettings";
import "@/components/ops/wearables.css";
import "@/components/ops/commerce.css";

type ElderOption = { id: number; first_name: string; last_name: string };
type HubRow = {
  id: number;
  label: string;
  mqtt_username: string;
  mqtt_password?: string;
  mqtt_topic: string;
  home_key: string;
  hub_key: string;
  status: string;
  mqtt_provision?: { ok: boolean; detail: string };
  mac_address?: string | null;
  elder_id?: number | null;
  http_url?: string | null;
  last_seen_at?: string | null;
  bands_heard?: number | null;
};
type DeviceRow = {
  id: number;
  label: string;
  mac_address: string;
  elder_id: number | null;
  kind?: "watch" | "sensor";
  last_rssi?: number | null;
  hub_id: number | null;
  hub_label?: string | null;
  status: string;
  notes?: string | null;
  battery_level?: number | null;
  last_seen_at?: string | null;
  motion_xyz?: string | null;
  last_motion_at?: string | null;
};
type KitResult = {
  hub: HubRow;
  device: DeviceRow;
  minewlink: {
    broker_host: string;
    broker_port: number;
    tls: boolean;
    username: string;
    password: string;
    topic: string;
    subscribe_topic?: string;
    reply_topic?: string;
    topic_mode?: string;
    source?: string;
  };
  beaconset: { mac_address: string; enable_sos_advertising: boolean };
  next_steps: string[];
};

type HeardResult = {
  last_seen_at: string | null;
  online: boolean;
  battery_level: number | null;
  rssi: number | null;
  via?: string | null;
};

type AddKind = "watch" | "gateway" | "sensor";

/** "AC233F123456", "ac-23-3f-12-34-56" → "ac:23:3f:12:34:56"; null when not 12 hex digits. */
export function normalizeMac(raw: string): string | null {
  const hex = raw.replace(/[^0-9a-f]/gi, "").toLowerCase();
  if (hex.length !== 12) return null;
  return hex.match(/../g)!.join(":");
}

type BrokerSettings = {
  broker_host: string;
  broker_port: number;
  tls: boolean;
  hub_username: string;
  hub_password: string;
  ingestor_username: string;
  ingestor_password: string;
  ingestor_mqtt_topic: string;
  dedupe_seconds: number;
  immobility_enabled: boolean;
  immobility_minutes: number;
  offline_enabled: boolean;
  offline_seconds: number;
  quiet_period_minutes: number;
  active_hours_start: number;
  active_hours_end: number;
  timezone: string;
  watch_policy_version?: number;
  topic_mode: string;
  subscribe_topic: string;
  reply_topic: string;
  use_shared_hub: boolean;
  notes?: string;
  source?: string;
  /** The API never returns passwords: they come back "" with these flags. Blank on save = keep. */
  hub_password_set?: boolean;
  ingestor_password_set?: boolean;
  /** Set after "Load from file": a blank password on save takes the file's value. */
  from_credentials_file?: boolean;
};

const DEFAULT_INGESTOR_TOPIC =
  "livewell/homes/+/hubs/+/ble,mg7/+/status,/mg7/+/status";

const WEARABLE_TIMEZONES = [
  { value: "Asia/Kolkata", label: "India (Asia/Kolkata)" },
  { value: "Asia/Dubai", label: "Dubai (Asia/Dubai)" },
  { value: "Asia/Singapore", label: "Singapore (Asia/Singapore)" },
  { value: "Europe/London", label: "UK (Europe/London)" },
  { value: "America/New_York", label: "US Eastern (America/New_York)" },
  { value: "America/Chicago", label: "US Central (America/Chicago)" },
  { value: "America/Los_Angeles", label: "US Pacific (America/Los_Angeles)" },
  { value: "Australia/Sydney", label: "Sydney (Australia/Sydney)" },
  { value: "UTC", label: "UTC" },
] as const;

function clampInt(value: number, lo: number, hi: number, fallback: number) {
  if (!Number.isFinite(value)) return fallback;
  return Math.max(lo, Math.min(hi, Math.trunc(value)));
}

function elderDisplayName(
  elders: ElderOption[],
  elderId: number | string | null | undefined,
): string {
  const id = Number(elderId);
  if (!Number.isFinite(id) || id <= 0) return "Unknown client";
  const match = elders.find((e) => e.id === id);
  if (!match) return `Client #${id}`;
  const name = `${match.first_name || ""} ${match.last_name || ""}`.trim();
  return name || `Client #${id}`;
}

/** Matches the jobs runner (backend band_checks.py). */
const BAND_OFFLINE_MS = 2 * 60 * 60 * 1000;
const BAND_LOW_BATTERY = 20;

/** Plain name for a band or hub label: hides model codes like "MG7" / "B7". */
function plainDeviceName(label: string, kind: "band" | "hub"): string {
  const rest = label.replace(/\b(MG7|B7)\b/gi, "").replace(/\s+/g, " ").trim();
  if (!rest || /^(band|hub|home hub)$/i.test(rest)) return kind === "band" ? "Band" : "Home hub";
  return rest;
}

type BandHealth = { label: string; tone: "ok" | "warn" | "bad" | "new"; rank: number };

function bandHealth(d: DeviceRow, now: Date): BandHealth {
  const seen = d.last_seen_at ? parseIso(d.last_seen_at) : null;
  if (seen == null) return { label: "Not heard yet", tone: "new", rank: 2 };
  if (now.getTime() - seen >= BAND_OFFLINE_MS) return { label: "Offline", tone: "bad", rank: 0 };
  if (d.battery_level != null && d.battery_level <= BAND_LOW_BATTERY)
    return { label: "Battery low", tone: "warn", rank: 1 };
  return { label: "Online", tone: "ok", rank: 3 };
}

/** API times without a zone are UTC (SQLite drops it); never read them as local time. */
function parseIso(iso: string): number {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`).getTime();
}

/** "Moving · X 0.02g Y -0.98g Z 0.10g" from the band's accelerometer (raw units: 256 = 1 g). */
function motionText(d: DeviceRow, now: Date): string {
  const parts = (d.motion_xyz || "").split(",").map(Number);
  if (parts.length !== 3 || parts.some((n) => !Number.isFinite(n))) return "";
  const g = (n: number) => `${(n / 256).toFixed(2)}g`;
  const moved = d.last_motion_at ? parseIso(d.last_motion_at) : null;
  const moving = moved != null && now.getTime() - moved < 60_000;
  const state = moving ? "Moving" : moved != null ? `Still, last moved ${timeAgo(d.last_motion_at, now)}` : "Still";
  return `${state} · X ${g(parts[0])} Y ${g(parts[1])} Z ${g(parts[2])}`;
}

function timeAgo(iso: string | null | undefined, now: Date): string {
  if (!iso) return "never";
  const mins = Math.max(0, Math.round((now.getTime() - parseIso(iso)) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 48) return `${hours} h ${mins % 60} min ago`;
  return `${Math.floor(hours / 24)} days ago`;
}

const PILL: Record<BandHealth["tone"], { bg: string; fg: string }> = {
  ok: { bg: "#dcfce7", fg: "#166534" },
  warn: { bg: "#fef3c7", fg: "#92400e" },
  bad: { bg: "#fee2e2", fg: "#b91c1c" },
  new: { bg: "#e2e8f0", fg: "#334155" },
};

function formatTimeInZone(date: Date, timeZone: string): string {
  try {
    return new Intl.DateTimeFormat("en-IN", {
      timeZone: timeZone || "UTC",
      weekday: "short",
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
    }).format(date);
  } catch {
    return new Intl.DateTimeFormat("en-IN", {
      timeZone: "UTC",
      weekday: "short",
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
    }).format(date);
  }
}

const emptyBroker: BrokerSettings = {
  broker_host: "ops.kushalaya.com",
  broker_port: 8883,
  tls: true,
  hub_username: "mg7_home1",
  hub_password: "",
  // Blank on purpose: the API fills the server default when this is empty
  // (see _normalize in backend/app/livewell/iot_broker_settings.py).
  ingestor_username: "",
  ingestor_password: "",
  ingestor_mqtt_topic: DEFAULT_INGESTOR_TOPIC,
  dedupe_seconds: 65,
  immobility_enabled: true,
  immobility_minutes: 30,
  offline_enabled: true,
  offline_seconds: 180,
  quiet_period_minutes: 60,
  active_hours_start: 7,
  active_hours_end: 21,
  timezone: "Asia/Kolkata",
  watch_policy_version: 2,
  topic_mode: "minew_status",
  subscribe_topic: "",
  reply_topic: "",
  use_shared_hub: true,
};

export function IotDevicesAdminPanel({ header }: { header?: ReactNode } = {}) {
  const [elders, setElders] = useState<ElderOption[]>([]);
  const [hubs, setHubs] = useState<HubRow[]>([]);
  const [devices, setDevices] = useState<DeviceRow[]>([]);
  const [broker, setBroker] = useState<BrokerSettings>(emptyBroker);
  const [brokerBusy, setBrokerBusy] = useState(false);
  const [showHubPassword, setShowHubPassword] = useState(true);
  const [showIngestorPassword, setShowIngestorPassword] = useState(true);

  const [elderId, setElderId] = useState("");
  const [mac, setMac] = useState("");
  const [bandLabel, setBandLabel] = useState("");
  const [addKind, setAddKind] = useState<AddKind>("watch");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<"give" | "swap" | null>(null);
  const [heard, setHeard] = useState<Record<string, string>>({});
  const [setupOpenId, setSetupOpenId] = useState<number | null>(null);

  const [updateElderId, setUpdateElderId] = useState("");
  const [updateMac, setUpdateMac] = useState("");
  const [updateBusy, setUpdateBusy] = useState(false);
  const [updateMsg, setUpdateMsg] = useState<string | null>(null);

  const [editMacById, setEditMacById] = useState<Record<number, string>>({});
  const [rowBusyId, setRowBusyId] = useState<number | null>(null);
  const [replacingId, setReplacingId] = useState<number | null>(null);
  const [hubBusyId, setHubBusyId] = useState<number | null>(null);
  const [clockNow, setClockNow] = useState(() => new Date());

  useEffect(() => {
    const id = window.setInterval(() => setClockNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const load = useCallback(async () => {
    const [e, h, d, b] = await Promise.all([
      api<ElderOption[]>("/api/v1/elders"),
      api<HubRow[]>("/api/v1/iot/hubs"),
      api<DeviceRow[]>("/api/v1/iot/devices"),
      api<BrokerSettings>("/api/v1/iot/broker-settings"),
    ]);
    setElders(e);
    setHubs(h);
    setDevices(d);
    setBroker({ ...emptyBroker, ...b });
    const drafts: Record<number, string> = {};
    for (const row of d) {
      drafts[row.id] = row.mac_address;
    }
    setEditMacById(drafts);
  }, []);

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [load]);

  async function onSaveBroker(ev: FormEvent) {
    ev.preventDefault();
    setBrokerBusy(true);
    setError(null);
    setUpdateMsg(null);
    try {
      const saved = await api<BrokerSettings>("/api/v1/iot/broker-settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(broker),
      });
      setBroker({ ...emptyBroker, ...saved });
      setUpdateMsg(
        `Saved MQTT + band-watch settings (${saved.hub_username} @ ${saved.broker_host}). Watch policy reaches the ingestor within ~30s; Apply to Mosquitto is only for hub/ingestor passwords and MQTT_TOPIC.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBrokerBusy(false);
    }
  }

  async function onLoadCredentialsFile() {
    setBrokerBusy(true);
    setError(null);
    try {
      const fromFile = await api<BrokerSettings>("/api/v1/iot/broker-settings/load-credentials-file", {
        method: "POST",
      });
      setBroker((prev) => ({ ...prev, ...fromFile, from_credentials_file: true }));
      setUpdateMsg("Loaded from .credentials.app — click Save broker settings to persist in the app.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBrokerBusy(false);
    }
  }

  async function onApplyMosquitto() {
    setBrokerBusy(true);
    setError(null);
    try {
      const result = await api<{ ok: boolean; detail: string }>(
        "/api/v1/iot/broker-settings/apply-mosquitto",
        { method: "POST" },
      );
      if (result.ok) {
        setUpdateMsg(`Mosquitto updated: ${result.detail}`);
      } else {
        setError(`Mosquitto apply failed: ${result.detail}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBrokerBusy(false);
    }
  }

  async function onAddDevice(ev: FormEvent) {
    ev.preventDefault();
    const cleanMac = normalizeMac(mac);
    if (!cleanMac) {
      setError("The MAC needs 12 letters or numbers, e.g. AC:23:3F:12:34:56.");
      return;
    }
    setBusy(true);
    setError(null);
    setUpdateMsg(null);
    try {
      const result = await api<{ id: number; label: string }>("/api/v1/iot/add-device", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kind: addKind,
          mac_address: cleanMac,
          label: bandLabel.trim() || null,
          elder_id: elderId ? Number(elderId) : null,
        }),
      });
      setUpdateMsg(
        addKind === "gateway"
          ? `Gateway added. Set it up with the upload link below.`
          : `Added ${result.label}${elderId ? ` for ${elderDisplayName(elders, elderId)}` : ""}.`,
      );
      if (addKind === "gateway") setSetupOpenId(result.id);
      setMac("");
      setBandLabel("");
      setDrawer(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onTest(kind: "devices" | "hubs", id: number) {
    const key = `${kind}-${id}`;
    setHeard((prev) => ({ ...prev, [key]: "Checking…" }));
    try {
      const r = await api<HeardResult>(`/api/v1/iot/${kind}/${id}/heard`);
      const parts = [
        r.last_seen_at ? `Last heard ${timeAgo(r.last_seen_at, new Date())}` : "Not heard yet",
        r.online ? "online" : "offline",
        r.battery_level != null ? `battery ${r.battery_level}%` : "",
        r.rssi != null ? `signal ${r.rssi} dBm` : "",
        r.via ? `via ${plainDeviceName(r.via, "hub")}` : "",
      ].filter(Boolean);
      setHeard((prev) => ({ ...prev, [key]: parts.join(" · ") }));
    } catch (err) {
      setHeard((prev) => ({ ...prev, [key]: err instanceof Error ? err.message : String(err) }));
    }
  }

  async function onAssign(path: string, name: string, value: string) {
    const nextId = value ? Number(value) : null;
    if (!nextId && !window.confirm(`Unassign ${name}? It will not alert anyone until you give it to a client.`)) {
      return;
    }
    setError(null);
    setUpdateMsg(null);
    try {
      await api(path, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ elder_id: nextId }),
      });
      setUpdateMsg(nextId ? `${name} now belongs to ${elderDisplayName(elders, nextId)}.` : `${name} is not assigned now.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function onNewLink(hub: HubRow) {
    if (!window.confirm("Make a new upload link? The old link stops working, so update the gateway right after.")) return;
    setHubBusyId(hub.id);
    setError(null);
    try {
      await api(`/api/v1/iot/hubs/${hub.id}/http-token`, { method: "POST" });
      setSetupOpenId(hub.id);
      setUpdateMsg("New upload link made. Paste it into the gateway.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setHubBusyId(null);
    }
  }

  async function onCopy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setUpdateMsg("Link copied.");
    } catch {
      setUpdateMsg("Copy did not work. Select the link and copy it.");
    }
  }

  async function onUpdateMac(ev: FormEvent) {
    ev.preventDefault();
    setUpdateBusy(true);
    setError(null);
    setUpdateMsg(null);
    try {
      const updated = await api<DeviceRow>("/api/v1/iot/devices/mac", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          elder_id: Number(updateElderId),
          mac_address: updateMac.trim(),
        }),
      });
      setUpdateMsg(
        `Updated ${elderDisplayName(elders, updated.elder_id)} now uses band ${updated.mac_address}`,
      );
      setUpdateMac("");
      setDrawer(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setUpdateBusy(false);
    }
  }

  async function onSaveRowMac(device: DeviceRow) {
    const nextMac = (editMacById[device.id] || "").trim();
    if (!nextMac || nextMac.toLowerCase() === device.mac_address.toLowerCase()) {
      return;
    }
    setRowBusyId(device.id);
    setError(null);
    setUpdateMsg(null);
    try {
      const updated = await api<DeviceRow>("/api/v1/iot/devices/mac", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          elder_id: device.elder_id,
          device_id: device.id,
          mac_address: nextMac,
        }),
      });
      setUpdateMsg(
        `Band replaced for ${elderDisplayName(elders, updated.elder_id)} — new Band ID ${updated.mac_address}`,
      );
      setReplacingId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRowBusyId(null);
    }
  }

  async function onSendTest(device: DeviceRow) {
    setRowBusyId(device.id);
    setError(null);
    setUpdateMsg(null);
    try {
      const res = await api<{ sent_to: string[]; email_connected: boolean }>(
        `/api/v1/iot/devices/${device.id}/test`,
        { method: "POST" },
      );
      const who = res.sent_to.length ? res.sent_to.join(", ") : "nobody (no alert recipients set)";
      setUpdateMsg(
        `Test alert for ${elderDisplayName(elders, device.elder_id)} sent to ${who}.` +
          (res.email_connected ? "" : " Email is not connected yet, so it was only logged."),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRowBusyId(null);
    }
  }

  async function onDeleteDevice(device: DeviceRow) {
    const ok = window.confirm(
      `Remove band ${device.mac_address} from ${elderDisplayName(elders, device.elder_id)}?\n\nSOS alerts from this band will stop until you add it again.`,
    );
    if (!ok) return;
    setRowBusyId(device.id);
    setError(null);
    setUpdateMsg(null);
    try {
      await api(`/api/v1/iot/devices/${device.id}`, { method: "DELETE" });
      setUpdateMsg(
        `Removed band ${device.mac_address} (${elderDisplayName(elders, device.elder_id)})`,
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRowBusyId(null);
    }
  }

  async function onDeleteHub(hub: HubRow) {
    const ok = window.confirm(
      `Remove hub "${plainDeviceName(hub.label, "hub")}"?\n\nBands stay linked to their clients.`,
    );
    if (!ok) return;
    setHubBusyId(hub.id);
    setError(null);
    setUpdateMsg(null);
    try {
      await api(`/api/v1/iot/hubs/${hub.id}`, { method: "DELETE" });
      setUpdateMsg(`Removed hub ${plainDeviceName(hub.label, "hub")}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setHubBusyId(null);
    }
  }

  // "Last heard" times come from the server; reload them so an open page doesn't
  // keep counting up ("3 min ago") while the gateway is still uploading.
  useEffect(() => {
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") void load().catch(() => undefined);
    }, 20_000);
    return () => window.clearInterval(id);
  }, [load]);

  const registerHint = !mac.trim() ? "Type the MAC to continue." : "";
  const swapHint = !updateElderId ? "Choose a client first." : !updateMac.trim() ? "Type the new Band ID to continue." : "";
  const clientOptions = elders.map((e) => (
    <option key={e.id} value={e.id}>
      {`${e.first_name} ${e.last_name}`.trim() || `Client #${e.id}`}
    </option>
  ));

  return (
    <div className="iot-page">
      <div className="ks-head-row">
        {header ?? <div />}
        <div className="ks-head-actions">
          <button
            type="button"
            onClick={() => { setError(null); setDrawer("give"); }}
            aria-label="Add device"
            title="Add device"
          >
            <span className="ks-ha-icon" aria-hidden="true">+</span>
            <span className="ks-ha-label">+ Add device</span>
          </button>
        </div>
      </div>

      {error && !drawer && (
        <p role="alert" style={{ color: "var(--danger, #b91c1c)", margin: 0 }}>
          {error}
        </p>
      )}
      {updateMsg && (
        <p style={{ color: "var(--success, #166534)", margin: 0 }}>{updateMsg}</p>
      )}

      <section className="card iot-card">
        <h2 className="iot-card-title">
          Watches and sensors <span className="iot-count">{devices.length}</span>
        </h2>
        {devices.length === 0 ? (
          <p className="muted" style={{ margin: 0 }}>
            None yet. Use <strong>Add device</strong> above.
          </p>
        ) : (
          <ul className="iot-list">
            {[...devices]
              .sort((a, b) => bandHealth(a, clockNow).rank - bandHealth(b, clockNow).rank)
              .map((d) => {
              const draft = editMacById[d.id] ?? d.mac_address;
              const dirty = draft.trim().toLowerCase() !== d.mac_address.toLowerCase();
              const health = bandHealth(d, clockNow);
              const busyRow = rowBusyId === d.id;
              return (
                <li key={d.id} className="iot-row">
                  <div className="iot-row-info">
                  <div className="iot-row-head">
                    <strong className={d.elder_id ? undefined : "muted"}>
                      {d.elder_id ? elderDisplayName(elders, d.elder_id) : "Not assigned"}
                    </strong>
                    <span className="iot-pill" style={{ background: PILL[health.tone].bg, color: PILL[health.tone].fg }}>
                      {health.label}
                    </span>
                    {(() => {
                      // "Band" on its own says nothing next to the status chip: show only names that add something.
                      const parts = [
                        d.kind === "sensor" ? "Sensor" : "SOS watch",
                        plainDeviceName(d.label, "band") === "Band" ? "" : plainDeviceName(d.label, "band"),
                        d.hub_label ? `via ${plainDeviceName(d.hub_label, "hub")}` : "",
                        d.status !== "active" ? d.status : "",
                      ].filter(Boolean);
                      return parts.length ? <span className="muted iot-type">{parts.join(" · ")}</span> : null;
                    })()}
                  </div>
                  <div className="iot-meta">
                    <span>
                      MAC <code>{d.mac_address}</code>
                    </span>
                    <span>Battery {d.battery_level != null ? `${d.battery_level}%` : "not reported"}</span>
                    <span>
                      {d.last_seen_at
                        ? `Last seen ${timeAgo(d.last_seen_at, clockNow)}`
                        : "Check the gateway is on and the device is charged"}
                    </span>
                    {motionText(d, clockNow) ? <span className="iot-motion">{motionText(d, clockNow)}</span> : null}
                    {d.notes ? <span>({d.notes})</span> : null}
                  </div>
                  </div>
                  {replacingId === d.id ? (
                    <div className="iot-replace">
                      <label style={{ display: "grid", gap: "0.2rem", flex: "1 1 14rem" }}>
                        <span className="muted" style={{ fontSize: "0.85rem" }}>
                          New Band ID (printed on the back of the band)
                        </span>
                        <input
                          value={draft}
                          onChange={(e) =>
                            setEditMacById((prev) => ({ ...prev, [d.id]: e.target.value }))
                          }
                          style={{ padding: "0.35rem", minWidth: "12rem" }}
                        />
                      </label>
                      <button
                        type="button"
                        disabled={busyRow || !dirty || !draft.trim()}
                        title={!dirty ? "Type the new Band ID first" : undefined}
                        onClick={() => onSaveRowMac(d)}
                      >
                        {busyRow ? "Saving…" : "Save new band"}
                      </button>
                      <button
                        type="button"
                        className="secondary"
                        disabled={busyRow}
                        onClick={() => {
                          setReplacingId(null);
                          setEditMacById((prev) => ({ ...prev, [d.id]: d.mac_address }));
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <div className="iot-row-actions">
                      <label className="iot-assign">
                        <span className="muted">Client</span>
                        <select
                          aria-label="Client"
                          value={d.elder_id ?? ""}
                          disabled={busyRow}
                          onChange={(e) =>
                            onAssign(`/api/v1/iot/devices/${d.id}/assign`, d.mac_address, e.target.value)
                          }
                        >
                          <option value="">Not assigned</option>
                          {clientOptions}
                        </select>
                      </label>
                      <button type="button" className="secondary" onClick={() => onTest("devices", d.id)}>
                        Test
                      </button>
                      <details className="iot-more">
                        <summary title="More actions">More</summary>
                        <div>
                          <button type="button" className="secondary" disabled={busyRow || !d.elder_id} onClick={() => onSendTest(d)}>
                            {busyRow ? "Sending…" : "Send test alert"}
                          </button>
                          <button type="button" className="secondary" disabled={busyRow} onClick={() => setReplacingId(d.id)}>
                            Replace
                          </button>
                          <button
                            type="button"
                            className="secondary is-danger"
                            disabled={busyRow}
                            onClick={() => onDeleteDevice(d)}
                          >
                            Remove
                          </button>
                        </div>
                      </details>
                    </div>
                  )}
                  {heard[`devices-${d.id}`] ? (
                    <p className="muted iot-heard" role="status">{heard[`devices-${d.id}`]}</p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="card iot-card">
        <h2 className="iot-card-title">
          Gateways <span className="iot-count">{hubs.length}</span>
        </h2>
        {hubs.length === 0 ? (
          <p className="muted" style={{ margin: 0 }}>
            None yet. Use <strong>Add device</strong> and choose Gateway.
          </p>
        ) : (
          <ul className="iot-list">
            {hubs.map((h) => {
              const seen = h.last_seen_at ? parseIso(h.last_seen_at) : null;
              const online = seen != null && clockNow.getTime() - seen <= (broker.offline_seconds || 180) * 1000;
              const tone = seen == null ? "new" : online ? "ok" : "bad";
              const name = plainDeviceName(h.label, "hub");
              return (
                <li key={h.id} className="iot-row">
                  <div className="iot-row-info">
                    <div className="iot-row-head">
                      <strong>{name}</strong>
                      <span
                        className="iot-pill"
                        style={{ background: PILL[tone].bg, color: PILL[tone].fg }}
                      >
                        {seen == null ? "Not heard yet" : online ? "Online" : "Offline"}
                      </span>
                      <span className="muted iot-type">Gateway</span>
                    </div>
                    <div className="iot-meta">
                      {h.mac_address ? (
                        <span>
                          MAC <code>{h.mac_address}</code>
                        </span>
                      ) : null}
                      <span>{h.elder_id ? elderDisplayName(elders, h.elder_id) : "Not placed in a home"}</span>
                      {seen != null ? <span>Last heard {timeAgo(h.last_seen_at, clockNow)}</span> : null}
                    </div>
                  </div>
                  <div className="iot-row-actions">
                    <label className="iot-assign">
                      <span className="muted">Home</span>
                      <select
                        aria-label="Home"
                        value={h.elder_id ?? ""}
                        onChange={(e) => onAssign(`/api/v1/iot/hubs/${h.id}/assign`, name, e.target.value)}
                      >
                        <option value="">Not placed</option>
                        {clientOptions}
                      </select>
                    </label>
                    <button type="button" className="secondary" onClick={() => onTest("hubs", h.id)}>
                      Test
                    </button>
                    <details className="iot-more">
                      <summary title="More actions">More</summary>
                      <div>
                        <button
                          type="button"
                          className="secondary is-danger"
                          disabled={hubBusyId === h.id}
                          onClick={() => onDeleteHub(h)}
                        >
                          {hubBusyId === h.id ? "Removing…" : "Remove"}
                        </button>
                      </div>
                    </details>
                  </div>
                  {h.bands_heard != null ? (
                    <p className="muted iot-heard">
                      Hearing {h.bands_heard} band{h.bands_heard === 1 ? "" : "s"} nearby
                    </p>
                  ) : null}
                  {heard[`hubs-${h.id}`] ? (
                    <p className="muted iot-heard" role="status">{heard[`hubs-${h.id}`]}</p>
                  ) : null}
                  <details className="iot-hub-tech" open={setupOpenId === h.id}>
                    <summary>Set up this gateway</summary>
                    {h.http_url ? (
                      <div className="iot-setup">
                        <span className="muted">Upload link (keep it private):</span>
                        <code className="iot-url">{h.http_url}</code>
                        <div className="iot-row-actions">
                          <button type="button" className="secondary" onClick={() => onCopy(h.http_url || "")}>
                            Copy link
                          </button>
                          <button type="button" className="secondary" disabled={hubBusyId === h.id} onClick={() => onNewLink(h)}>
                            New link
                          </button>
                        </div>
                        <ol className="iot-steps">
                          <li>Power the gateway and open its setup page (Minew G1: join its Wi-Fi, then open 192.168.99.1).</li>
                          <li>Connect it to the home Wi-Fi or network cable.</li>
                          <li>Under Service, choose HTTP. Paste the link as the URL.</li>
                          <li>Data format JSON. Upload every 1–5 seconds.</li>
                          <li>Save and restart. Press Test here — it should say “just now”.</li>
                        </ol>
                      </div>
                    ) : (
                      <div className="iot-setup">
                        <span className="muted">This gateway has no upload link yet.</span>
                        <div>
                          <button type="button" className="secondary" disabled={hubBusyId === h.id} onClick={() => onNewLink(h)}>
                            Make upload link
                          </button>
                        </div>
                      </div>
                    )}
                    <span className="muted" style={{ fontSize: "0.85rem" }}>
                      Using MQTT instead? User {h.mqtt_username}
                      {h.mqtt_password ? (
                        <>
                          {" "}
                          · password <code>{h.mqtt_password}</code>
                        </>
                      ) : null}{" "}
                      · topic {h.mqtt_topic}
                    </span>
                  </details>
                </li>
              );
            })}
          </ul>
        )}
      </section>
      <BandAlertSettings />
      {drawer === "give" ? (
        <div className="cm-drawer-wrap" role="presentation" onClick={() => !busy && setDrawer(null)}>
          <form
            onSubmit={onAddDevice}
            className="cm-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Add device"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="cm-drawer-head">
              <h2>Add device</h2>
              <button type="button" className="secondary" onClick={() => setDrawer(null)} disabled={busy}>
                Close
              </button>
            </div>
            <label>
              Type
              <select value={addKind} onChange={(e) => setAddKind(e.target.value as AddKind)}>
                <option value="watch">SOS watch / band</option>
                <option value="gateway">Gateway</option>
                <option value="sensor">Sensor</option>
              </select>
            </label>
            <label>
              MAC
              <input
                required
                value={mac}
                onChange={(e) => setMac(e.target.value)}
                placeholder="AC:23:3F:12:34:56"
                autoComplete="off"
                spellCheck={false}
              />
              <small className="muted" style={{ fontWeight: 400 }}>
                {mac.trim() && !normalizeMac(mac)
                  ? "Needs 12 letters or numbers."
                  : "Printed on the device or its box."}
              </small>
            </label>
            <label>
              Name
              <input
                value={bandLabel}
                onChange={(e) => setBandLabel(e.target.value)}
                placeholder={addKind === "gateway" ? "e.g. Hall gateway" : addKind === "sensor" ? "e.g. Door sensor" : "e.g. Amma's watch"}
              />
            </label>
            <label>
              {addKind === "gateway" ? "Home (client)" : "Client"}
              <select value={elderId} onChange={(e) => setElderId(e.target.value)}>
                <option value="">Not yet</option>
                {clientOptions}
              </select>
              <small className="muted" style={{ fontWeight: 400 }}>You can give it to a client later.</small>
            </label>
            {error ? <p className="cm-error" role="alert">{error}</p> : null}
            <div className="cm-drawer-actions" style={{ alignItems: "center", flexWrap: "wrap" }}>
              {registerHint ? <small className="muted">{registerHint}</small> : null}
              <button type="button" className="secondary" onClick={() => setDrawer(null)} disabled={busy}>
                Cancel
              </button>
              <button type="submit" disabled={busy || !!registerHint || !normalizeMac(mac)}>
                {busy ? "Saving…" : "Add device"}
              </button>
            </div>
          </form>
        </div>
      ) : null}

      {drawer === "swap" ? (
        <div className="cm-drawer-wrap" role="presentation" onClick={() => !updateBusy && setDrawer(null)}>
          <form
            onSubmit={onUpdateMac}
            className="cm-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Swap a band"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="cm-drawer-head">
              <h2>Swap a band</h2>
              <button type="button" className="secondary" onClick={() => setDrawer(null)} disabled={updateBusy}>
                Close
              </button>
            </div>
            <p className="muted" style={{ margin: 0 }}>
              Use this when a client gets a new band. If they had none yet, this links one to them.
            </p>
            <label>
              Client
              <select required value={updateElderId} onChange={(e) => setUpdateElderId(e.target.value)}>
                <option value="">Choose…</option>
                {clientOptions}
              </select>
            </label>
            <label>
              New Band ID
              <input required value={updateMac} onChange={(e) => setUpdateMac(e.target.value)} placeholder="AA:BB:CC:DD:EE:FF" />
              <small className="muted" style={{ fontWeight: 400 }}>Printed on the back of the band.</small>
            </label>
            {error ? <p className="cm-error" role="alert">{error}</p> : null}
            <div className="cm-drawer-actions" style={{ alignItems: "center", flexWrap: "wrap" }}>
              {swapHint ? <small className="muted">{swapHint}</small> : null}
              <button type="button" className="secondary" onClick={() => setDrawer(null)} disabled={updateBusy}>
                Cancel
              </button>
              <button type="submit" disabled={updateBusy || !!swapHint}>
                {updateBusy ? "Saving…" : "Save new band"}
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}
