"use client";

import { useEffect } from "react";
import { registerPortalWorker } from "@/lib/pwa-register";

/** Keep in step with CACHE in public/kushalaya-family-sw.js. */
const FAMILY_SW_VERSION = "7";

/** Installable PWA shell for the family portal; also evicts any older worker. */
export function FamilyPwaRegister() {
  useEffect(() => {
    void registerPortalWorker("/kushalaya-family-sw.js", FAMILY_SW_VERSION);
  }, []);
  return null;
}
