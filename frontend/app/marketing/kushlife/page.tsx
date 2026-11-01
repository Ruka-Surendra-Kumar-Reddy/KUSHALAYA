import type { Metadata } from "next";
import { seoMetadata } from "@/lib/marketing/seo-common";
import { KushLifeMarketingPage } from "@/components/marketing/KushLifeMarketingPage";
import { publicBrandName } from "@/lib/public-brand";

const title = `KushLife Caregiver Visits for Parents at Home | ${publicBrandName()}`;
const description = "Caregiver visits at home with four checks every time: safe, steady, settled, connected. Weekly summaries for families across India and NRI families.";

export const metadata: Metadata = seoMetadata("/kushlife", title, description);

export default function KushLifePage() {
  return <KushLifeMarketingPage />;
}
