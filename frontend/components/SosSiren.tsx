"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, getStoredAuth } from "@/lib/api";
import {
  SIREN_POLL_MS,
  SIREN_GAP_SECONDS,
  SIREN_PLAYS,
  WAIL_SECONDS,
  dueKeys,
  pressedHereAt,
  quietHere,
  pressedAtLabel,
  sirenKey,
  telHref,
  wailSchedule,
  type SirenItem,
} from "@/lib/sos-siren";
import { nativeStopAlarm } from "@/lib/native-app";
import { useNativePush } from "./useNativePush";
import "./sos-siren.css";

/**
 * The siren the owner chose (27 Oct): a real civil-defence wailing siren
 * recording (public domain, Wikimedia Commons), 6 s, in public/sounds. Decoded
 * once into the already-unlocked AudioContext. If the file can't load, the
 * generated hooter below plays instead, so an SOS is never silent.
 */
const SIREN_URL = "/sounds/kushalaya-sos-siren.mp3";
let sirenBuffer: Promise<AudioBuffer | null> | null = null;

function loadSiren(ctx: AudioContext): Promise<AudioBuffer | null> {
  sirenBuffer ??= fetch(SIREN_URL)
    .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject(new Error(String(r.status)))))
    .then((b) => ctx.decodeAudioData(b))
    .catch(() => {
      sirenBuffer = null; // try the file again next time
      return null;
    });
  return sirenBuffer;
}

/** What is sounding now, so Acknowledge can silence it at once. */
let sounding: { stop: () => void }[] = [];

export function stopSiren() {
  for (const s of sounding) {
    try {
      s.stop();
    } catch {
      // already finished
    }
  }
  sounding = [];
}

/** SIREN_PLAYS plays with SIREN_GAP_SECONDS of quiet between them. */
function wail(ctx: AudioContext) {
  void loadSiren(ctx).then((buf) => {
    if (!buf) {
      // Backup: the generated hooter, the same number of times.
      for (let i = 0; i < SIREN_PLAYS; i++) {
        const t = window.setTimeout(() => synthWail(ctx), i * (WAIL_SECONDS + SIREN_GAP_SECONDS) * 1000);
        sounding.push({ stop: () => window.clearTimeout(t) });
      }
      return;
    }
    const t0 = ctx.currentTime + 0.05;
    for (let i = 0; i < SIREN_PLAYS; i++) {
      const src = ctx.createBufferSource();
      src.buffer = buf;
      src.connect(ctx.destination);
      src.start(t0 + i * (buf.duration + SIREN_GAP_SECONDS));
      sounding.push(src);
    }
  });
}

/**
 * About 4 s of ambulance hooter (wail then yelp), made with the Web Audio API (no
 * audio file): two slightly detuned sawtooth horns gliding together, shaped by a
 * band-pass like a siren horn and a limiter so it is loud but never distorts.
 */
function synthWail(ctx: AudioContext) {
  const t0 = ctx.currentTime + 0.05;
  const end = t0 + WAIL_SECONDS;
  const horn = ctx.createBiquadFilter();
  horn.type = "bandpass";
  horn.frequency.value = 1100;
  horn.Q.value = 0.8;
  const limiter = ctx.createDynamicsCompressor();
  limiter.threshold.value = -10;
  limiter.ratio.value = 12;
  const gain = ctx.createGain();
  gain.gain.setValueAtTime(0.0001, t0);
  gain.gain.exponentialRampToValueAtTime(0.6, t0 + 0.04);
  gain.gain.setValueAtTime(0.6, end - 0.12);
  gain.gain.exponentialRampToValueAtTime(0.0001, end);
  horn.connect(gain).connect(limiter).connect(ctx.destination);
  for (const detune of [0, 12]) {
    const osc = ctx.createOscillator();
    osc.type = "sawtooth";
    osc.detune.value = detune;
    const points = wailSchedule();
    osc.frequency.setValueAtTime(points[0].f, t0);
    for (const { t, f } of points.slice(1)) osc.frequency.linearRampToValueAtTime(f, t0 + t);
    osc.connect(horn);
    osc.start(t0);
    osc.stop(end + 0.05);
  }
}

