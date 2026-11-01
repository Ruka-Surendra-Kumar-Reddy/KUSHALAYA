import type { Metadata } from "next";
import { seoMetadata } from "@/lib/marketing/seo-common";
import { localBusinessJsonLd } from "@/lib/marketing/seo";
import { EMAILS } from "@/lib/marketing/family-contacts";
import { ContactMarketingPage } from "@/components/marketing/ContactMarketingPage";
import { LEGAL_ENTITY_NAME, publicBrandName } from "@/lib/public-brand";

const title = `Contact Us: Elder Care in Hyderabad & India | ${publicBrandName()}`;
const description = `Call, WhatsApp or email ${publicBrandName()} about elder care at home for your parents, in Hyderabad or anywhere in India. Request a free call back.`;

export const metadata: Metadata = seoMetadata("/contact", title, description);

export default function ContactPage() {
  const org = localBusinessJsonLd(publicBrandName(), LEGAL_ENTITY_NAME, EMAILS.contact, description);
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(org) }} />
      <ContactMarketingPage />
    </>
  );
}
