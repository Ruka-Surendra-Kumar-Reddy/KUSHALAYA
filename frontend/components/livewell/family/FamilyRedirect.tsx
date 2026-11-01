"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useFamilyHref } from "./FamilyLink";

/**
 * A family page that was merged into another (Phase 2E). Page loads are
 * redirected by middleware.ts; this covers in-app (router) navigations.
 */
export function FamilyRedirect({ to }: { to: string }) {
  const router = useRouter();
  const href = useFamilyHref();
  const target = href(to);
  useEffect(() => {
    router.replace(target);
  }, [router, target]);
  return <p className="muted" style={{ padding: "1rem" }}>Opening…</p>;
}
