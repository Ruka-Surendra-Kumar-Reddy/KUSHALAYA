import { describe, expect, it } from "vitest";
import { areaContradictsPin, landingPageLabel, leadSourceLabel, matchLeadToClient, splitLeadNotes } from "./lead-labels";

describe("leadSourceLabel", () => {
  it("turns codes into words", () => {
    expect(leadSourceLabel("website")).toBe("Website");
    expect(leadSourceLabel("home_safety_assessment")).toBe("Home safety assessment");
    expect(leadSourceLabel("website:care-check")).toBe("Website · KushCare Discovery");
    expect(leadSourceLabel("qr:care-check")).toBe("QR / standee");
    expect(leadSourceLabel("google_ads")).toBe("Google ads");
    expect(leadSourceLabel(null)).toBe("Not recorded");
  });
});

describe("landingPageLabel", () => {
  it("names the page instead of showing the path", () => {
    expect(landingPageLabel("/")).toBe("Home page");
    expect(landingPageLabel("/blog/fall-proofing?utm=x")).toBe("Blog › Fall proofing");
    expect(landingPageLabel("https://www.example.com/")).toBe("Home page");
    expect(landingPageLabel("")).toBe("Not recorded");
  });
});


describe("lead notes", () => {
  it("pulls Area and For into fields and keeps the free text", () => {
    const r = splitLeadNotes("Services: Care check\nArea: Hyderabad\nFor: Mother, 78\n\nPlease call after 6");
    expect(r.fields).toEqual([
      ["Services", "Care check"],
      ["Area", "Hyderabad"],
      ["For", "Mother, 78"],
    ]);
    expect(r.rest).toBe("Please call after 6");
  });
  it("flags an area that cannot match the PIN", () => {
    expect(areaContradictsPin("Hyderabad", "831009")).toBe(true);
    expect(areaContradictsPin("Hyderabad", "500034")).toBe(false);
    expect(areaContradictsPin("Jamshedpur", "831009")).toBe(false);
    expect(areaContradictsPin("Hyderabad", "")).toBe(false);
  });
});

describe("matchLeadToClient", () => {
  const clients = [
    { id: 7, first_name: "surendra", last_name: "ruka", phone: "6304480702" },
    { id: 8, first_name: "Lakshmi", last_name: "Reddy", phone: "+91-9000000001", family_email: "Son@x.in" },
  ];
  it("matches by phone whatever the format", () => {
    expect(matchLeadToClient({ phone: "+916304480702" }, clients)?.id).toBe(7);
  });
  it("matches by family email", () => {
    expect(matchLeadToClient({ email: "son@x.in" }, clients)?.id).toBe(8);
  });
  it("returns null for a new person", () => {
    expect(matchLeadToClient({ phone: "+91 99999 11111", email: "" }, clients)).toBeNull();
  });
});
