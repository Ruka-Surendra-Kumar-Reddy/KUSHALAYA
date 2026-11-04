import type { Metadata } from "next";
import { seoMetadata } from "@/lib/marketing/seo-common";
import { LEGAL_ENTITY_NAME, LegalPage, Mail, brand } from "../_legal/LegalPage";

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

      <h2>Data summary for our apps</h2>
      <p>
        This policy applies to the website <strong>www.kushalaya.com</strong>, the web portals{" "}
        <strong>family.kushalaya.com</strong> and <strong>ops.kushalaya.com</strong>, and the Android apps{" "}
        <strong>KushAlaya Family</strong> (for families) and <strong>KushAlaya Ops</strong> (for our care staff).
        The same company, {LEGAL_ENTITY_NAME}, operates all of them. In every one of them:
      </p>
      <div className="lg-table-wrap">
        <table className="lg-table">
          <thead>
            <tr><th>Data</th><th>Collected</th><th>Why</th><th>Shared with</th></tr>
          </thead>
          <tbody>
            <tr><td>Name, email, phone</td><td>When you sign up, enquire or are added by a family member</td><td>Create and secure your account, contact you about care</td><td>Our care team; email/SMS/WhatsApp providers to deliver messages</td></tr>
            <tr><td>Care recipient details (name, age, address, emergency contacts)</td><td>Entered by the family or our staff</td><td>Plan and deliver visits</td><td>Assigned care manager and caregivers; installation partners when fitting products</td></tr>
            <tr><td>Health and wellbeing notes</td><td>Only with separate consent</td><td>Safe care at each visit</td><td>Assigned care team only</td></tr>
            <tr><td>Photos, voice notes, documents</td><td>When you or our staff upload them</td><td>Visit evidence, assessment reports</td><td>Room photos only: Google Gemini / fal.ai for hazard checks and previews (no names)</td></tr>
            <tr><td>Precise location</td><td>Staff app during a visit; family app only if you share it</td><td>Confirm the visit happened at the home; on-the-way map</td><td>Not shared outside the care team</td></tr>
            <tr><td>Payments</td><td>Wallet top-ups and purchases</td><td>Billing, GST invoices</td><td>Razorpay processes the payment; we keep invoice records</td></tr>
            <tr><td>Device token for push notifications</td><td>If you allow notifications in the Android apps</td><td>Visit updates, SOS alerts</td><td>Google Firebase Cloud Messaging delivers the notification</td></tr>
            <tr><td>Usage and diagnostics</td><td>Sign-in events, errors</td><td>Security, support</td><td>Nobody</td></tr>
          </tbody>
        </table>
      </div>
      <p>
        We do not sell personal data and do not show advertising. If you choose &ldquo;Sign in with Google&rdquo;, we
        receive only your name, email address and profile photo (see section 6). Data is encrypted in transit; access is limited to the staff assigned to you. You can
        delete your account and data at any time (see <a href="#delete">How to delete your data</a>) or email{" "}
        <Mail />.
      </p>

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
        <li>Registered office: Uppal, Rangareddy district, Hyderabad, Telangana 500039, India</li>
        <li>Corporate Identity Number (CIN): U88100TS2026PTC224774</li>
        <li>Email: <Mail /></li>
      </ul>
      <p>
        This policy covers our website (www.kushalaya.com), the family portal (family.kushalaya.com), the staff
        portal (ops.kushalaya.com), our Android apps <strong>KushAlaya Family</strong> and{" "}
        <strong>KushAlaya Ops</strong>, and our services.
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

      <h2>6. Our apps and Google services</h2>
      <p>
        We do <strong>not</strong> access your Google contacts, calendar, Gmail or Drive. The Google services we use
        are:
      </p>
      <ul>
        <li>
          <strong>Sign in with Google</strong> (optional) on family.kushalaya.com and ops.kushalaya.com. If you choose
          it, Google shares only your <strong>name, email address and profile photo</strong> with us (the
          &ldquo;openid&rdquo;, &ldquo;email&rdquo; and &ldquo;profile&rdquo; permissions). We use them only to sign
          you in to the KushAlaya account that already has that email address, and to show your name in the portal.
          We do not ask for any other Google data, we do not use it for advertising, we do not sell it or share it
          with anyone, and we do not use it to train AI models. Our use of information received from Google APIs
          adheres to the{" "}
          <a href="https://developers.google.com/terms/api-services-user-data-policy" target="_blank" rel="noreferrer">
            Google API Services User Data Policy
          </a>
          , including the Limited Use requirements. You can stop it at any time by removing KushAlaya from your Google
          account&rsquo;s{" "}
          <a href="https://myaccount.google.com/connections" target="_blank" rel="noreferrer">
            third-party connections
          </a>
          ; you can still sign in with your email and password.
          <br />
          <strong>How we store and delete Google user data:</strong> we keep only your Google email address, name and
          a link to your profile photo, stored with your KushAlaya account on our secure cloud servers, encrypted in
          transit and limited to the staff who look after your family. We do not keep Google passwords or access
          tokens after you are signed in. This data is deleted when you delete your KushAlaya account or ask us to
          (email <Mail />) &mdash; within 30 days &mdash; and it is never transferred to anyone else.
        </li>
        <li>
          <strong>Firebase Cloud Messaging</strong> (push notifications) in the KushAlaya Family and KushAlaya Ops
          Android apps. When you allow notifications, the app registers a device token with us so we can send visit
          updates, SOS alerts and reminders. The token identifies the device, not you by name. Turning notifications
          off in Android or deleting your account removes it.
        </li>
        <li>
          <strong>Gemini</strong> (AI photo analysis) as described in section 5: room photos only, with location data
          removed, never names or health information.
        </li>
        <li>
          <strong>Google Forms</strong>, embedded on our Parent Care Check page. What you type into that form is
          collected by Google Forms into our account under Google&rsquo;s own privacy policy.
        </li>
      </ul>
      <p>
        The Android apps also ask for <strong>location</strong> (caregiver check-in at the home and the on-the-way
        map, section 3), <strong>camera and photos</strong> (visit and assessment photos) and{" "}
        <strong>microphone</strong> (optional voice notes). Each permission is requested when first needed and can be
        withdrawn in Android settings.
      </p>

      <h2>7. Who we share it with</h2>
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
        <strong>Where your data is stored:</strong> our servers and database run on Oracle Cloud Infrastructure in the
        US East (Ashburn) region, with encrypted backups on the same servers. Razorpay processes payments in India.
        Google (Gemini, Firebase) and fal.ai process the specific items described in this policy on their own
        infrastructure, which may be outside India. Where data leaves India we rely on the DPDP Act and any rules the
        Government of India makes on transfers.
      </p>

      <h2>8. How long we keep it</h2>
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
      <h3 id="delete">How to delete your data</h3>
      <ul>
        <li>
          <strong>Family portal / KushAlaya Family app:</strong> open <em>More &rarr; Privacy &rarr; Delete my
          account</em>. We confirm the request and erase or anonymise your data within 30 days.
        </li>
        <li>
          <strong>By email:</strong> write to <Mail /> from the address you signed up with, with the subject
          &ldquo;Delete my data&rdquo;.
        </li>
        <li>
          <strong>Staff and caregivers:</strong> ask your agency administrator, or email us; the account is deactivated
          at once and personal data erased on the same 30-day timeline.
        </li>
      </ul>
      <p>
        Deleting your account removes your login, contact details, documents, photos, messages and device tokens.
        Invoices and payment records are kept for the 8-year statutory period with names and contact details removed.
      </p>

      <h2>9. Your rights</h2>
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

      <h2>10. Security</h2>
      <p>
        We use reasonable security safeguards, including encrypted connections, sign-in controls and access limited to
        the people who need it. Every consent, data download and delete request is logged. No system is perfectly
        secure. If a breach affects your data, we will tell you and the Data Protection Board of India as the law
        requires.
      </p>

      <h2>11. Children</h2>
      <p>
        Our service is for adults. We do not knowingly collect data from children, except where a child&rsquo;s
        details appear in a family member&rsquo;s records.
      </p>

      <h2>12. Cookies</h2>
      <p>
        We use the cookies and browser storage needed to keep you signed in and to make the site work. We do not use
        advertising cookies.
      </p>

      <h2>13. Grievance Officer</h2>
      <p>For any question, complaint or request about your personal data, contact:</p>
      <ul>
        <li>Grievance Officer, {LEGAL_ENTITY_NAME}</li>
        <li>Name: Krish Posa (Founder)</li>
        <li>Phone: +91 905 905 1085</li>
        <li>Email: <Mail /></li>
        <li>Address: Uppal, Rangareddy district, Hyderabad, Telangana 500039, India</li>
      </ul>
      <p>
        We aim to reply within 30 days. If you are not satisfied with our answer, you may complain to the Data
        Protection Board of India.
      </p>

      <h2>14. Changes to this policy</h2>
      <p>
        We may update this policy. If a change affects what you agreed to, we will ask for your consent again in the
        family portal. The date at the top shows the latest version.
      </p>
    </LegalPage>
  );
}
