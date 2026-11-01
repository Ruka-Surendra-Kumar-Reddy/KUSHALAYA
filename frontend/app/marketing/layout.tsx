import type { Metadata } from "next";

import { portalFont } from "@/components/portal-font";
import { MARKETING_OG_IMAGE } from "@/lib/marketing/seo";
import "./marketing.css";

/**
 * Defaults for every www page. A page's own `openGraph` block replaces this
 * one, so each page also lists MARKETING_OG_IMAGE (lib/marketing/seo.ts).
 */
export const metadata: Metadata = {
  metadataBase: new URL("https://www.kushalaya.com"),
  openGraph: { images: [MARKETING_OG_IMAGE] },
  twitter: { card: "summary_large_image", images: [MARKETING_OG_IMAGE.url] },
};

/** Public site — same typeface and brand tokens as the portals, no admin chrome. */
/**
 * Runs before the page paints: scroll-reveal content is only hidden once JS is
 * known to be running (html.js). If the app hasn't hydrated within 4 s (script
 * error, slow network) the class is removed again so nothing stays invisible.
 */
const REVEAL_BOOT = `(function(){var d=document.documentElement;d.classList.add("js");setTimeout(function(){if(!d.classList.contains("mk-hydrated"))d.classList.remove("js")},4000)})();`;

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className={`mk-root ${portalFont.variable}`}>
      <script dangerouslySetInnerHTML={{ __html: REVEAL_BOOT }} />
      {children}
    </div>
  );
}
