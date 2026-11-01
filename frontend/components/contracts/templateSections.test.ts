import { describe, expect, it } from "vitest";
import { fromFriendly, fromSections, toFriendly, toSections } from "./templateSections";

const known = new Set(["vendor_company", "date", "vendor_fee"]);

describe("template sections", () => {
  it("round-trips headings and paragraphs", () => {
    const body = "# Parties\nMade on {date}.\n\nSecond paragraph.\n\n# Fees\n{vendor_fee}.";
    const sections = toSections(body);
    expect(sections).toEqual([
      { heading: "Parties", text: "Made on {date}.\n\nSecond paragraph." },
      { heading: "Fees", text: "{vendor_fee}." },
    ]);
    expect(fromSections(sections)).toBe("# Parties\n\nMade on {date}.\n\nSecond paragraph.\n\n# Fees\n\n{vendor_fee}.");
  });

  it("keeps text before the first heading and drops empty sections", () => {
    expect(toSections("Intro\n\n# A\nx")[0]).toEqual({ heading: "", text: "Intro" });
    expect(fromSections([{ heading: "", text: "" }, { heading: "B", text: "" }])).toBe("# B");
  });

  it("shows details in plain words and converts them back", () => {
    const friendly = toFriendly("By {vendor_company} on {date}, {unknown}.", known);
    expect(friendly).toBe("By [Vendor company] on [Today's date], {unknown}.");
    expect(fromFriendly(friendly, known)).toBe("By {vendor_company} on {date}, {unknown}.");
    expect(fromFriendly("[vendor COMPANY] and [Not a detail]", known)).toBe("{vendor_company} and [Not a detail]");
  });
});
