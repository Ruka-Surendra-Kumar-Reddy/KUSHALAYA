"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { PlatformAdminTenantGate } from "@/components/PlatformAdminTenantGate";
import { getStoredAuth } from "@/lib/api";
import { platformAdminNeedsTenantContext } from "@/lib/auth";
import {
  platformAdminGateFeatureLabel,
  platformAdminNeedsTenantForPath,
} from "@/lib/platformAdminRoutes";

function TenantScopeGateInner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const auth = getStoredAuth();

  if (
    !platformAdminNeedsTenantContext(auth) ||
    !platformAdminNeedsTenantForPath(pathname, searchParams)
  ) {
    return <>{children}</>;
  }

  return (
    <PlatformAdminTenantGate
      featureLabel={platformAdminGateFeatureLabel(pathname)}
      backHref="/tenants"
      backLabel="Back to tenants"
    />
  );
}

/** Blocks tenant-scoped pages for super admin without impersonated tenant. */
export function TenantScopeGuard({ children }: { children: React.ReactNode }) {
  const auth = getStoredAuth();
  if (!platformAdminNeedsTenantContext(auth)) {
    return <>{children}</>;
  }

  return (
    <Suspense fallback={children}>
      <TenantScopeGateInner>{children}</TenantScopeGateInner>
    </Suspense>
  );
}
