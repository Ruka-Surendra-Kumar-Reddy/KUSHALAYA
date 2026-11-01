import { describe, expect, it } from "vitest";
import { appForHost, nativeAlarm, printPage, registrationKey } from "./native-app";

const plugin = { getToken: async () => ({ token: "t" }), setSession: async () => {}, signOut: async () => {}, stop: async () => {} };

describe("native app helpers", () => {
  it("finds the KushAlarm plugin only inside the native app", () => {
    expect(nativeAlarm(undefined)).toBeNull();
    expect(nativeAlarm({})).toBeNull();
    expect(nativeAlarm({ Capacitor: { isNativePlatform: () => false, Plugins: { KushAlarm: plugin } } })).toBeNull();
    expect(nativeAlarm({ Capacitor: { isNativePlatform: () => true, Plugins: {} } })).toBeNull();
    expect(nativeAlarm({ Capacitor: { isNativePlatform: () => true, Plugins: { KushAlarm: plugin } } })).toBe(plugin);
  });

  it("tells the two apps apart by host", () => {
    expect(appForHost("family.kushalaya.com")).toBe("family");
    expect(appForHost("ops.kushalaya.com")).toBe("ops");
    expect(appForHost("localhost")).toBe("ops");
    expect(appForHost(undefined)).toBe("ops");
  });

  it("registers again for a new person, token or session", () => {
    const a = registrationKey("A@x.com", "tok", "session-token-1234567890");
    expect(registrationKey("a@x.com", "tok", "session-token-1234567890")).toBe(a);
    expect(registrationKey("b@x.com", "tok", "session-token-1234567890")).not.toBe(a);
    expect(registrationKey("a@x.com", "tok2", "session-token-1234567890")).not.toBe(a);
    expect(registrationKey("a@x.com", "tok", "session-token-0000000000")).not.toBe(a);
  });
});

describe("printPage", () => {
  const base = { getToken: async () => ({ token: "" }), setSession: async () => undefined, signOut: async () => undefined, stop: async () => undefined };
  const app = (plugin: object) => ({ Capacitor: { isNativePlatform: () => true, Plugins: { KushAlarm: plugin } } });

  it("uses the app's print screen inside the Android app", async () => {
    const calls: string[] = [];
    let browser = 0;
    await printPage("Report", { ...app({ ...base, print: async (o: { title: string }) => void calls.push(o.title) }), print: () => browser++ });
    expect(calls).toEqual(["Report"]);
    expect(browser).toBe(0);
  });

  it("falls back to the browser print in a browser or an older app", async () => {
    let browser = 0;
    await printPage("Report", { print: () => browser++ });
    await printPage("Report", { ...app(base), print: () => browser++ });
    expect(browser).toBe(2);
  });
});
