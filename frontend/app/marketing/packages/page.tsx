import { publicBrandName, withPublicBrand } from "@/lib/public-brand";
import type { Metadata } from "next";
import { seoMetadata } from "@/lib/marketing/seo-common";
import { planOffersJsonLd } from "@/lib/marketing/seo";
import { CARE_PLANS } from "@/lib/marketing/plans";
import { PackagesMarketingPage } from "@/components/marketing/PackagesMarketingPage";

const title = withPublicBrand("Elder Care Plans & Prices in India | LiveWell360");
const description = "Elder care at home plans with GST included, monthly billing, pay-as-you-go caregiver visits and home safety products like the SOS wearable.";

export const metadata: Metadata = seoMetadata("/packages", title, description);

export default function PackagesPage() {
  const offers = planOffersJsonLd(publicBrandName(), CARE_PLANS);
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(offers) }} />
      <PackagesMarketingPage />
    </>
  );
}
