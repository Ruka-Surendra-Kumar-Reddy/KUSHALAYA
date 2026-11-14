import type { Metadata } from "next";
import { withPublicBrand } from "@/lib/public-brand";
import { seoMetadata } from "@/lib/marketing/seo-common";
import { ServicesMarketingPage } from "@/components/marketing/ServicesMarketingPage";

const title = withPublicBrand("Our Services: LiveWell360 Family Partner");
const description = withPublicBrand(
  "What your LiveWell360 Family Partner does for your parent at home, and the services we arrange through verified partners: health, safety, daily life, companionship, mobility and more.",
);

export const metadata: Metadata = seoMetadata("/services", title, description);

export default function ServicesPage() {
  return <ServicesMarketingPage />;
}
