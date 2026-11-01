import { describe, expect, it } from "vitest";

import { authFromLoginResponse } from "./api";

describe("authFromLoginResponse", () => {
  it("maps elder_id onto customer_id when customer_id missing", () => {
    const auth = authFromLoginResponse({
      access_token: "a",
      refresh_token: "r",
      email: "family@test.example",
      role: "ELDER_PORTAL",
      tenant_id: 3,
      elder_id: 9,
      caregiver_id: null,
      session_id: "s1",
    });
    expect(auth.customer_id).toBe(9);
    expect(auth.session_id).toBe("s1");
    expect(auth.role).toBe("ELDER_PORTAL");
  });

  it("prefers customer_id over elder_id", () => {
    const auth = authFromLoginResponse({
      access_token: "a",
      refresh_token: "r",
      email: "x@y.z",
      role: "ELDER_PORTAL",
      tenant_id: 1,
      customer_id: 4,
      elder_id: 9,
    });
    expect(auth.customer_id).toBe(4);
  });
});
