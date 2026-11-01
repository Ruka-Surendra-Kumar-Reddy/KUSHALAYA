import { describe, expect, it } from "vitest";
import { directionsTarget, mapAppLinks } from "./live-location";

describe("directionsTarget", () => {
  const home = { lat: 17.41, lng: 78.44 };
  it("prefers the saved home pin over the address", () => {
    expect(directionsTarget({ home, address: "Plot 42", location: "Plot 42" })).toEqual(home);
  });
  it("uses the visit's own location when it differs from home", () => {
    expect(directionsTarget({ home, address: "Plot 42", location: "Care Hospital" })).toBe("Care Hospital");
  });
  it("falls back to the address, and to nothing", () => {
    expect(directionsTarget({ home: null, address: " Plot 42 " })).toBe("Plot 42");
    expect(directionsTarget({})).toBeNull();
  });
  it("builds Google / Apple / Waze links for a pin", () => {
    const links = mapAppLinks(home);
    expect(links.map((l) => l.label)).toEqual(["Google Maps", "Apple Maps", "Waze"]);
    expect(links[0].href).toContain("destination=17.41%2C78.44");
  });
});
