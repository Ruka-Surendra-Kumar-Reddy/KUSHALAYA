import { publicBrandName, withPublicBrand } from "@/lib/public-brand";
import type { Metadata } from "next";
import { seoMetadata } from "@/lib/marketing/seo-common";
import { SafeHomesMarketingPage } from "@/components/marketing/SafeHomesMarketingPage";

const title = withPublicBrand("Fall Prevention & Home Safety for Seniors | LiveWell360");
const description = "Falls are the top cause of injury in older adults, and most are preventable. We screen, assess and fix homes across India, guided by CDC STEADI.";

export const metadata: Metadata = seoMetadata("/safe-homes", title, description);

export default function SafeHomesPage() {
  return <SafeHomesMarketingPage />;
}
