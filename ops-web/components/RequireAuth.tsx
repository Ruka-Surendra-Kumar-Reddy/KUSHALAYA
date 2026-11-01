"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getStoredAuth, isStaffRole } from "@/lib/api";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    const auth = getStoredAuth();
    if (!auth || !isStaffRole(auth.role)) {
      router.replace(`/login?next=${encodeURIComponent(pathname || "/dashboard")}`);
    }
  }, [pathname, router]);

  return <>{children}</>;
}
