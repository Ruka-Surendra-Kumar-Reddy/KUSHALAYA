import { afterEach, describe, expect, it, vi } from "vitest";

import {
  distanceText,
  mapsUrl,
  optionalLocation,
  placeLines,
  pointText,
  requireLocation,
  toLocationPayload,
  withTimeout,
} from "./visit-location";

const far = { lat: 17.44, lng: 78.37, accuracy_m: 20, distance_m: 2300, away: true };

describe("visit location helpers", () => {
  it("builds the payload with rounded accuracy", () => {
    expect(toLocationPayload({ coords: { latitude: 17.4, longitude: 78.3, accuracy: 12.6 } })).toEqual({
      latitude: 17.4,
      longitude: 78.3,
      accuracy: 13,
    });
    expect(toLocationPayload({ coords: { latitude: 1, longitude: 2, accuracy: null } }).accuracy).toBeNull();
  });

  it("formats distance and the map link", () => {
    expect(distanceText(434)).toBe("430 m");
    expect(distanceText(2300)).toBe("2.3 km");
    expect(mapsUrl(17.44, 78.37)).toBe("https://www.google.com/maps/search/?api=1&query=17.440000,78.370000");
  });

  it("describes each point", () => {
    expect(pointText("Check-in", null, true)).toBe("Check-in: no location");
    expect(pointText("Check-in", { ...far, distance_m: null, away: null }, false)).toBe("Check-in location (no home pin)");
    expect(pointText("Check-out", far, true)).toBe("Check-out 2.3 km from home — away from home");
  });

  it("lists check-in, and check-out once completed", () => {
    const loc = { has_home_pin: true, checkin: far, checkout: null };
    expect(placeLines(loc, "scheduled")).toEqual([]);
    expect(placeLines(loc, "checked_in")).toHaveLength(1);
    const done = placeLines(loc, "completed");
    expect(done.map((p) => p.text)).toEqual(["Check-in 2.3 km from home — away from home", "Check-out: no location"]);
    expect(done[0].href).toContain("google.com/maps");
    expect(done[1]).toMatchObject({ href: null, away: false });
  });
});

describe("optionalLocation", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("returns null instead of blocking when there is no geolocation", async () => {
    vi.stubGlobal("navigator", {});
    await expect(optionalLocation(10)).resolves.toBeNull();
  });
});

describe("location never hangs", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("withTimeout rejects a promise that never settles", async () => {
    vi.useFakeTimers();
    const p = withTimeout(new Promise(() => undefined), 1000);
    const check = expect(p).rejects.toThrow(/in time/);
    await vi.advanceTimersByTimeAsync(1001);
    await check;
  });

  it("requireLocation gives up when the permission prompt is never answered", async () => {
    vi.useFakeTimers();
    // watchPosition / getCurrentPosition that never call back (prompt left open on an iPad).
    vi.stubGlobal("navigator", { geolocation: { watchPosition: () => 1, clearWatch: () => undefined, getCurrentPosition: () => undefined } });
    const p = requireLocation(100);
    const check = expect(p).rejects.toThrow();
    await vi.advanceTimersByTimeAsync(10_200);
    await check;
  });
});
