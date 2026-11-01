import type { Metadata } from "next";
import { FounderMarketingPage } from "@/components/marketing/FounderMarketingPage";
import { FOUNDER } from "@/lib/marketing/founder";
import { publicBrandName } from "@/lib/public-brand";

const title = `From the founder | ${publicBrandName()}`;
const description = `${FOUNDER.name}, founder of ${publicBrandName()}: why we act before something goes wrong, and how to reach him directly.`;

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: "https://www.kushalaya.com/founder" },
  openGraph: {
    title,
    description,
    type: "profile",
    url: "https://www.kushalaya.com/founder",
    images: [{ url: `https://www.kushalaya.com${FOUNDER.photo}`, width: 900, height: 1125, alt: FOUNDER.photoAlt }],
  },
  robots: { index: true, follow: true },
};

export default function FounderPage() {
  return <FounderMarketingPage />;
}
