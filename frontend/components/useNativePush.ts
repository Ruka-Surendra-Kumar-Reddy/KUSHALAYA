"use client";

import { useEffect } from "react";
import { api, getApiUrl, getStoredAuth } from "@/lib/api";
import { appForHost, nativeAlarm, nativeState, registrationKey } from "@/lib/native-app";

/**
 * Inside the KushAlaya Android app: register this phone for SOS alarm pushes and
 * hand the session to the native Acknowledge button. Does nothing in a browser.
 * Mounted by SosSiren, which every signed-in portal renders.
 */
export function useNativePush(): void {
  useEffect(() => {
    const plugin = nativeAlarm();
    const auth = getStoredAuth();
    if (!plugin || !auth?.access_token) return;
    let cancelled = false;
    void (async () => {
      try {
        const app = appForHost(window.location.hostname);
        await plugin.setSession({ apiBase: getApiUrl(), accessToken: auth.access_token, app });
        const { token } = await plugin.getToken();
        if (cancelled || !token) return;
        const key = registrationKey(auth.email, token, auth.access_token);
        if (key === nativeState.lastKey) return;
        await api("/api/v1/push/devices", { method: "POST", body: JSON.stringify({ token, app, platform: "android" }) });
        nativeState.lastKey = key;
      } catch {
        // The web siren still works; the next page load tries again.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);
}
