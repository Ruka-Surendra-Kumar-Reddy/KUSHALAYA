import type { Metadata } from "next";
import { seoMetadata } from "@/lib/marketing/seo-common";
import { LEGAL_ENTITY_NAME, LegalPage, Mail, Todo, brand } from "../_legal/LegalPage";

const B = brand();
const title = `Privacy Policy | ${B}`;
const description = `How ${B} collects, uses, shares and protects personal data, and how to use your rights under India's Digital Personal Data Protection Act, 2023.`;
const url = "https://www.kushalaya.com/privacy";

export const metadata: Metadata = seoMetadata("/privacy", title, description);

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy">
      <div className="lg-summary">
        <p><strong>In short:</strong></p>
        <ul>
          <li>We use personal data to plan, deliver and bill care for your parent or family member.</li>
          <li>Health information, visit location sharing and marketing messages are optional. Each needs your separate consent.</li>
          <li>We never sell your data.</li>
          <li>You can see, download, correct and delete your data, and withdraw consent, from the family portal or by email.</li>
        </ul>
      </div>

      <h2>1. Who we are</h2>
      <p>
        {B} is run by {LEGAL_ENTITY_NAME} (&ldquo;{B}&rdquo;, &ldquo;we&rdquo;, &ldquo;us&rdquo;). We provide home
        safety assessments, home safety products and installation, and in-home elder care visits for families
        across India, including families who live abroad and arrange care for parents in India.
      </p>
      <p>
        Under India&rsquo;s Digital Personal Data Protection Act, 2023 (&ldquo;DPDP Act&rdquo;), we are the{" "}
        <strong>Data Fiduciary</strong> for the personal data described here.
      </p>
      <ul>
        <li>Registered office: <Todo>Registered address</Todo></li>
        <li>Corporate Identity Number (CIN): <Todo>CIN</Todo></li>
        <li>Email: <Mail /></li>
      </ul>
      <p>
        This policy covers our website (www.kushalaya.com), the family portal (family.kushalaya.com), our
        caregiver and staff apps, and our services.
      </p>

      <h2>2. Whose data this covers</h2>
      <ul>
        <li><strong>Family members</strong> who sign up, book or pay for care (often a son or daughter).</li>
        <li>
          <strong>The person receiving care</strong> (your parent or relative). A family member usually gives consent
          on their behalf and records their name and relationship. Please make sure you are entitled to do so, and
          tell your parent how their data is used.
        </li>
        <li><strong>Website visitors</strong> who send an enquiry or request a call back.</li>
      </ul>

      <h2>3. What we collect</h2>
      <ul>
        <li><strong>Contact details:</strong> your name, email and phone number.</li>
        <li>
          <strong>About the person receiving care:</strong> name, age, home address, phone and emergency contacts.
        </li>
        <li>
          <strong>Health and wellbeing</strong> (only with consent): health conditions, allergies, mobility, and the
          checks a caregiver records at each visit.
        </li>
        <li>
          <strong>Visit records:</strong> visit times, caregiver notes, voice notes, photos, and incident or SOS
          reports.
        </li>
        <li>
          <strong>Home safety assessment:</strong> room photos, the hazards found, recommendations and your{" "}
          {B} Safety Score report.
        </li>
        <li>
          <strong>Location</strong> (only with consent): where the caregiver checked in at the home, and the
          caregiver&rsquo;s position while on the way to you.
        </li>
        <li><strong>Devices</strong> (only if you choose wearables or sensors): alerts and readings they send us.</li>
        <li>
          <strong>Payments:</strong> wallet top-ups, orders, invoices and receipts. Card, UPI and bank details are
          entered on Razorpay&rsquo;s checkout. We do not see or store your full card details.
        </li>
        <li><strong>Messages</strong> you send us through the portal, email, phone or WhatsApp.</li>
        <li>
          <strong>Documents</strong> you upload to the family portal.
        </li>
      </ul>

      <h2>4. Why we use it</h2>
      <div className="lg-table-wrap">
        <table className="lg-table">
          <thead>
            <tr><th>Purpose</th><th>What it means</th><th>Consent</th></tr>
          </thead>
          <tbody>
            <tr>
              <td>Care delivery</td>
              <td>Use names, phone, address and visit records to plan, deliver and bill care.</td>
              <td>Needed to use the service</td>
            </tr>
            <tr>
              <td>Health information</td>
              <td>Record health conditions, allergies, mobility and wellbeing checks so caregivers can look after your family member safely.</td>
              <td>Optional, off by default</td>
            </tr>
            <tr>
              <td>Location during visits</td>
              <td>Record where a caregiver checked in, and show you the caregiver&rsquo;s position while they are on the way.</td>
              <td>Optional, off by default</td>
            </tr>
            <tr>
              <td>News and offers</td>
              <td>Occasional news, tips and offers by email, SMS or WhatsApp.</td>
              <td>Optional, off unless you turn it on</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p>We also use personal data to:</p>
      <ul>
        <li>send you visit updates, reminders, alerts and receipts;</li>
        <li>handle SOS and emergency alerts;</li>
        <li>issue GST invoices and keep the accounts the law requires;</li>
        <li>keep the service secure and keep a record of what was agreed and done.</li>
      </ul>
      <p>
        <strong>We never sell your data.</strong> If you do not give care delivery consent, we cannot provide the
        service. To stop, you can ask us to delete your account.
      </p>

      <h2>5. AI room checks and previews</h2>
      <p>
        During a home safety assessment we may use AI to help spot hazards in room photos and to create a preview of
        how a room could look with safety products installed.
      </p>
      <ul>
        <li>
          Room photos are sent to <strong>Google&rsquo;s Gemini</strong> service for analysis. Before sending, we
          re-save the image to remove hidden details such as GPS location.
        </li>
        <li>
          Only the image, our list of hazard types, and product names are sent. We do not send names, addresses or
          health information.
        </li>
        <li>
          If Google is unavailable, a preview image may be created by fal.ai (an AI image service) under the same
          rule: only the room photo and product names are sent.
        </li>
        <li>
          AI results are a starting point only. A {B} care manager reviews them before they appear in your report.
        </li>
      </ul>

      <h2>6. Who we share it with</h2>
      <ul>
        <li>
          <strong>Our care team:</strong> care managers and the caregivers assigned to your family member. Each sees
          only what they need.
        </li>
        <li>
          <strong>Service providers</strong> who help us run the service, under contract: cloud hosting, Razorpay
          (payments), SMS, email and WhatsApp messaging, and the AI services named above.
        </li>
        <li>
          <strong>Installation partners</strong> who fit products in the home, with the details needed for the job.
        </li>
        <li>
          <strong>In an emergency</strong>, what is needed with hospitals, ambulance services or the police.
        </li>
        <li><strong>Authorities</strong>, when the law requires it.</li>
      </ul>
      <p>
        Some of these providers may store or process data outside India. Where they do, we rely on the DPDP Act and
        any rules the Government of India makes on transfers. <Todo>Hosting region / data location</Todo>
      </p>

      <h2>7. How long we keep it</h2>
      <ul>
        <li>We keep your data while you use the service.</li>
        <li>
          If you ask us to delete your account, we erase or anonymise your personal data within 30 days.
        </li>
        <li>
          Invoices, receipts, credit notes, wallet and payment records are kept for <strong>8 years</strong>, because
          tax and GST law requires it. Names and contact details on them are removed.
        </li>
        <li>
          A record of the consent you gave, and of the request itself, is kept as proof, with names removed.
        </li>
        <li>Backups roll off within 8 weeks.</li>
      </ul>

      <h2>8. Your rights</h2>
      <p>Under the DPDP Act you can:</p>
      <ul>
        <li><strong>Access</strong> your data and get a summary of how it is used. You can download it from the family portal.</li>
        <li><strong>Correct</strong> or update data that is wrong or incomplete.</li>
        <li><strong>Erase</strong> your data by asking us to delete your account.</li>
        <li>
          <strong>Withdraw consent</strong> for any optional purpose at any time. This does not affect what was done
          before you withdrew.
        </li>
        <li>
          <strong>Nominate</strong> someone to use these rights for you if you die or cannot act yourself.
        </li>
        <li><strong>Raise a grievance</strong> with our Grievance Officer (below).</li>
      </ul>
      <p>
        Use the privacy section of the family portal, or email <Mail />. We may need to confirm who you are before
        acting on a request.
      </p>

      <h2>9. Security</h2>
      <p>
        We use reasonable security safeguards, including encrypted connections, sign-in controls and access limited to
        the people who need it. Every consent, data download and delete request is logged. No system is perfectly
        secure. If a breach affects your data, we will tell you and the Data Protection Board of India as the law
        requires.
      </p>

      <h2>10. Children</h2>
      <p>
        Our service is for adults. We do not knowingly collect data from children, except where a child&rsquo;s
        details appear in a family member&rsquo;s records.
      </p>

      <h2>11. Cookies</h2>
      <p>
        We use the cookies and browser storage needed to keep you signed in and to make the site work. We do not use
        advertising cookies.
      </p>

      <h2>12. Grievance Officer</h2>
      <p>For any question, complaint or request about your personal data, contact:</p>
      <ul>
        <li>Grievance Officer, {LEGAL_ENTITY_NAME}</li>
        <li>Name: Krish Posa (Founder)</li>
        <li>Phone: +91 83095 00488</li>
        <li>Email: <Mail /></li>
        <li>Address: <Todo>Registered address</Todo></li>
      </ul>
      <p>
        We aim to reply within 30 days. If you are not satisfied with our answer, you may complain to the Data
        Protection Board of India.
      </p>

      <h2>13. Changes to this policy</h2>
      <p>
        We may update this policy. If a change affects what you agreed to, we will ask for your consent again in the
        family portal. The date at the top shows the latest version.
      </p>
    </LegalPage>
  );
}
