import type { Metadata } from "next";
import { seoMetadata } from "@/lib/marketing/seo-common";
import { COMPANY_CIN, COMPANY_GSTIN, REGISTERED_ADDRESS } from "@/lib/public-brand";
import { LEGAL_ENTITY_NAME, LegalPage, Mail, Todo, brand } from "../_legal/LegalPage";

const B = brand();
const title = `Terms of Service | ${B}`;
const description = `The terms for using ${B}: home safety assessments, safety products, KushLife care visits, the family portal, wallet and payments.`;
const url = "https://www.kushalaya.com/terms";

export const metadata: Metadata = seoMetadata("/terms", title, description);

export default function TermsPage() {
  return (
    <LegalPage title="Terms of Service">
      <div className="lg-summary">
        <p>
          These terms are an agreement between you and {LEGAL_ENTITY_NAME} (&ldquo;{B}&rdquo;, &ldquo;we&rdquo;,
          &ldquo;us&rdquo;). By booking a service, creating an account or using the family portal, you agree to them.
          Please also read our <a href="/privacy">Privacy Policy</a> and{" "}
          <a href="/refund-policy">Refund &amp; Cancellation Policy</a>.
        </p>
      </div>

      <h2>1. About us</h2>
      <ul>
        <li>Company: {LEGAL_ENTITY_NAME}</li>
        <li>Registered office: {REGISTERED_ADDRESS}</li>
        <li>CIN: {COMPANY_CIN}</li>
        <li>GSTIN: {COMPANY_GSTIN}</li>
        <li>Email: <Mail /></li>
      </ul>

      <h2>2. Our services</h2>
      <p>We serve families across India, including families who live abroad and arrange care for parents in India.</p>
      <ul>
        <li>
          <strong>KushCare Discovery:</strong> a home safety assessment at your family member&rsquo;s home.
        </li>
        <li>
          <strong>{B} Safety Score report:</strong> what we found, how serious it is, and what we recommend.
        </li>
        <li><strong>Home safety products and installation</strong>, such as grab bars, lighting and alarms.</li>
        <li>
          <strong>KushLife care visits:</strong> visits by trained caregivers, with a wellbeing check at every visit.
        </li>
        <li>
          <strong>Family portal</strong> (family.kushalaya.com): visit updates, documents, messages, wallet, invoices
          and SOS alerts.
        </li>
        <li><strong>Optional wearables and sensors</strong> that can raise alerts.</li>
      </ul>
      <p>
        What is included in a particular service, and its price, is what we show you when you book or in the quote
        you accept.
      </p>

      <h2>3. Your account</h2>
      <ul>
        <li>You must be 18 or older to create an account or book a service.</li>
        <li>Give us accurate details, and keep them up to date.</li>
        <li>Keep your sign-in details private. You are responsible for what happens in your account.</li>
        <li>
          If you book for a parent or relative, you confirm you are allowed to share their details with us and to
          give consent for them.
        </li>
      </ul>

      <h2>4. Assessments and reports</h2>
      <ul>
        <li>The KushCare Discovery and the home assessment are free.</li>
        <li>
          The Safety Score report reflects what our team saw on the day of the visit. It is advice to reduce risk. It
          is not a guarantee that no accident will happen.
        </li>
        <li>
          We may use AI to help spot hazards in photos and to show a preview of a room with products fitted. A care
          manager reviews AI results. Previews are illustrations. The finished installation may look different.
        </li>
      </ul>

      <h2>5. Quotes, orders and installation</h2>
      <ul>
        <li>We send product and installation work as a quote in the family portal.</li>
        <li>You accept and pay for a quote in the portal. We then book the installation and tell you the date.</li>
        <li>Prices are in Indian rupees and include GST, as shown on the quote.</li>
        <li>
          Someone needs to give our installer access to the home at the booked time. Please tell us before the visit
          about anything that affects the work, such as walls we must not drill.
        </li>
        <li>
          Product warranties are as given by the manufacturer. <Todo>Workmanship warranty on installation, if any</Todo>
        </li>
      </ul>

      <h2>6. Care visits</h2>
      <ul>
        <li>We schedule visits as agreed with you, and assign suitable caregivers.</li>
        <li>
          Our caregivers provide non-medical support and wellbeing checks. They are not doctors, and a visit is not
          medical treatment or advice.
        </li>
        <li>
          Caregivers may need to change at times. We will tell you, and we try to keep the same caregiver where we
          can.
        </li>
        <li>Please treat our caregivers with respect. We may stop a visit if a caregiver is unsafe.</li>
      </ul>

      <h2>7. SOS and emergencies</h2>
      <p>
        <strong>{B} is not an emergency service.</strong> In an emergency, call 112 (or the local ambulance or police)
        first.
      </p>
      <ul>
        <li>
          SOS alerts, wearables and sensors depend on power, phone networks and the internet. They can fail or be
          delayed.
        </li>
        <li>When we receive an alert, we will try to reach your family member, you and the emergency contacts you gave us.</li>
        <li>We do not promise any particular response time unless your plan says so in writing.</li>
      </ul>

      <h2>8. Wallet and payments</h2>
      <ul>
        <li>
          The family portal has a prepaid {B} wallet. You add money to it through Razorpay, using the payment methods
          Razorpay offers.
        </li>
        <li>Orders and services are paid from the wallet balance. Some bookings can be paid directly at checkout.</li>
        <li>
          Money is credited to your wallet only after the payment is confirmed by Razorpay. If a payment fails, the
          wallet is not credited.
        </li>
        <li>
          We issue a GST tax invoice for each payment for an order or service, and a credit note for each refund. A
          wallet top-up gets a receipt, not a tax invoice, because it is not a sale.
        </li>
        <li>The wallet is not a bank account and earns no interest. It can only be used for {B} services.</li>
        <li>
          Refunds and cancellations follow our <a href="/refund-policy">Refund &amp; Cancellation Policy</a>.
        </li>
      </ul>

      <h2>9. Acceptable use</h2>
      <p>Do not misuse the website or portal. For example, do not:</p>
      <ul>
        <li>give false information or use someone else&rsquo;s account;</li>
        <li>raise false SOS alerts on purpose;</li>
        <li>try to break, overload or get around the security of our systems;</li>
        <li>upload anything unlawful, or anything you do not have the right to share.</li>
      </ul>

      <h2>10. Our content</h2>
      <p>
        The website, apps, reports and brand belong to {LEGAL_ENTITY_NAME}. You may use your reports for your own
        family&rsquo;s needs. Please do not copy or resell our content.
      </p>

      <h2>11. Liability</h2>
      <ul>
        <li>We provide our services with reasonable skill and care.</li>
        <li>
          We cannot guarantee that a fall, injury or other harm will never happen. Our assessments, products and
          visits reduce risk. They do not remove it.
        </li>
        <li>
          We are not responsible for delays or failures caused by events outside our reasonable control, such as
          network outages, power cuts, natural events or strikes.
        </li>
        <li>
          To the extent the law allows, our total liability for any claim is limited to the amount you paid us for the
          service the claim is about.
        </li>
        <li>Nothing in these terms limits any right you have under Indian consumer protection law.</li>
      </ul>

      <h2>12. Ending the service</h2>
      <ul>
        <li>You can stop using the service at any time. To close your account, use the family portal or email us.</li>
        <li>We may suspend or close an account that breaks these terms, after telling you why where we can.</li>
        <li>Wallet balance and refunds on closing are covered in the Refund &amp; Cancellation Policy.</li>
      </ul>

      <h2>13. Changes to these terms</h2>
      <p>
        We may update these terms. We will show the new date at the top, and tell you in the family portal about
        important changes. If you keep using the service after a change, the new terms apply.
      </p>

      <h2>14. Law and disputes</h2>
      <ul>
        <li>These terms are governed by the laws of India.</li>
        <li>Please contact us first at <Mail />. Most problems can be sorted out quickly.</li>
        <li>
          If we cannot resolve it, the courts at <Todo>City for jurisdiction</Todo> will have jurisdiction, subject to
          your rights under consumer protection law.
        </li>
      </ul>

      <h2>15. Contact</h2>
      <p>
        {LEGAL_ENTITY_NAME}, {REGISTERED_ADDRESS}. Email: <Mail />.
      </p>
    </LegalPage>
  );
}
