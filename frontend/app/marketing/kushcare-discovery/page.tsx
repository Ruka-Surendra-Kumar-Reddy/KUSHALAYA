import { publicBrandName, withPublicBrand } from "@/lib/public-brand";
import type { Metadata } from "next";
import { MARKETING_OG_IMAGE } from "@/lib/marketing/seo";
import { ParentCareCheckMarketingPage } from "@/components/marketing/ParentCareCheckMarketingPage";

const PAGE_URL = "https://www.kushalaya.com/kushcare-discovery";
const title = withPublicBrand("Free Home Safety Assessment for Seniors | LiveWell360");
const description =
  "Book a free KushCare Discovery: we call you back and check your parents' home for fall risks. Elder care at home across India, from Hyderabad.";

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: PAGE_URL },
  openGraph: {
    title,
    description,
    type: "website",
    images: [MARKETING_OG_IMAGE],
    url: PAGE_URL,
    locale: "en_IN",
    siteName: withPublicBrand("LiveWell360"),
  },
  twitter: { card: "summary_large_image", title, description, images: [MARKETING_OG_IMAGE.url] },
  robots: { index: true, follow: true },
};

export default function KushcareDiscoveryPage() {
  const brand = publicBrandName();
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Service",
    name: "KushCare Discovery",
    serviceType: "Home safety assessment for seniors",
    url: PAGE_URL,
    provider: { "@type": "Organization", name: brand, url: "https://www.kushalaya.com/" },
    areaServed: { "@type": "Country", name: "India" },
    offers: { "@type": "Offer", price: 0, priceCurrency: "INR", url: PAGE_URL },
  };
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <ParentCareCheckMarketingPage />
    </>
  );
}
