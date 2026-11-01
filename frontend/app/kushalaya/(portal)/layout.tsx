import type { Metadata, Viewport } from "next";
import { BRAND_ASSETS } from "@/lib/brand-assets";
import { HomeSafetyPwaRegister } from "@/components/livewell/HomeSafetyPwaRegister";

export const metadata: Metadata = {
  title: "KushAlaya — Assessor",
  description: "Home safety risk assessment (100-point score)",
  appleWebApp: {
    capable: true,
    title: "KushAlaya",
  },
  icons: {
    icon: "/brand/kushalaya-icon.png",
    apple: "/brand/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  themeColor: "#0d6e6e",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export default function HomeSafetyPortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      {/* The portal shell is a client component, so the logo is not in the
          server HTML and the browser cannot discover it until React hydrates.
          Preloading here starts the download alongside the page instead.
          The media queries mirror the <picture> in OpsShell, so each screen
          One mark at every width, so one unscoped preload. */}
      <link rel="preload" as="image" href={BRAND_ASSETS.header} fetchPriority="high" />
      <HomeSafetyPwaRegister />
      {children}
    </>
  );
}
