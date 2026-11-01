import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { SeoCityPage } from "@/components/marketing/SeoPages";
import { SEO_BRAND, SEO_ORIGIN, SEO_PROVIDER, seoMetadata } from "@/lib/marketing/seo-common";
import { localBusinessJsonLd } from "@/lib/marketing/seo";
import { LEGAL_ENTITY_NAME } from "@/lib/public-brand";
import { SEO_CITIES, seoCityBySlug } from "@/lib/marketing/seo-cities";

export const dynamicParams = false;

export function generateStaticParams() {
  return SEO_CITIES.map((c) => ({ city: c.slug }));
}

export function generateMetadata({ params }: { params: { city: string } }): Metadata {
  const c = seoCityBySlug(params.city);
  if (!c) return {};
  return seoMetadata(`/elder-care/${c.slug}`, c.metaTitle, c.metaDescription);
}

export default function CityPage({ params }: { params: { city: string } }) {
  const c = seoCityBySlug(params.city);
  if (!c) notFound();
  // A Service with an areaServed city. Only Hyderabad (the registered office)
  // also gets a LocalBusiness: there is no office in the other cities.
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Service",
    name: `Elder care and home safety in ${c.name}`,
    serviceType: "Elder care and home safety",
    description: c.metaDescription,
    url: `${SEO_ORIGIN}/elder-care/${c.slug}`,
    provider: SEO_PROVIDER,
    areaServed: {
      "@type": "City",
      name: c.name,
      containedInPlace: { "@type": "AdministrativeArea", name: c.state },
    },
  };
  const localBusiness =
    c.slug === "hyderabad" ? localBusinessJsonLd(SEO_BRAND, LEGAL_ENTITY_NAME, undefined, c.metaDescription) : null;
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      {localBusiness ? (
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(localBusiness) }} />
      ) : null}
      <SeoCityPage slug={c.slug} />
    </>
  );
}
