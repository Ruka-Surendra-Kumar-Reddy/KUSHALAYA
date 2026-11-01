"use client";

/**
 * "Services" and "Cities we serve" link columns for the www footer.
 * Renders two `mk-footer-col` blocks, so mount it inside `.mk-footer-grid`
 * (MarketingShell) next to the other columns.
 */
import { MkLink as Link } from "./MkLink";
import { SEO_CITIES } from "@/lib/marketing/seo-cities";
import { SEO_SERVICES } from "@/lib/marketing/seo-services";
import "@/app/marketing/seo-pages.css";

export function SeoFooterLinks() {
  return (
    <>
      <nav className="mk-footer-col seo-footer-col" aria-label="Services">
        <p className="mk-footer-label">Services</p>
        {SEO_SERVICES.map((s) => (
          <Link key={s.slug} href={`/services/${s.slug}`}>
            {s.label}
          </Link>
        ))}
        <Link href="/faq">FAQ</Link>
      </nav>
      <nav className="mk-footer-col seo-footer-col seo-footer-cities" aria-label="Cities we serve">
        <p className="mk-footer-label">Cities we serve</p>
        {SEO_CITIES.map((c) => (
          <Link key={c.slug} href={`/elder-care/${c.slug}`}>
            {c.name}
          </Link>
        ))}
      </nav>
    </>
  );
}
