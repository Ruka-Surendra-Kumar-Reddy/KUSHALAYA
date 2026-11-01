"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Flash } from "@/components/Flash";
import { PricingConfigFields } from "@/components/livewell/PricingConfigFields";
import { DEFAULT_SAFEHOME_PRICING } from "@/lib/livewell/pricing-defaults";
import { fetchAdminPricing, saveAdminPricing } from "@/lib/livewell/pricingApi";
import { normalizePricingConfig, resetLocalPricingConfig } from "@/lib/livewell/pricing";
import type { SafeHomePricingConfig } from "@/lib/livewell/pricing-types";

export function PricingAdminEditor() {
  const [config, setConfig] = useState<SafeHomePricingConfig>(DEFAULT_SAFEHOME_PRICING);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAdminPricing()
      .then(setConfig)
      .catch(() => setConfig(DEFAULT_SAFEHOME_PRICING))
      .finally(() => setLoading(false));
  }, []);

  function patch(partial: Partial<SafeHomePricingConfig>) {
    setConfig((prev) => normalizePricingConfig({ ...prev, ...partial }));
  }

  async function savePricing() {
    setError("");
    try {
      const saved = await saveAdminPricing(config);
      setConfig(saved);
      setMessage("Pricing configuration saved. Assess review quotes will use these rates.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    }
  }

  function resetPricing() {
    if (!window.confirm("Reset pricing to factory defaults?")) return;
    setConfig(resetLocalPricingConfig());
    setMessage("Reset locally — click Save to push to server.");
  }

  if (loading) return <p>Loading pricing…</p>;

  return (
    <div className="home-safety-pricing-admin home-safety-rubric-admin">
      <Flash message={message} error={error} onClear={() => { setMessage(""); setError(""); }} />

      <div
        className="home-safety-sync-hint muted"
        style={{
          padding: "0.65rem 0.85rem",
          marginBottom: "1rem",
          fontSize: "0.88rem",
          borderLeft: "4px solid var(--color-muted, #94a3b8)",
        }}
      >
        These rates map to sheet <strong>09_Pricing</strong> in{" "}
        <Link href="/kushalaya/master-data">Master Data</Link>. After saving here,{" "}
        <strong>Export current workbook</strong> and commit the xlsx so git stays in sync with
        production. Import/approve on Master Data is the version-controlled path.
      </div>

      <div className="home-safety-rubric-admin actions" style={{ marginBottom: "1rem" }}>
        <button type="button" className="primary" onClick={() => void savePricing()}>
          Save pricing
        </button>
        <button type="button" className="secondary" onClick={resetPricing}>
          Reset defaults
        </button>
      </div>

      <PricingConfigFields config={config} onPatch={patch} />
    </div>
  );
}
