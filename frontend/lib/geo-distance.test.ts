import { describe, expect, it } from "vitest";
import { distanceMeters, pinFarFromAddress } from "./geo-distance";

const banjaraHills = { lat: 17.4156, lng: 78.4347 };
const hitecCity = { lat: 17.4474, lng: 78.3762 };

describe("pinFarFromAddress", () => {
  it("measures roughly 7 km from Banjara Hills to HITEC City", () => {
    const d = distanceMeters(banjaraHills, hitecCity);
    expect(d).toBeGreaterThan(6000);
    expect(d).toBeLessThan(8000);
  });
  it("warns only beyond 1 km", () => {
    expect(pinFarFromAddress(hitecCity, banjaraHills)).not.toBeNull();
    expect(pinFarFromAddress({ lat: 17.4158, lng: 78.435 }, banjaraHills)).toBeNull();
  });
  it("stays silent without a geocoded address", () => {
    expect(pinFarFromAddress(hitecCity, null)).toBeNull();
  });
});
