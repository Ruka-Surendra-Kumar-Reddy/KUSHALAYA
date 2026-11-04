/**
 * Founder details shown on the public site (www.kushalaya.com). One place so
 * the phone and email never drift between the home page and the vision sheet.
 *
 * The founder asked to be reachable directly — this is a deliberate public
 * contact, not a leak.
 */
export const FOUNDER = {
  name: "Krish Posa",
  role: "Founder, KushAlaya",
  phoneDisplay: "+91 905 905 1085",
  phoneTel: "tel:+919059051085",
  email: "contact@kushalaya.com",
  /** 4:5 portrait, 900×1125 (a 450-wide copy exists for small screens). */
  photo: "/marketing/founder/krish-posa.webp",
  photoSmall: "/marketing/founder/krish-posa-450.webp",
  photoAlt: "Krish Posa, founder of KushAlaya",
  /** The line the vision hangs on — also used as the section heading. */
  tagline: "Home is more than a place. It’s where comfort and dignity live.",
  statement: [
    "I’m Krish Posa, founder of KushAlaya. I want us to act before something goes wrong — not only after.",
    "I want to help prevent falls and give every older adult the support and tools to live independently, with dignity, in the comfort of their own home.",
  ],
  invite: "Call me directly for any input, question or idea. I read every message myself.",
} as const;

export function founderMailtoHref(): string {
  return `mailto:${FOUNDER.email}`;
}

/** WhatsApp link to the founder, optionally with a prefilled first message. */
export function founderWhatsAppHref(prefill?: string): string {
  const base = `https://wa.me/${FOUNDER.phoneTel.replace(/\D/g, "")}`;
  return prefill ? `${base}?text=${encodeURIComponent(prefill)}` : base;
}

/**
 * KushLife — the family-facing name for what happens on every visit after the
 * assessment: we measure the "kush"ness (comfort, ease, wellbeing) of the
 * person in the home, not just the hazards in it. Four short checks, every
 * visit, so a family can see the trend and not just the incident.
 */
export const KUSHLIFE = {
  name: "KushLife",
  strap: "Every visit, we assess the “kush”ness.",
  meaning:
    "“Kush” means comfort and contentment. KushLife measures it on every visit — so care is about how your parents live, not only what went wrong.",
  checks: [
    {
      title: "Safe",
      body: "Hazards, lighting, grab bars, footwear — anything that raises fall risk since the last visit.",
    },
    {
      title: "Steady",
      body: "Walking, balance, sit-to-stand, and how confidently they move around their own home.",
    },
    {
      title: "Settled",
      body: "Sleep, meals, medicines, mood and routine — the quiet signs that daily life is going well.",
    },
    {
      title: "Connected",
      body: "What they want the family to know, and what the family asked us to look at — closed in the portal.",
    },
  ],
} as const;
