import { COMPANY_CIN, PUBLIC_EMAIL, PUBLIC_PHONE, REGISTERED_ADDRESS_PARTS } from "@/lib/public-brand";

/** Default share image for every www page: 1200×630 JPG (social sites skip WebP). */
export const MARKETING_OG_IMAGE = {
  url: "https://www.kushalaya.com/marketing/og/kushalaya-home.jpg",
  width: 1200,
  height: 630,
  alt: "Safer homes and care for your parents",
} as const;

/** Stable @id values so the Organization and LocalBusiness nodes link up. */
export const ORG_ID = "https://www.kushalaya.com/#organization";
export const LOCAL_BUSINESS_ID = "https://www.kushalaya.com/#localbusiness";

/** The registered office as a schema.org PostalAddress (one source: lib/public-brand). */
export const POSTAL_ADDRESS = { "@type": "PostalAddress", ...REGISTERED_ADDRESS_PARTS } as const;

/** schema.org Organization for www pages (about, contact, home). */
export function organizationJsonLd(name: string, legalName: string, email: string = PUBLIC_EMAIL) {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": ORG_ID,
    name,
    legalName,
    identifier: COMPANY_CIN,
    address: POSTAL_ADDRESS,
    url: "https://www.kushalaya.com/",
    logo: "https://www.kushalaya.com/brand/kushalaya-icon.png",
    email,
    telephone: PUBLIC_PHONE.e164,
    areaServed: { "@type": "Country", name: "India" },
    contactPoint: {
      "@type": "ContactPoint",
      contactType: "customer support",
      email,
      telephone: PUBLIC_PHONE.e164,
      areaServed: ["IN", "US", "GB", "AE"],
    },
  };
}

/**
 * schema.org LocalBusiness (home, contact, Hyderabad page): the registered
 * office in Hyderabad, serving families across India. Same facts as
 * organizationJsonLd, linked to it by parentOrganization.
 */
export function localBusinessJsonLd(name: string, legalName: string, email: string = PUBLIC_EMAIL, description?: string) {
  const org = organizationJsonLd(name, legalName, email);
  return {
    ...org,
    "@type": "LocalBusiness",
    "@id": LOCAL_BUSINESS_ID,
    ...(description ? { description } : {}),
    image: MARKETING_OG_IMAGE.url,
    parentOrganization: { "@id": ORG_ID },
  };
}

/** schema.org Offers for the care plans on /packages (yearly INR prices). */
export function planOffersJsonLd(
  brand: string,
  plans: { id: string; name: string; fit: string; annualInr: number | null }[],
) {
  return {
    "@context": "https://schema.org",
    "@type": "Service",
    name: `${brand} care plans`,
    serviceType: "Elder care at home",
    provider: { "@type": "Organization", "@id": ORG_ID, name: brand, url: "https://www.kushalaya.com/" },
    areaServed: { "@type": "Country", name: "India" },
    offers: plans
      .filter((p) => p.annualInr !== null)
      .map((p) => ({
        "@type": "Offer",
        name: p.name,
        description: p.fit,
        price: p.annualInr,
        priceCurrency: "INR",
        url: `https://www.kushalaya.com/packages#plans`,
        priceSpecification: {
          "@type": "UnitPriceSpecification",
          price: p.annualInr,
          priceCurrency: "INR",
          unitCode: "ANN",
          valueAddedTaxIncluded: true,
        },
      })),
  };
}
