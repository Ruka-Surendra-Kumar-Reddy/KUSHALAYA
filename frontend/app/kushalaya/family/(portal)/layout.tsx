import { withPublicBrand } from "@/lib/public-brand";
import { BRAND_ASSETS } from "@/lib/brand-assets";
import type { Metadata, Viewport } from "next";
import { FamilyPwaRegister } from "@/components/livewell/family/FamilyPwaRegister";
import { RequireFamilyAuth } from "@/components/livewell/family/RequireFamilyAuth";
import { PrivacyConsentGate } from "@/components/livewell/family/PrivacyConsentGate";
import { AdminLocaleProvider } from "@/components/AdminLocaleProvider";
import { SosSiren } from "@/components/SosSiren";
import { familyFont } from "@/components/livewell/family/family-font";

export const metadata: Metadata = {
  title: withPublicBrand("LiveWell360 — Family"),
  description: withPublicBrand("LiveWell360 Safety Score, living plan, visits, and alerts"),
  appleWebApp: {
    capable: true,
    title: withPublicBrand("LiveWell360 Family"),
  },
  icons: {
    icon: "/brand/kushalaya-icon.png",
    apple: "/brand/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  // Matches the white top bar so the phone status bar blends with the app.
  themeColor: "#ffffff",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export default function FamilyPortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    // Deliberately NOT .home-safety-family-portal: that class (and the
    // .site-frame:has() rule keyed off it) locks the frame to 100dvh with
    // overflow:hidden, which the old bottom-tab shell relied on for its inner
    // scroll pane. This shell scrolls the document instead.
    //
    // `ks-portal-root` is load-bearing: components/ks-shell.css keys the
    // sticky copyright footer off `.site-frame:has(> .ks-portal-root)`.
    // Rename it and the footer silently disappears from the whole portal.
    <div className={`ks-portal-root ${familyFont.variable}`}>
      {/* Same locale provider as the staff portal, so families get the
          English / Telugu switch too. */}
      {/* The portal shell is a client component, so the logo is not in the
          server HTML and the browser cannot discover it until React hydrates.
          Preloading here starts the download alongside the page instead.
          One mark at every width, so one unscoped preload. */}
      <link rel="preload" as="image" href={BRAND_ASSETS.header} fetchPriority="high" />
      <AdminLocaleProvider>
        <RequireFamilyAuth>
          <FamilyPwaRegister />
          <SosSiren />
          <PrivacyConsentGate />
          {children}
        </RequireFamilyAuth>
      </AdminLocaleProvider>
    </div>
  );
}
