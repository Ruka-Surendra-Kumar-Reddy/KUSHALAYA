"use client";

import { useEffect } from "react";
import { registerPortalWorker } from "@/lib/pwa-register";

/** Keep in step with CACHE in public/kushalaya-sw.js. */
const ASSESSOR_SW_VERSION = "10";

/** Installable PWA shell for home safety assessor routes; also evicts any older worker. */
export function HomeSafetyPwaRegister() {
  useEffect(() => {
    void registerPortalWorker("/kushalaya-sw.js", ASSESSOR_SW_VERSION);
  }, []);
  return null;
}
