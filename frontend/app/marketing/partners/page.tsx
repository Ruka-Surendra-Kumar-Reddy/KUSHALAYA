import { publicBrandName, withPublicBrand } from "@/lib/public-brand";
import type { Metadata } from "next";
import { seoMetadata } from "@/lib/marketing/seo-common";
import { PartnersMarketingPage } from "@/components/marketing/PartnersMarketingPage";

const title = withPublicBrand("Trusted Partner Network | LiveWell360");
const description = "Verified suppliers and installers for senior home safety across India. Assessment-led work and co-branded recognition for trusted partners.";

export const metadata: Metadata = seoMetadata("/partners", title, description);

export default function PartnersPage() {
  return <PartnersMarketingPage />;
}
