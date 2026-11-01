"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback } from "react";
import { VerticalRouteGuard as CoreVerticalRouteGuard } from "@workforceos/contracts/shell";

import { useBranding } from "@/components/BrandingProvider";
import { isPathAllowedForVertical } from "@/lib/features";

/** Redirects when the current route belongs to another vertical pack. */
export function VerticalRouteGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const branding = useBranding();
  const onRedirect = useCallback((path: string) => router.replace(path), [router]);

  return (
    <CoreVerticalRouteGuard
      pathname={pathname}
      vertical={branding.vertical}
      isPathAllowed={isPathAllowedForVertical}
      onRedirect={onRedirect}
    >
      {children}
    </CoreVerticalRouteGuard>
  );
}
