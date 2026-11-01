import type { Metadata } from "next";

import { SeoFaqPage } from "@/components/marketing/SeoPages";
import { seoMetadata } from "@/lib/marketing/seo-common";
import { SEO_FAQ_ALL } from "@/lib/marketing/seo-faq";

export const metadata: Metadata = seoMetadata(
  "/faq",
  "Elder Care & Home Safety FAQ | KushAlaya",
  "Answers about KushAlaya home safety assessments, AI room checks, KushLife caregiver visits, prices, privacy and care for parents in India from abroad.",
);

const faqJsonLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: SEO_FAQ_ALL.map((f) => ({
    "@type": "Question",
    name: f.q,
    acceptedAnswer: { "@type": "Answer", text: f.a },
  })),
};

export default function FaqPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }} />
      <SeoFaqPage />
    </>
  );
}
