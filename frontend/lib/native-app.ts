/**
 * The KushAlaya Android apps (mobile/) load this same website in a Capacitor
 * WebView and add a native "KushAlarm" plugin: the SOS alarm that rings even when
 * the app is closed, locked, silent or on do-not-disturb. These helpers find that
 * plugin; in a normal browser they all return null / do nothing.
 */

export type NativeApp = "ops" | "family";

export type KushAlarmPlugin = {
  /** The phone's FCM registration token ("" until Firebase is set up). */
  getToken(): Promise<{ token: string }>;
  /** Lets the lock-screen Acknowledge button call the API as this person. */
  setSession(opts: { apiBase: string; accessToken: string; app: NativeApp }): Promise<void>;
  /** Unregisters the phone with the server and forgets the session. */
  signOut(): Promise<void>;
  /** Silences a ringing alarm (the SOS was acknowledged on the page). */
  stop(): Promise<void>;
  /** Android print / Save as PDF for this page (app v1.3+; WebViews ignore window.print()). */
  print?(opts: { title: string }): Promise<void>;
};

type CapacitorWindow = {
  Capacitor?: {
    isNativePlatform?: () => boolean;
    getPlatform?: () => string;
    Plugins?: Record<string, unknown>;
  };
  location?: { hostname?: string };
};

export function nativeAlarm(win: unknown = typeof window === "undefined" ? undefined : window): KushAlarmPlugin | null {
  const cap = (win as CapacitorWindow | undefined)?.Capacitor;
  if (!cap || typeof cap.isNativePlatform !== "function" || !cap.isNativePlatform()) return null;
  const plugin = cap.Plugins?.KushAlarm as KushAlarmPlugin | undefined;
  return plugin && typeof plugin.getToken === "function" ? plugin : null;
}

/**
 * Print / Save as PDF. Inside the Android app window.print() does nothing, so the
 * app's own print screen is used; an older app without it falls back to window.print().
 */
export async function printPage(title: string, win: unknown = typeof window === "undefined" ? undefined : window): Promise<void> {
  const plugin = nativeAlarm(win);
  if (plugin && typeof plugin.print === "function") {
    try {
      await plugin.print({ title });
      return;
    } catch {
      /* fall back to the browser print below */
    }
  }
  (win as { print?: () => void } | undefined)?.print?.();
}

/** Which of the two apps this page is running in, by host. */
export function appForHost(hostname: string | undefined | null): NativeApp {
  return (hostname || "").toLowerCase().startsWith("family.") ? "family" : "ops";
}

/** Register once per (person, token, session); a new sign-in or token registers again. */
export function registrationKey(email: string, token: string, accessToken: string): string {
  return `${email.toLowerCase()}|${token}|${accessToken.slice(-16)}`;
}

/** The last registration sent this page load (see useNativePush). */
export const nativeState = { lastKey: "" };

/** Called by clearAuth(): the phone must stop ringing for whoever signed out. */
export function nativeSignOut(): void {
  nativeState.lastKey = "";
  const plugin = nativeAlarm();
  if (plugin) void plugin.signOut().catch(() => undefined);
}

export function nativeStopAlarm(): void {
  const plugin = nativeAlarm();
  if (plugin) void plugin.stop().catch(() => undefined);
}
