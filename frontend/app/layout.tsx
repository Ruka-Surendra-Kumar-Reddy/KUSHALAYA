import type { Metadata, Viewport } from "next";
import { Noto_Sans_Telugu } from "next/font/google";
import { SiteFooter } from "@/components/SiteFooter";
import "./globals.css";
import "../styles/themes.css";

const notoSansTelugu = Noto_Sans_Telugu({
  subsets: ["telugu"],
  weight: ["400", "600", "700"],
  display: "swap",
  variable: "--font-telugu",
});

export const metadata: Metadata = {
  title: "KushAlaya",
  description: "KushAlaya — home safety, assessments, and family care at home",
  icons: {
    icon: [{ url: "/brand/favicon-32.png", sizes: "32x32", type: "image/png" }, { url: "/favicon.png" }],
    apple: "/brand/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    // The marketing layout adds a "js" class to <html> before React loads (reveal animations).
    <html lang="en" className={notoSansTelugu.variable} suppressHydrationWarning>
      <body>
        <div className="site-frame">
          {children}
          <SiteFooter />
        </div>
      </body>
    </html>
  );
}
