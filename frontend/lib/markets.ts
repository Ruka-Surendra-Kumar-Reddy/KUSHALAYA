import type { MarketId } from "@workforceos/contracts/client";
import { normalizeMarket } from "@workforceos/contracts/client";

export type { MarketId };
export { DEFAULT_MARKET, normalizeMarket } from "@workforceos/contracts/client";

export type MarketInfo = {
  id: string;
  label: string;
  currency: string;
  tax_label: string;
  payroll_regime: string;
};

export const MARKETS = {
  IN: "IN",
  US: "US",
} as const satisfies Record<string, MarketId>;

import { api } from "./api";

export async function fetchMarkets(): Promise<MarketInfo[]> {
  return api<MarketInfo[]>("/api/v1/tenants/markets");
}
