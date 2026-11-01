import type { Metadata } from "next";
import { seoMetadata } from "@/lib/marketing/seo-common";
import { AboutMarketingPage } from "@/components/marketing/AboutMarketingPage";
import { LEGAL_ENTITY_NAME, publicBrandName } from "@/lib/public-brand";
import { organizationJsonLd } from "@/lib/marketing/seo";
import { EMAILS } from "@/lib/marketing/family-contacts";

const title = `About Us: Elder Care Across India | ${publicBrandName()}`;
const description = `${publicBrandName()} helps families across India keep ageing parents safe at home with home safety checks, fixes and caregiver visits. Meet the team.`;

export const metadata: Metadata = seoMetadata("/about", title, description);

export default function AboutPage() {
  const org = organizationJsonLd(publicBrandName(), LEGAL_ENTITY_NAME, EMAILS.contact);
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(org) }} />
      <AboutMarketingPage />
    </>
  );
}
