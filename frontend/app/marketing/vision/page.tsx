import { publicBrandName, withPublicBrand } from "@/lib/public-brand";
import type { Metadata } from "next";
import { seoMetadata } from "@/lib/marketing/seo-common";
import { VisionMarketingPage } from "@/components/marketing/VisionMarketingPage";

const title = withPublicBrand("Vision Sheet: Ageing Safely at Home | LiveWell360");
const description = "Printable one-pager: home safety assessments, fixes, elder care management and family updates in India, with a free KushCare Discovery QR.";

export const metadata: Metadata = seoMetadata("/vision", title, description);

export default function VisionPage() {
  return <VisionMarketingPage />;
}
