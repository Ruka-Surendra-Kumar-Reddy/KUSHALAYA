import { api } from "@/lib/api";
import type { SafeHomePricingConfig } from "./pricing-types";
import { getLocalPricingConfig, saveLocalPricingConfig } from "./pricing";

export async function fetchAdminPricing(): Promise<SafeHomePricingConfig> {
  const config = await api<SafeHomePricingConfig>("/api/v1/home-safety/pricing");
  saveLocalPricingConfig(config);
  return config;
}

export async function saveAdminPricing(config: SafeHomePricingConfig): Promise<SafeHomePricingConfig> {
  const saved = await api<SafeHomePricingConfig>("/api/v1/home-safety/pricing", {
    method: "PUT",
    body: JSON.stringify(config),
  });
  saveLocalPricingConfig(saved);
  return saved;
}

export function getCachedPricing(): SafeHomePricingConfig {
  return getLocalPricingConfig();
}
