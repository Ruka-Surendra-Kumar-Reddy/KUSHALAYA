"use client";

import { getStoredAuth } from "@/lib/api";
import { getStoredBrandingForAuth } from "@/lib/branding";
import { LocaleProvider } from "@/lib/i18n/context";
import { LOCALE_STORAGE_KEY, MESSAGE_CATALOGS } from "@/lib/i18n";
import { useOptionalBranding } from "./BrandingProvider";

export function AdminLocaleProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const branding = useOptionalBranding();
  const stored =
    typeof window !== "undefined"
      ? getStoredBrandingForAuth(getStoredAuth())
      : null;
  const market = branding?.market ?? stored?.market;

  return (
    <LocaleProvider
      market={market}
      catalogs={MESSAGE_CATALOGS}
      localeStorageKey={LOCALE_STORAGE_KEY}
    >
      {children}
    </LocaleProvider>
  );
}
