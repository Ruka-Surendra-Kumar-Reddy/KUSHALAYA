import type { Metadata, Viewport } from "next";

/**
 * Shared by the family sign-in page and the (portal) group.
 *
 * Renders a fragment on purpose: globals.css and ks-shell.css key the sticky
 * copyright footer off `.site-frame > .home-safety-family-login` and
 * `.site-frame > .ks-portal-root` as DIRECT children, so this layout must not
 * add a wrapper element.
 *
 * Its job is the PWA manifest link (see app/family-manifest.webmanifest) and a
 * light theme colour for the phone status bar, on the sign-in page too — the
 * old manifest was never served, so installs had no light splash to show.
 */
export const metadata: Metadata = {
  manifest: "/family-manifest.webmanifest",
};

export const viewport: Viewport = {
  themeColor: "#ffffff",
  width: "device-width",
  initialScale: 1,
};

export default function FamilyLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
