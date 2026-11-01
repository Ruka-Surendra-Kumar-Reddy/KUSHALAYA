import { describe, expect, it } from "vitest";

import { formatCoordinates } from "./geocoding";

describe("formatCoordinates", () => {
  it.each([
    [17.385044, 78.486671, "17.385044, 78.486671"],
    ["17.4", "78.5", "17.400000, 78.500000"],
    [null, 78.4, ""],
    [17.4, null, ""],
    ["x", "y", ""],
    [undefined, undefined, ""],
  ] as const)("%j %j", (lat, lon, expected) => {
    expect(formatCoordinates(lat as never, lon as never)).toBe(expected);
  });
});
