"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { PortalLoading } from "@/components/PortalLoading";
import { getStoredAuth } from "@/lib/api";
import { isElderPortalRole } from "@/lib/auth";
import { familyLoginPath } from "@/lib/livewell/family-paths";

export function RequireFamilyAuth({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const stored = getStoredAuth();
    // Host-aware: a client-side replace to the internal path would leave
    // family.kushalaya.com/kushalaya/family/login in the address bar.
    if (!stored) {
      router.replace(familyLoginPath());
      return;
    }
    if (!isElderPortalRole(stored.role)) {
      router.replace(familyLoginPath());
      return;
    }
    setReady(true);
  }, [router]);

  if (!ready) {
    return (
      <main className="home-safety-app home-safety-family home-safety-loading">
        <PortalLoading />
      </main>
    );
  }

  return <>{children}</>;
}
