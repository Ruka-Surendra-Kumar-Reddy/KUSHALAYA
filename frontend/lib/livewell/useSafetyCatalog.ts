"use client";

import { useEffect, useState } from "react";
import type { SafetyCatalog } from "./catalog-types";
import { DEFAULT_SAFETY_CATALOG } from "./catalog-defaults";
import { getLocalCatalog } from "./catalog";

export function useSafetyCatalog(loader?: () => Promise<SafetyCatalog>): SafetyCatalog {
  const [catalog, setCatalog] = useState<SafetyCatalog>(DEFAULT_SAFETY_CATALOG);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const data = loader ? await loader() : getLocalCatalog();
        if (!cancelled) setCatalog(data);
      } catch {
        if (!cancelled) setCatalog(getLocalCatalog());
      }
    })();

    const onUpdate = () => setCatalog(getLocalCatalog());
    window.addEventListener("home-safety-catalog-updated", onUpdate);
    return () => {
      cancelled = true;
      window.removeEventListener("home-safety-catalog-updated", onUpdate);
    };
  }, [loader]);

  return catalog;
}
