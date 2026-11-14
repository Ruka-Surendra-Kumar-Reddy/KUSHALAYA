import { headers } from "next/headers";

import { CARE_PLAN_CATALOG, HOME_ASSESSMENT, SINGLE_VISIT, inr } from "@/lib/care-plan-catalog";
import { isMarketingHost } from "@/lib/hosts";
import { SEO_CITIES } from "@/lib/marketing/seo-cities";
import { SEO_SERVICES } from "@/lib/marketing/seo-services";
import { siteOrigin } from "@/lib/marketing/site-origin";
import {
  COMPANY_CIN,
  COMPANY_GSTIN,
  LEGAL_ENTITY_NAME,
  PUBLIC_EMAIL,
  PUBLIC_PHONE,
  REGISTERED_ADDRESS,
} from "@/lib/public-brand";

/**
 * /llms.txt — plain-text summary for AI crawlers (www only). Prices come from
 * lib/care-plan-catalog.ts and contact facts from lib/public-brand.ts, so this
 * never drifts from the site. The middleware passes "." paths straight through.
 */
export const dynamic = "force-dynamic";

export function GET() {
  const host = headers().get("host") || "";
  if (!isMarketingHost(host)) return new Response("Not found", { status: 404 });
  const o = siteOrigin(host);
  const plans = CARE_PLAN_CATALOG.map(
    (p) =>
      `- ${p.name}: ${inr(p.annualPaise)} a year` +
      (p.monthlyPaise ? ` or ${inr(p.monthlyPaise)} a month` : "") +
      ` (${p.visitsPerYear} care-manager visits a year)`,
  ).join("\n");
  const assessment = HOME_ASSESSMENT.pricePaise ? inr(HOME_ASSESSMENT.pricePaise) : "free";
  const text = `# KushAlaya

> KushAlaya is elder care at home in India. We make parents' homes safer (home safety assessment, fall-prevention fixes) and send Family Partners on regular visits, with photo reports and alerts for their families, including families living abroad (NRI).

## Who it is for
- Adult children, in India or abroad, whose parents live at home in India.
- Older adults who want to stay safe and independent at home.

## Where
- Families across India. Registered office in Hyderabad, Telangana.

## How it starts
- KushCare Discovery: a short enquiry form. A Family Partner then calls and books the home safety assessment (${assessment}). ${o}/kushcare-discovery

## Plans (GST included; monthly billing costs more than annual)
${plans}
- ${SINGLE_VISIT.name}: ${inr(SINGLE_VISIT.pricePaise)} + ${inr(SINGLE_VISIT.registrationPaise)} registration (${SINGLE_VISIT.hours} hours, no subscription)
- Details: ${o}/packages

KushAlaya is not an emergency service. In an emergency in India call 112 or 108 first. An SOS watch (Privilege and Signature plans) alerts the client's Family Partner, who checks and then informs the family.

## Key pages
- Home: ${o}/
- Plans and prices: ${o}/packages
- KushLife care visits: ${o}/kushlife
- FAQ: ${o}/faq
${SEO_SERVICES.map((s) => `- ${s.label}: ${o}/services/${s.slug}`).join("\n")}
${SEO_CITIES.map((c) => `- Elder care in ${c.name}: ${o}/elder-care/${c.slug}`).join("\n")}
- About: ${o}/about
- Contact: ${o}/contact

## Contact
- ${LEGAL_ENTITY_NAME} (CIN ${COMPANY_CIN}, GSTIN ${COMPANY_GSTIN})
- ${REGISTERED_ADDRESS}
- Phone: ${PUBLIC_PHONE.display}
- Email: ${PUBLIC_EMAIL}
`;
  return new Response(text, {
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "public, max-age=3600" },
  });
}
