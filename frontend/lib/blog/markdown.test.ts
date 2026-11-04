import { describe, expect, it } from "vitest";

import { parseBlocks } from "./markdown";

describe("tables", () => {
  it("reads a header, a rule and rows", () => {
    expect(parseBlocks("Intro\n\n| Care | Cost |\n| --- | --- |\n| Nurse | ₹1 |\n| Attendant | ₹2 |\n\nAfter")).toEqual([
      { kind: "p", text: "Intro" },
      { kind: "table", head: ["Care", "Cost"], rows: [["Nurse", "₹1"], ["Attendant", "₹2"]] },
      { kind: "p", text: "After" },
    ]);
  });

  it("leaves a stray pipe in a paragraph alone", () => {
    expect(parseBlocks("a | b\nnext line")).toEqual([{ kind: "p", text: "a | b next line" }]);
  });
});
