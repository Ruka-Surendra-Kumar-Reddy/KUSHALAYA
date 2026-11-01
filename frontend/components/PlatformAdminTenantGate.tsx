"use client";

import Link from "next/link";

type PlatformAdminTenantGateProps = {
  featureLabel?: string;
  backHref?: string;
  backLabel?: string;
};

/** Shown when SYSTEM_ADMIN has no tenant_id — tenant-scoped APIs require agency context. */
export function PlatformAdminTenantGate({
  featureLabel = "this view",
  backHref = "/dashboard",
  backLabel = "Back to dashboard",
}: PlatformAdminTenantGateProps) {
  return (
    <div className="card">
      <p>
        Platform administrators need an agency context for {featureLabel}. Open a
        tenant from <Link href="/tenants">Tenants</Link> to work in that agency&apos;s
        data, or log in as a tenant admin.
      </p>
      {backHref && (
        <p style={{ marginTop: "0.75rem", marginBottom: 0 }}>
          <Link href={backHref}>{backLabel}</Link>
        </p>
      )}
    </div>
  );
}
