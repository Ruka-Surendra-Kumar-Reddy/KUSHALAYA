/**
 * The template editor works in plain words: sections (a title + text) and details
 * shown as [Vendor company]. Storage stays the same: "# Heading" lines and {keys}.
 */

export type Section = { heading: string; text: string };

/** Short, everyday names for the details that are filled in when a contract is sent. */
export const DETAIL_LABEL: Record<string, string> = {
  company_name: "Our company name",
  company_address: "Our address",
  company_gstin: "Our GSTIN",
  date: "Today's date",
  start_date: "Start date",
  end_date: "End date",
  signer_name: "Signer's name",
  client_name: "Client name",
  client_address: "Client address",
  client_phone: "Client phone",
  plan_name: "Plan name",
  plan_amount: "Plan amount",
  vendor_name: "Vendor contact name",
  vendor_company: "Vendor company",
  vendor_address: "Vendor address",
  vendor_gstin: "Vendor GSTIN",
  vendor_phone: "Vendor phone",
  vendor_services: "Vendor services",
  vendor_fee: "Vendor fee",
};

export function detailLabel(key: string): string {
  return DETAIL_LABEL[key] || key.replace(/_/g, " ");
}

/** {vendor_company} -> [Vendor company] */
export function toFriendly(text: string, known: Set<string>): string {
  return text.replace(/\{([a-z_]+)\}/g, (m, key: string) => (known.has(key) ? `[${detailLabel(key)}]` : m));
}

/** [Vendor company] (any case) -> {vendor_company}; unknown [brackets] stay as typed. */
export function fromFriendly(text: string, known: Set<string>): string {
  const byLabel = new Map<string, string>();
  for (const key of known) byLabel.set(detailLabel(key).toLowerCase(), key);
  return text.replace(/\[([^\]\n]{1,60})\]/g, (m, label: string) => {
    const key = byLabel.get(label.trim().toLowerCase());
    return key ? `{${key}}` : m;
  });
}

/** Stored body -> sections. Text before the first heading becomes an untitled section. */
export function toSections(body: string): Section[] {
  const blocks = body
    .replace(/\r\n/g, "\n")
    .split(/\n\s*\n/)
    .map((b) => b.trim())
    .filter(Boolean);
  const out: Section[] = [];
  for (const block of blocks) {
    if (block.startsWith("#")) {
      const [first, ...rest] = block.split("\n");
      out.push({ heading: first.replace(/^#+\s*/, ""), text: rest.join("\n").trim() });
    } else if (out.length) {
      const cur = out[out.length - 1];
      cur.text = cur.text ? `${cur.text}\n\n${block}` : block;
    } else {
      out.push({ heading: "", text: block });
    }
  }
  return out.length ? out : [{ heading: "", text: "" }];
}

/** Sections -> stored body ("# Heading" line, blank line between paragraphs). */
export function fromSections(sections: Section[]): string {
  return sections
    .map((s) => {
      const heading = s.heading.replace(/\n/g, " ").trim();
      const text = s.text.replace(/\r\n/g, "\n").trim();
      if (!heading && !text) return "";
      return heading ? (text ? `# ${heading}\n\n${text}` : `# ${heading}`) : text;
    })
    .filter(Boolean)
    .join("\n\n");
}
