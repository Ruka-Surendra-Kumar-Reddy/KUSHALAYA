import { publicBrandName, withPublicBrand } from "@/lib/public-brand";
import type { Metadata } from "next";
import { seoMetadata } from "@/lib/marketing/seo-common";
import { BrochureMarketingPage } from "@/components/marketing/BrochureMarketingPage";

const title = withPublicBrand("Brochure: Home Safety for Seniors | LiveWell360");
const description = withPublicBrand("Printable LiveWell360 brochure: why falls matter, how we screen, assess and fix homes, and a QR code to book a free KushCare Discovery.");

export const metadata: Metadata = seoMetadata("/brochure", title, description);

export default function BrochurePage() {
  return <BrochureMarketingPage />;
}
