/**
 * SOS siren (C1): pure helpers for components/SosSiren.tsx.
 * The server decides who hears an SOS (backend/app/livewell/sos_siren.py).
 */

export const SIREN_POLL_MS = 12_000;
/** Play again every 2 minutes while the person has not acknowledged it. */
export const SIREN_REPEAT_MS = 2 * 60_000;
export const WAIL_SECONDS = 4.3;
/** Each alert sounds the siren this many times, with this many seconds of quiet between (owner, 27 Oct). */
export const SIREN_PLAYS = 2;
export const SIREN_GAP_SECONDS = 10;

export type SirenItem = {
  id: number;
  incident_id: number;
  elder_id: number;
  elder_name: string;
  kind: string;
  title: string;
  audience: "staff" | "family";
  pressed_by: string;
  /** This account pressed it (on this device or another one). */
  pressed_by_me?: boolean;
  source: string;
  pressed_at: string | null;
  /** Staff: not checked yet; the card offers "It's real" / "False alarm". */
  verify: boolean;
  /** Staff: confirmed, the family not told yet; the card offers "Notify family". */
  notify_family?: boolean;
  /** The family has been alerted (false while the care team checks it first). */
  family_told?: boolean;
  escalated: boolean;
  confirmed_by: string | null;
  acknowledged_by: string[];
  call: { label: string; phone: string };
};

const PRESSED_HERE_KEY = "ks-sos-pressed-here";
/** How long after pressing SOS on this device its own alert stays quiet here. */
export const PRESSED_HERE_MS = 10 * 60 * 1000;

/** Call just before sending an SOS from this device: its own alert won't sound here. */
export function markPressedHere(now: number = Date.now()): void {
  try {
    window.localStorage.setItem(PRESSED_HERE_KEY, String(now));
  } catch {
    /* storage blocked: this device will ring for its own SOS too */
  }
}

/** Pure: this account pressed it, and this device pressed an SOS just now. */
export function quietHere(item: Pick<SirenItem, "pressed_by_me">, pressedHereAt: number | null, now: number): boolean {
  return Boolean(item.pressed_by_me) && pressedHereAt !== null && now - pressedHereAt >= 0 && now - pressedHereAt < PRESSED_HERE_MS;
}

export function pressedHereAt(): number | null {
  try {
    const v = Number(window.localStorage.getItem(PRESSED_HERE_KEY));
    return Number.isFinite(v) && v > 0 ? v : null;
  } catch {
    return null;
  }
}

/** An escalation is a new alert: it sounds again even if the first one just played.
 *  Confirming it does not (the team already has it). */
export function sirenKey(item: Pick<SirenItem, "id" | "escalated">): string {
  return `${item.id}${item.escalated ? ":esc" : ""}`;
}

/** Keys that should sound now: never played, or last played at least `repeatMs` ago. */
export function dueKeys(
  items: Pick<SirenItem, "id" | "escalated">[],
  lastPlayed: Record<string, number>,
  now: number,
  repeatMs: number = SIREN_REPEAT_MS,
): string[] {
  return items
    .map(sirenKey)
    .filter((k) => lastPlayed[k] === undefined || now - lastPlayed[k] >= repeatMs);
}

/**
 * Ambulance hooter (owner, 26 Oct): two slow "wail" sweeps, then a fast "yelp".
 * Each point is a frequency the pitch glides to (linear ramp) by time t.
 */
export function wailSchedule(lo = 650, hi = 1400): { t: number; f: number }[] {
  const out: { t: number; f: number }[] = [{ t: 0, f: lo }];
  let t = 0;
  const sweep = (up: number, down: number, times: number) => {
    for (let i = 0; i < times; i++) {
      t += up;
      out.push({ t: +t.toFixed(3), f: hi });
      t += down;
      out.push({ t: +t.toFixed(3), f: lo });
    }
  };
  sweep(0.9, 0.5, 2); // wail: 2.8 s
  sweep(0.12, 0.13, 6); // yelp: 1.5 s
  return out;
}

/** "tel:" link: digits and a leading +, nothing else. Empty when there is no number. */
export function telHref(phone: string | null | undefined): string {
  const raw = (phone || "").trim();
  const digits = raw.replace(/[^\d+]/g, "").replace(/(?!^)\+/g, "");
  return digits.replace(/\D/g, "").length >= 6 ? `tel:${digits}` : "";
}

/** "10:42 am" in the viewer's time, or "" for a bad value. */
export function pressedAtLabel(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
}
