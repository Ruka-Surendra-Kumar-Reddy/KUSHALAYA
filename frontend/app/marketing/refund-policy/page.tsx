import type { Metadata } from "next";
import { seoMetadata } from "@/lib/marketing/seo-common";
import { COMPANY_CIN, COMPANY_GSTIN, REGISTERED_ADDRESS } from "@/lib/public-brand";
import { LEGAL_ENTITY_NAME, LegalPage, Mail, brand } from "../_legal/LegalPage";

const B = brand();
const title = `Refund & Cancellation Policy | ${B}`;
const description = `How cancellations and refunds work at ${B}: quotes, orders, service requests, assessments, care visits and the prepaid wallet.`;
const url = "https://www.kushalaya.com/refund-policy";

export const metadata: Metadata = seoMetadata("/refund-policy", title, description);

export default function RefundPolicyPage() {
  return (
    <LegalPage title="Refund & Cancellation Policy">
      <div className="lg-summary">
        <p><strong>In short:</strong></p>
        <ul>
          <li>Most payments are made from your prepaid {B} wallet.</li>
          <li>If something you paid for is cancelled, the full amount goes back to your wallet.</li>
          <li>You can ask for unused wallet money to be returned to your original payment method.</li>
          <li>Every refund gets a GST credit note in the family portal.</li>
        </ul>
      </div>

      <p>
        This policy is part of our <a href="/terms">Terms of Service</a>. It applies to services provided by{" "}
        {LEGAL_ENTITY_NAME} (CIN {COMPANY_CIN}, GSTIN {COMPANY_GSTIN}), {REGISTERED_ADDRESS}. All amounts are in Indian rupees.
      </p>

      <h2>1. How payments work</h2>
      <ul>
        <li>You add money to your {B} wallet in the family portal, through Razorpay.</li>
        <li>Your wallet is credited only after Razorpay confirms the payment.</li>
        <li>Orders, quotes and service requests are then paid from the wallet.</li>
        <li>The KushCare Discovery and the home assessment that follows are free; there is nothing to pay.</li>
      </ul>

      <h2>2. Failed or duplicate payments</h2>
      <ul>
        <li>If a payment fails, your wallet is not credited.</li>
        <li>
          If money left your account but the wallet was not credited, it is usually returned to you by your bank or
          Razorpay automatically. If it is not, email <Mail /> with the payment reference and we will help.
        </li>
        <li>If you were charged twice for the same top-up, tell us and we will return the extra amount.</li>
      </ul>

      <h2>3. Quotes and product orders</h2>
      <ul>
        <li>You can decline a quote in the family portal. Nothing is charged.</li>
        <li>
          If a paid order is cancelled before the installation is done, the full amount you paid is returned to your
          wallet, and you get a credit note.
        </li>
        <li>
          To cancel a booked installation, contact us as early as you can. Once the installer is on the way or on site,
          please call us first.
        </li>
        <li>Any coupon used on a cancelled unpaid order can be used again.</li>
        <li>
          Once products are installed, the order is complete. We cannot take back products that have been fixed to
          walls or floors. If a product is faulty or the work is not right, tell us within 7 days and we will repair or
          replace it, or refund it to your wallet.
        </li>
      </ul>

      <h2>4. Care visits and service requests</h2>
      <ul>
        <li>
          You can cancel a requested or confirmed service in the family portal. If you already paid for it, the full
          amount goes back to your wallet.
        </li>
        <li>Any visit booked for that request is cancelled too, and the caregiver is told.</li>
        <li>
          Please cancel at least 24 hours before a visit. A visit cancelled after the caregiver has arrived may be
          charged.
        </li>
        <li>If we have to cancel a visit and cannot offer another time, we return the amount to your wallet.</li>
      </ul>

      <h2>5. KushCare Discovery assessments</h2>
      <ul>
        <li>The KushCare Discovery and the home assessment visit are free, so there is no fee to refund.</li>
        <li>You can cancel or move an assessment at any time; please tell us 24 hours ahead if you can.</li>
        <li>If we cancel, we offer a new time of your choice.</li>
      </ul>

      <h2>6. Unused wallet balance</h2>
      <ul>
        <li>Wallet money can only be used for {B} services. It does not earn interest.</li>
        <li>
          You can ask for unused balance to be returned at any time, including when you close your account. Email{" "}
          <Mail />. We send it back to the original payment method, less any amount owed for services already
          delivered.
        </li>
      </ul>

      <h2>7. How long refunds take</h2>
      <ul>
        <li>Refunds to your wallet happen straight away, when the cancellation is made.</li>
        <li>
          Refunds to your bank account or card are sent within 7 working days of approval. Your bank may take a few more
          days to show it.
        </li>
        <li>For families paying from abroad, the amount returned is in rupees. Your bank may convert it at its own rate.</li>
      </ul>

      <h2>8. Invoices and credit notes</h2>
      <p>
        We issue a GST tax invoice for each payment for an order or service. When that payment is refunded, we issue a
        credit note against the invoice. You can see both in the family portal. Wallet top-ups get a receipt, not a tax
        invoice.
      </p>

      <h2>9. Questions</h2>
      <p>
        Email <Mail /> with your registered phone number or email and the order or receipt number. We will reply as soon
        as we can.
      </p>
    </LegalPage>
  );
}
