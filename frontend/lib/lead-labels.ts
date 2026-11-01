/** Plain words for enquiry (lead) fields that are stored as codes or paths. */

const KNOWN: Record<string, string> = {
  website: "Website",
  "website:care-check": "Website · KushCare Discovery",
  "website:custom-plan": "Website · custom plan",
  "website:contact": "Website · contact form",
  qr: "QR / standee",
  "qr:care-check": "QR / standee",
  home_safety_assessment: "Home safety assessment",
  referral: "Referral",
  whatsapp: "WhatsApp",
  google: "Google",
  direct: "Direct visit",
  staff: "Added by staff",
};

/** "website" → "Website", "home_safety_assessment" → "Home safety assessment". */
export function leadSourceLabel(raw: string | null | undefined): string {
  const v = (raw || "").trim();
  if (!v) return "Not recorded";
  const known = KNOWN[v.toLowerCase()];
  if (known) return known;
  const words = v.replace(/[_:-]+/g, " ").replace(/\s+/g, " ").trim().toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** "/" → "Home page"; "/blog/fall-proofing?x=1" → "Blog › Fall proofing". Full URLs keep only the path. */
export function landingPageLabel(raw: string | null | undefined): string {
  let v = (raw || "").trim();
  if (!v) return "Not recorded";
  try {
    if (/^https?:\/\//i.test(v)) v = new URL(v).pathname;
  } catch {
    /* keep as typed */
  }
  const path = v.split(/[?#]/)[0] ?? "";
  const parts = path.split("/").filter(Boolean);
  if (!parts.length) return "Home page";
  return parts
    .map((p) => {
      const w = decodeURIComponent(p).replace(/[-_]+/g, " ").trim();
      return w.charAt(0).toUpperCase() + w.slice(1);
    })
    .join(" › ");
}

/** Note lines the website writes as "Key: value"; shown in the lead details grid. */
const NOTE_KEYS = ["Services", "Visits wanted", "Products of interest", "Area", "For"];

export function splitLeadNotes(notes: string | null | undefined): { fields: [string, string][]; rest: string } {
  const fields: [string, string][] = [];
  const rest: string[] = [];
  for (const line of (notes || "").split("\n")) {
    const m = /^([A-Za-z ]+):\s*(.+)$/.exec(line.trim());
    if (m && NOTE_KEYS.includes(m[1].trim())) fields.push([m[1].trim(), m[2].trim()]);
    else rest.push(line);
  }
  return { fields, rest: rest.join("\n").trim() };
}

/** Area names that only fit Telangana PIN codes (50xxxx). */
const TELANGANA_AREAS = /\b(hyderabad|secunderabad|cyberabad|telangana|gachibowli|madhapur|kondapur|banjara|jubilee hills|kukatpally|hitec)\b/i;

/** True when a typed area cannot be where the PIN code is (e.g. "Hyderabad" with 831009, Jamshedpur). */
export function areaContradictsPin(area: string | null | undefined, pincode: string | null | undefined): boolean {
  const pin = (pincode || "").replace(/\D/g, "");
  if (pin.length !== 6 || !area) return false;
  return TELANGANA_AREAS.test(area) && !pin.startsWith("50");
}

type ClientLike = {
  id: number;
  first_name: string;
  last_name: string;
  phone?: string | null;
  emergency_contact_phone?: string | null;
  family_email?: string | null;
};

const last10 = (v: string | null | undefined) => (v || "").replace(/\D/g, "").slice(-10);

/** An enquiry from someone who is already a client: same phone (last 10 digits) or family email. */
export function matchLeadToClient<T extends ClientLike>(
  lead: { phone?: string | null; email?: string | null },
  clients: T[],
): T | null {
  const phone = last10(lead.phone);
  const email = (lead.email || "").trim().toLowerCase();
  return (
    clients.find(
      (c) =>
        (phone.length === 10 && (last10(c.phone) === phone || last10(c.emergency_contact_phone) === phone)) ||
        (!!email && (c.family_email || "").trim().toLowerCase() === email),
    ) || null
  );
}
