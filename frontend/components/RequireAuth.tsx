"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";
import { RequireStaffAuth } from "@workforceos/contracts/shell";

import { PortalLoading } from "@/components/PortalLoading";
import { getStoredAuth } from "@/lib/api";
import { homePathForRole, isStaffRole } from "@/lib/auth";

/** Admin portal — staff roles only (blocks family & caregiver accounts). */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const onRedirect = useCallback((path: string) => router.replace(path), [router]);

  return (
    <RequireStaffAuth
      getSession={getStoredAuth}
      isStaffRole={isStaffRole}
      homePathForRole={homePathForRole}
      onRedirect={onRedirect}
      loading={<PortalLoading />}
    >
      {children}
    </RequireStaffAuth>
  );
}
