import { LEGAL_ENTITY_NAME, publicBrandName, withPublicBrand } from "@/lib/public-brand";
import type { Metadata } from "next";
import { FamilyMarketingPage } from "@/components/marketing/FamilyMarketingPage";
import { FAQS } from "@/lib/marketing/content";
import { EMAILS } from "@/lib/marketing/family-contacts";
import { localBusinessJsonLd, organizationJsonLd } from "@/lib/marketing/seo";

const title = withPublicBrand("Elder Care at Home & Fall Prevention | LiveWell360");
const description =
  "Elder care at home across India: a free home safety assessment, fall-prevention fixes and caregiver visits, with updates for NRI families.";

export const metadata: Metadata = {
  title,
  description,
  keywords: [
    "elder care at home",
    "fall prevention for seniors",
    "home safety assessment for seniors",
    "NRI parent care",
    "elder care Hyderabad",
    withPublicBrand("LiveWell360"),
    "bathroom grab bars for seniors",
  ],
  alternates: {
    canonical: "https://www.kushalaya.com/",
  },
  openGraph: {
    title,
    description,
    type: "website",
    url: "https://www.kushalaya.com/",
    locale: "en_IN",
    siteName: withPublicBrand("LiveWell360"),
    images: [
      {
        url: "https://www.kushalaya.com/marketing/og/kushalaya-home.jpg",
        width: 1200,
        height: 630,
        alt: withPublicBrand("LiveWell360 — Safer homes and care for your parents"),
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: ["https://www.kushalaya.com/marketing/og/kushalaya-home.jpg"],
  },
  robots: {
    index: true,
    follow: true,
  },
};

/** Built from the same FAQ list the page shows, so search results never disagree with it. */
const faqJsonLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: FAQS.map((f) => ({
    "@type": "Question",
    name: f.q,
    acceptedAnswer: { "@type": "Answer", text: f.a },
  })),
};

const orgJsonLd = organizationJsonLd(withPublicBrand("LiveWell360"), LEGAL_ENTITY_NAME, EMAILS.contact);
const localBusinessLd = localBusinessJsonLd(withPublicBrand("LiveWell360"), LEGAL_ENTITY_NAME, EMAILS.contact, description);

export default function MarketingHomePage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(orgJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(localBusinessLd) }}
      />
      <FamilyMarketingPage />
    </>
  );
}
