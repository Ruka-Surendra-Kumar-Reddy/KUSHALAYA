"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import {
  DEFAULT_BRANDING,
  applyStoredBranding,
  loadBrandingFromApi,
  type TenantBranding,
} from "@/lib/branding";
import { getStoredAuth } from "@/lib/api";

type BrandingContextValue = {
  branding: TenantBranding;
  refresh: () => Promise<TenantBranding>;
};

const BrandingContext = createContext<BrandingContextValue | null>(null);

export function BrandingProvider({ children }: { children: React.ReactNode }) {
  const [branding, setBranding] = useState<TenantBranding>(() => {
    if (typeof window !== "undefined") {
      return applyStoredBranding(getStoredAuth());
    }
    return DEFAULT_BRANDING;
  });

  const refresh = useCallback(
    () => loadBrandingFromApi().then((b) => {
      setBranding(b);
      return b;
    }),
    [],
  );

  useEffect(() => {
    loadBrandingFromApi().then(setBranding);
  }, []);

  return (
    <BrandingContext.Provider value={{ branding, refresh }}>
      {children}
    </BrandingContext.Provider>
  );
}

export function useBranding() {
  const ctx = useContext(BrandingContext);
  if (!ctx) {
    throw new Error("useBranding must be used within BrandingProvider");
  }
  return ctx.branding;
}

export function useOptionalBranding(): TenantBranding | null {
  return useContext(BrandingContext)?.branding ?? null;
}

export function useBrandingRefresh() {
  const ctx = useContext(BrandingContext);
  if (!ctx) {
    throw new Error("useBrandingRefresh must be used within BrandingProvider");
  }
  return ctx.refresh;
}
