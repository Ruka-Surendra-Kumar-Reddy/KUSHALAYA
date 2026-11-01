import { LEGAL_ENTITY_NAME } from "@/lib/public-brand";

/**
 * Global footer shown on every page (staff portal, family portal, marketing).
 * Replaces the former "Powered by Tek Matrix, LLC" credit — the software is now
 * owned by Kushalaya Pvt Ltd.
 */
export function SiteFooter() {
  // Server-rendered, so statically prerendered pages carry the build year.
  const year = new Date().getFullYear();
  return (
    <footer className="site-footer" aria-label={`Copyright ${LEGAL_ENTITY_NAME}`}>
      <span className="site-footer-copy">
        © {year} {LEGAL_ENTITY_NAME}. All rights reserved.
      </span>
    </footer>
  );
}
