import { AdminLocaleProvider } from "@/components/AdminLocaleProvider";
import { AppShell } from "@/components/AppShell";
import { BrandingProvider } from "@/components/BrandingProvider";
import { RequireAuth } from "@/components/RequireAuth";
import { TenantScopeGuard } from "@/components/TenantScopeGuard";
import { VerticalRouteGuard } from "@/components/VerticalRouteGuard";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RequireAuth>
      <BrandingProvider>
        <AdminLocaleProvider>
          <VerticalRouteGuard>
            <AppShell>
              <TenantScopeGuard>{children}</TenantScopeGuard>
            </AppShell>
          </VerticalRouteGuard>
        </AdminLocaleProvider>
      </BrandingProvider>
    </RequireAuth>
  );
}
