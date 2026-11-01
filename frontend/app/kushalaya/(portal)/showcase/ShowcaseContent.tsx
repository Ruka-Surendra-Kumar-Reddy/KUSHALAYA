"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ProductShowcase } from "@/components/livewell/ProductShowcase";
import { DEFAULT_SAFETY_CATALOG } from "@/lib/livewell/catalog-defaults";
import type { SafetyCatalog } from "@/lib/livewell/catalog-types";
import { fetchShowcaseCatalog } from "@/lib/livewell/catalogApi";
import { getStoredBranding } from "@/lib/branding";

export default function HomeSafetyShowcasePage() {
  const searchParams = useSearchParams();
  const tenantParam = searchParams.get("tenant");
  const branding = getStoredBranding();
  const tenantId = tenantParam ? Number(tenantParam) : branding?.id ?? 1;

  const [catalog, setCatalog] = useState<SafetyCatalog>(DEFAULT_SAFETY_CATALOG);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchShowcaseCatalog(tenantId)
      .then(setCatalog)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load catalog"));
  }, [tenantId]);

  return (
    <div className="home-safety-app home-safety-showcase-page">
      <header className="home-safety-header">
        <div className="home-safety-header-top">
          <Link href="/kushalaya" className="home-safety-back">
            ← Assessments
          </Link>
        </div>
        <h1>Show family</h1>
        <p className="home-safety-subtitle">Products &amp; packages · presentation mode</p>
      </header>
      <main className="home-safety-main">
        {error && <p className="error-text">{error}</p>}
        <ProductShowcase catalog={catalog} tenantId={tenantId} />
      </main>
    </div>
  );
}
