"use client";

import Link from "next/link";
import { MasterDataAdminEditor } from "@/components/livewell/MasterDataAdminEditor";

export default function HomeSafetyMasterDataPage() {
  return (
    <>
      <h1 style={{ marginBottom: "0.25rem" }}>Master data — spreadsheet upload</h1>
      <p className="muted" style={{ marginBottom: "1.25rem" }}>
        Upload <strong>Kushalaya_Configuration.xlsx</strong>, then Approve to update rubric,
        solutions, catalog, pricing, and suppliers. Per-entity editors remain at{" "}
        <Link href="/kushalaya/rubric">checklist</Link>,{" "}
        <Link href="/kushalaya/solutions">solutions</Link>,{" "}
        <Link href="/kushalaya/catalog">catalog</Link>,{" "}
        <Link href="/kushalaya/pricing">pricing</Link>, and{" "}
        <Link href="/kushalaya/suppliers">suppliers</Link>.
      </p>
      <MasterDataAdminEditor />
    </>
  );
}
