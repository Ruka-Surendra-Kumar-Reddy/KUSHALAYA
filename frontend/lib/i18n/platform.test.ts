import { describe, expect, it } from "vitest";

import { PLATFORM_MESSAGES, translate } from "@workforceos/contracts/i18n";

import { LOCALE_STORAGE_KEY, MESSAGE_CATALOGS } from "./index";

describe("MESSAGE_CATALOGS", () => {
  it("merges platform nav strings", () => {
    expect(MESSAGE_CATALOGS.en.nav.items.dashboard).toBe("Dashboard");
    expect(MESSAGE_CATALOGS.en.nav.items.liveWellCustomers).toBe("Customers");
    expect(MESSAGE_CATALOGS.en.nav.items.liveWellAssessments).toBe("Assessments");
    expect(MESSAGE_CATALOGS.en.nav.items.liveWellVisits).toBe("Visits");
    expect(MESSAGE_CATALOGS.en.dashboard.liveWellOps).toBe("KushAlaya operations");
  });

  it("keeps vertical-specific page strings", () => {
    expect(MESSAGE_CATALOGS.en.pages.elders?.title).toBe("Elders");
  });

  it("uses eco locale storage key", () => {
    expect(LOCALE_STORAGE_KEY).toBe("sho_admin_locale");
  });
});

describe("platform catalog parity", () => {
  it("matches core platform messages for nav", () => {
    expect(translate("en", "nav.items.settings", MESSAGE_CATALOGS)).toBe(
      PLATFORM_MESSAGES.en.nav.items.settings,
    );
  });
});
