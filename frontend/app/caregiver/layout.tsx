import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

/** Install-as-app support for the caregiver field app (see app/caregiver-manifest.webmanifest). */
export const metadata: Metadata = {
  title: "Caregiver · KushAlaya",
  manifest: "/caregiver-manifest.webmanifest",
  appleWebApp: { capable: true, title: "Caregiver", statusBarStyle: "default" },
};

export const viewport: Viewport = { themeColor: "#0e2a4f" };

export default function CaregiverLayout({ children }: { children: ReactNode }) {
  return children;
}
