"use client";

import Link from "next/link";
import { PricingAdminEditor } from "@/components/livewell/PricingAdminEditor";
import { publicBrandName } from "@/lib/public-brand";

export default function HomeSafetyPricingAdminPage() {
  return (
    <>
      <h1 style={{ marginBottom: "0.25rem" }}>{publicBrandName()} pricing</h1>
      <p className="muted" style={{ marginBottom: "1.25rem" }}>
        Configure margin, labor, travel, GST, and surcharges for automatic customer quotes on
        assessment review. Product sell prices come from the{" "}
        <Link href="/kushalaya/catalog">product catalog</Link>; vendor costs from{" "}
        <Link href="/kushalaya/suppliers">suppliers</Link>.
      </p>
      <PricingAdminEditor />
    </>
  );
}
