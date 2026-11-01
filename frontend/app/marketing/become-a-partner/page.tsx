import { publicBrandName, withPublicBrand } from "@/lib/public-brand";
import type { Metadata } from "next";
import { seoMetadata } from "@/lib/marketing/seo-common";
import { BecomePartnerMarketingPage } from "@/components/marketing/BecomePartnerMarketingPage";

const title = withPublicBrand("Become a Partner: Suppliers & Installers | LiveWell360");
const description = withPublicBrand("Join the LiveWell360 Trusted Partner Network. Suppliers and installers get assessment-led work, clear scopes and co-branded recognition.");

export const metadata: Metadata = seoMetadata("/become-a-partner", title, description);

export default function BecomeAPartnerPage() {
  return <BecomePartnerMarketingPage />;
}