/**
 * SOS siren for the people linked to a client (ops, caregiver and family apps).
 * Polls the server for this person's unacknowledged SOS alerts, sounds the
 * siren once per new alert and again every 2 minutes until they acknowledge,
 * and always shows the notice, even while the browser still blocks sound.
 */
/** `cards={false}`: keep the alarm sound but show no card (a page that lists the SOS itself). */
export function SosSiren({ cards = true }: { cards?: boolean } = {}) {
  useNativePush(); // Android app: register this phone for the SOS alarm
  const [items, setItems] = useState<SirenItem[]>([]);
  const [locked, setLocked] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState("");
  const ctxRef = useRef<AudioContext | null>(null);
  const played = useRef<Record<string, number>>({});
  const pending = useRef(false);

  const audio = useCallback((): AudioContext | null => {
    if (ctxRef.current) return ctxRef.current;
    try {
      const Ctor =
        window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      ctxRef.current = Ctor ? new Ctor() : null;
    } catch {
      ctxRef.current = null;
    }
    return ctxRef.current;
  }, []);

  const sound = useCallback(() => {
    const ctx = audio();
    if (!ctx || ctx.state !== "running") {
      pending.current = true;
      setLocked(true);
      return;
    }
    pending.current = false;
    setLocked(false);
    wail(ctx);
  }, [audio]);

  const unlock = useCallback(async () => {
    const ctx = audio();
    if (!ctx) return;
    if (ctx.state === "running") return;
    // Inside the tap itself: resume, and play one silent sample (iPhones only unlock
    // Web Audio when something actually plays during a gesture).
    const resumed = ctx.resume();
    try {
      const blip = ctx.createBufferSource();
      blip.buffer = ctx.createBuffer(1, 1, 22050);
      blip.connect(ctx.destination);
      blip.start(0);
    } catch {
      /* ignore */
    }
    try {
      await resumed;
    } catch {
      /* still blocked */
    }
    void loadSiren(ctx); // fetch and decode now, so the first alert plays at once
    const running = (ctx.state as AudioContextState) === "running"; // re-read after the await
    setLocked(!running);
    if (running && pending.current) {
      pending.current = false;
      wail(ctx);
    }
  }, [audio]);

  // Browsers block sound until the person interacts: unlock on the first click / tap / key.
  useEffect(() => {
    const onGesture = () => void unlock();
    const opts = { capture: true, passive: true } as const;
    // On phones a finger going DOWN does not count as permission to play sound —
    // only lifting it (touchend / pointerup / click) does — so listen to all of them.
    const events = ["pointerdown", "pointerup", "touchend", "click", "keydown"] as const;
    for (const e of events) window.addEventListener(e, onGesture, opts);
    return () => {
      for (const e of events) window.removeEventListener(e, onGesture, opts);
    };
  }, [unlock]);

  const load = useCallback(async () => {
    if (!getStoredAuth()) return;
    try {
      const rows = await api<SirenItem[]>("/api/v1/sos-siren/active");
      setItems(rows);
      const now = Date.now();
      // Once someone confirmed it, the card stays (to offer "Notify family") but stays quiet.
      const due = dueKeys(rows.filter((r) => !r.notify_family), played.current, now);
      if (due.length) {
        for (const k of due) played.current[k] = now;
        // The device that pressed SOS stays quiet for its own alert (the notice still
        // shows); every other device on this account rings (owner, 27 Oct).
        const here = pressedHereAt();
        const loud = rows.some((r) => due.includes(sirenKey(r)) && !quietHere(r, here, now));
        if (loud) sound();
      }
    } catch {
      /* keep the last list; try again next tick */
    }
  }, [sound]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), SIREN_POLL_MS);
    return () => window.clearInterval(timer);
  }, [load]);

  async function act(item: SirenItem, path: string, body?: unknown) {
    setBusy(item.id);
    setError("");
    try {
      await api(path, { method: "POST", ...(body ? { body: JSON.stringify(body) } : {}) });
      if (path.endsWith("/confirm")) {
        stopSiren(); // confirmed: quiet now, the card stays to offer "Notify family"
        nativeStopAlarm();
      }
      if (path.endsWith("/acknowledge") || path.endsWith("/false-alarm") || path.endsWith("/notify-family")) {
        stopSiren(); // they have seen it: silence the remaining plays now
        nativeStopAlarm(); // and the phone's alarm, in the Android app
        setItems((list) => list.filter((x) => x.id !== item.id));
        delete played.current[sirenKey(item)];
      }
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save. Try again.");
    } finally {
      setBusy(null);
    }
  }

  if (items.length === 0 || !cards) return null;

  return (
    <div className="ks-siren" role="alertdialog" aria-modal="false" aria-labelledby="ks-siren-title">
      {items.slice(0, 3).map((item, i) => {
        const tel = telHref(item.call.phone);
        const when = pressedAtLabel(item.pressed_at);
        return (
          <section key={item.id} className={`ks-siren-card${item.verify ? " is-verify" : ""}`}>
            <p className="ks-siren-kicker">
              <span className="ks-siren-dot" aria-hidden="true" />
              {item.title}
              {item.escalated ? <span className="ks-siren-badge">Escalated</span> : null}
            </p>
            <h2 id={i === 0 ? "ks-siren-title" : undefined} className="ks-siren-name" aria-live="assertive">
              {item.elder_name}
            </h2>
            <p className="ks-siren-meta">
              Pressed by {item.pressed_by}
              {when ? ` · ${when}` : ""}
            </p>
            {item.verify ? (
              <p className="ks-siren-meta">
                {item.source === "watch" ? "From the watch. " : ""}Check it first. The family has not been told.
              </p>
            ) : null}
            {item.notify_family ? (
              <p className="ks-siren-meta">
                {item.confirmed_by ? `Confirmed by ${item.confirmed_by}. ` : "Confirmed. "}The family has not been told yet.
              </p>
            ) : null}
            {item.audience === "family" && item.pressed_by_me && !item.family_told ? (
              <p className="ks-siren-meta">Your care team has been alerted.</p>
            ) : null}
            {item.acknowledged_by.length ? (
              <p className="ks-siren-ack">Acknowledged by {item.acknowledged_by.join(", ")}</p>
            ) : null}
            <div className="ks-siren-actions">
              {tel ? (
                <a className="ks-siren-btn ks-siren-call" href={tel}>
                  {item.call.label}
                </a>
              ) : null}
              {item.verify ? (
                <>
                  <button
                    type="button"
                    className="ks-siren-btn ks-siren-confirm"
                    disabled={busy === item.id}
                    onClick={() => void act(item, `/api/v1/sos-siren/incidents/${item.incident_id}/confirm`)}
                  >
                    Confirm it&apos;s real
                  </button>
                  <button
                    type="button"
                    className="ks-siren-btn ks-siren-quiet"
                    disabled={busy === item.id}
                    onClick={() => void act(item, `/api/v1/sos-siren/incidents/${item.incident_id}/false-alarm`, {})}
                  >
                    False alarm
                  </button>
                </>
              ) : null}
              {item.notify_family ? (
                <button
                  type="button"
                  className="ks-siren-btn ks-siren-confirm"
                  disabled={busy === item.id}
                  onClick={() => void act(item, `/api/v1/sos-siren/incidents/${item.incident_id}/notify-family`, {})}
                >
                  Notify family
                </button>
              ) : null}
              <button
                type="button"
                className="ks-siren-btn ks-siren-ackbtn"
                disabled={busy === item.id}
                onClick={() => void act(item, `/api/v1/sos-siren/${item.id}/acknowledge`)}
              >
                {item.notify_family ? "Not now" : "Acknowledge"}
              </button>
            </div>
          </section>
        );
      })}
      {items.length > 3 ? <p className="ks-siren-more">+{items.length - 3} more SOS</p> : null}
      {error ? (
        <p className="ks-siren-error" role="alert">
          {error}
        </p>
      ) : null}
      {locked ? (
        <button type="button" className="ks-siren-sound" onClick={() => void unlock()}>
          Turn on alert sound
        </button>
      ) : null}
    </div>
  );
}
