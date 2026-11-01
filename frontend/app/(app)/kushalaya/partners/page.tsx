"use client";

import Link from "next/link";
import { PartnersAdminEditor } from "@/components/livewell/PartnersAdminEditor";
import { withPublicBrand } from "@/lib/public-brand";

export default function LiveWellPartnersAdminPage() {
  return (
    <>
      <h1 style={{ marginBottom: "0.25rem" }}>Partners — suppliers &amp; installers</h1>
      <p className="muted" style={{ marginBottom: "1.25rem" }}>
        {withPublicBrand("Founding Partner directory for LiveWell360.")} Mark each organization as a{" "}
        <strong>supplier</strong> (catalog products), an <strong>installer</strong> (field visits),
        or both. Families rate the <em>visit / installation experience</em>; we average the last N
        reviews into a rolling partner rating. Product cost offers stay on{" "}
        <Link href="/kushalaya/suppliers">Suppliers</Link>.
      </p>
      <PartnersAdminEditor />
    </>
  );
}
