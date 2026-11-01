import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { SeoServicePage } from "@/components/marketing/SeoPages";
import { SEO_ORIGIN, SEO_PROVIDER, seoMetadata } from "@/lib/marketing/seo-common";
import { SEO_SERVICES, seoServiceBySlug } from "@/lib/marketing/seo-services";

export const dynamicParams = false;

export function generateStaticParams() {
  return SEO_SERVICES.map((s) => ({ slug: s.slug }));
}

export function generateMetadata({ params }: { params: { slug: string } }): Metadata {
  const s = seoServiceBySlug(params.slug);
  if (!s) return {};
  return seoMetadata(`/services/${s.slug}`, s.metaTitle, s.metaDescription);
}

export default function ServicePage({ params }: { params: { slug: string } }) {
  const s = seoServiceBySlug(params.slug);
  if (!s) notFound();
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Service",
    name: s.label,
    serviceType: s.serviceType,
    description: s.metaDescription,
    url: `${SEO_ORIGIN}/services/${s.slug}`,
    provider: SEO_PROVIDER,
    areaServed: { "@type": "Country", name: "India" },
  };
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <SeoServicePage slug={s.slug} />
    </>
  );
}
