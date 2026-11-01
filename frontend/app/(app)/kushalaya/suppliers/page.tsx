"use client";

import Link from "next/link";
import { SuppliersAdminEditor } from "@/components/livewell/SuppliersAdminEditor";
import { publicBrandName } from "@/lib/public-brand";

export default function HomeSafetySuppliersAdminPage() {
  return (
    <>
      <h1 style={{ marginBottom: "0.25rem" }}>{publicBrandName()} suppliers</h1>
      <p className="muted" style={{ marginBottom: "1.25rem" }}>
        Configure multiple vendors per catalog SKU — supplier cost, MOQ, lead time, and preferred
        vendor. Partner roles, tiers, and visit ratings live on{" "}
        <Link href="/kushalaya/partners">Partners</Link>. Import/export master workbook sheets
        (JSON + CSV). Customer quotes use sell prices from the{" "}
        <Link href="/kushalaya/catalog">product catalog</Link>; purchase orders on assessment review
        use vendor selection.
      </p>
      <SuppliersAdminEditor />
    </>
  );
}
