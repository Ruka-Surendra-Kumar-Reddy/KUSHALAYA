import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LiveWell ops",
  description: "Daily work for LiveWell360 — clients, assessments, and visits",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
