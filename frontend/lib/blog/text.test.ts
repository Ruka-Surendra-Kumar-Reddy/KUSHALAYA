import { describe, expect, it } from "vitest";

import { blogDate, imagesMissingAlt, plainWords, readingLabel, readingMinutes, safeHref, slugify, tagLabel } from "./text";

describe("slugify", () => {
  it("makes clean addresses", () => {
    expect(slugify("Caring for Parents — Hyderabad!")).toBe("caring-for-parents-hyderabad");
    expect(slugify("  Café   déjà vu  ")).toBe("cafe-deja-vu");
    expect(slugify("---")).toBe("post");
    expect(slugify("a".repeat(150)).length).toBe(100);
  });
});

describe("reading time", () => {
  it("counts words, not Markdown", () => {
    expect(plainWords("## Hello **world** ![alt text](/x.webp) [link text](/y)")).toEqual(["Hello", "world", "link", "text"]);
    expect(readingMinutes("")).toBe(1);
    expect(readingMinutes("word ".repeat(200))).toBe(1);
    expect(readingMinutes("word ".repeat(401))).toBe(3);
    expect(readingLabel(6)).toBe("6 min read");
  });
});

describe("editor checks", () => {
  it("finds images without alt text", () => {
    expect(imagesMissingAlt("![](/a.webp) and ![ok](/b.webp) and ![ ](/c.webp)")).toBe(2);
  });
  it("formats dates in India time", () => {
    expect(blogDate("2026-10-10T20:00:00Z")).toMatch(/11 October 2026/);
    expect(blogDate(null)).toBe("");
  });
});

describe("safeHref", () => {
  it("allows only safe link targets", () => {
    expect(safeHref("https://example.com")).toBe("https://example.com");
    expect(safeHref("/kushlife")).toBe("/kushlife");
    expect(safeHref("#faq")).toBe("#faq");
    expect(safeHref("mailto:a@b.com")).toBe("mailto:a@b.com");
    expect(safeHref("javascript:alert(1)")).toBe("#");
    expect(safeHref(" JavaScript:alert(1)")).toBe("#");
    expect(safeHref("data:text/html,x")).toBe("#");
    expect(safeHref("//evil.example")).toBe("#");
  });
});

describe("tagLabel", () => {
  it("title-cases tags and keeps acronyms upper case", () => {
    expect(tagLabel("ai room check")).toBe("AI Room Check");
    expect(tagLabel("nri families")).toBe("NRI Families");
    expect(tagLabel("care for parents")).toBe("Care for Parents");
  });
});
