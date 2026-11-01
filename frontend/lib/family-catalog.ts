/** Family Requests page: group the ops catalog into a few plain shelves, and search it. */
import type { FamilyProduct } from "@/lib/family-money";

export type Shelf = { id: string; label: string };

export const SHELVES: Shelf[] = [
  { id: "safety", label: "Home safety products" },
  { id: "mobility", label: "Mobility aids" },
  { id: "alerts", label: "Smart home & alerts" },
  { id: "health", label: "Health devices" },
  { id: "care", label: "Care at home" },
  { id: "clinical", label: "Nursing & doctor" },
  { id: "maintenance", label: "Home maintenance" },
  { id: "transport", label: "Transport & errands" },
  { id: "other", label: "More" },
];

/** Which shelf a catalog category sits on (categories are the ops Products categories). */
export function shelfFor(category: string): string {
  const c = category.toLowerCase();
  if (/bath|bed|living|entry|exterior|hallway|kitchen|balcony|stair/.test(c)) return "safety";
  if (/mobility/.test(c)) return "mobility";
  if (/smart|emergency|wearable/.test(c)) return "alerts";
  if (/health/.test(c)) return "health";
  if (/nurs|physio|doctor|diagnos/.test(c)) return "clinical";
  if (/maintenance|property/.test(c)) return "maintenance";
  if (/transport|errand/.test(c)) return "transport";
  if (/service|care|wellness/.test(c)) return "care";
  return "other";
}

/** "₹3,658 incl. GST · per visit", or "We'll quote after a visit" when ops has not priced it yet. */
export function familyPriceLabel(p: Pick<FamilyProduct, "price_with_gst_paise" | "unit">): string {
  if (!p.price_with_gst_paise) return "We'll quote after a visit";
  const rupees = `₹${Math.round(p.price_with_gst_paise / 100).toLocaleString("en-IN")} incl. GST`;
  return p.unit ? `${rupees} · ${p.unit}` : rupees;
}

/** Every word typed must appear in the name, description, category or code. */
export function matchesSearch(p: FamilyProduct, query: string): boolean {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return true;
  const hay = `${p.name} ${p.description} ${p.category} ${p.product_code}`.toLowerCase();
  return words.every((w) => hay.includes(w));
}

/** Shelves that have at least one item, in SHELVES order. */
export function shelvesWithItems(items: FamilyProduct[]): Shelf[] {
  const used = new Set(items.map((p) => shelfFor(p.category)));
  return SHELVES.filter((s) => used.has(s.id));
}

/**
 * Product ↔ finding map for families. The server matches products to findings
 * by keyword ("bed" in "Bedroom night lighting" picked the bed rail), so the
 * family pages check each pairing here: a product with a rule only keeps the
 * findings it really fixes, and a finding left without a product gets the
 * catalog items whose rule fits it (a night light for a dark bedroom).
 * Order matters: the first rule whose `product` matches is used.
 */
export const PRODUCT_FINDING_RULES: { product: RegExp; fixes: RegExp }[] = [
  // Outside lights light the way in, not a dark bedroom (checked before the night-light rule).
  { product: /outdoor|solar|security light|porch light/i, fixes: /entr(?:y|ance)|outdoor|outside|porch|gate|garden/i },
  { product: /night ?light|motion.*light|sensor.*light|led strip|light(?:ing)? kit|torch|flashlight/i, fixes: /light|dark|night|lamp/i },
  { product: /contact card|emergency (?:contact|info)|fridge card|medical id/i, fixes: /emergency contact|contacts? (?:posted|displayed)|doctor information|medication list/i },
  { product: /sos|panic|alert (?:button|pendant)|fall (?:alert|detect)|wearable/i, fixes: /sos|alert|alarm|call for help|phone for emergencies|emergency (?:contact|button|bell)|fall|alone/i },
  { product: /pull ?cord|call bell|emergency bell/i, fixes: /sos|alert|alarm|call for help|emergency (?:button|bell)|pull cord/i },
  { product: /bed ?rail|bed (?:assist|handle|lever)/i, fixes: /\bbed\b(?! ?room)|bed transfer|bed\/chair|transfers? bed/i },
  { product: /l[- ]?shaped grab/i, fixes: /shower|bath/i },
  { product: /toilet (?:rail|frame|safety)|raised toilet|commode/i, fixes: /toilet/i },
  { product: /grab ?(?:bar|rail)/i, fixes: /grab|toilet|shower|bath/i },
  { product: /shower (?:chair|stool|seat)|bath (?:seat|bench|stool)/i, fixes: /shower|bath/i },
  { product: /anti-?slip|non-?slip|bath ?mat|floor (?:treatment|coating)|slip/i, fixes: /slip|floor|wet/i },
  { product: /smoke|co detector|gas (?:alarm|detector)/i, fixes: /smoke|detector|gas/i },
];

function ruleFor(name: string) {
  return PRODUCT_FINDING_RULES.find((r) => r.product.test(name)) ?? null;
}

/** Does this product fix this finding? Products without a rule are trusted as they are. */
export function productFixesFinding(productName: string, finding: string): boolean {
  const rule = ruleFor(productName);
  return rule ? rule.fixes.test(finding) : true;
}

type Matchable = { id: number; name: string; reasons: string[] };

/**
 * Re-checks the server's product → finding pairs against the map: drops
 * findings a product doesn't fix, then gives every flagged finding left
 * without a product the catalog items that fit it. Returns product id →
 * reasons (only recommended ones).
 */
export function alignRecommendations(
  recommended: Matchable[],
  catalog: { id: number; name: string }[],
  perFinding = 2,
  /** Findings to cover even when the server paired no product with them (the urgent ones). */
  extraFindings: string[] = [],
): Map<number, string[]> {
  const out = new Map<number, string[]>();
  const flagged: string[] = [];
  for (const p of recommended) {
    for (const r of p.reasons) if (!flagged.includes(r)) flagged.push(r);
    const kept = p.reasons.filter((r) => productFixesFinding(p.name, r));
    if (kept.length) out.set(p.id, kept);
  }
  for (const f of extraFindings) if (f && !flagged.includes(f)) flagged.push(f);
  const covered = new Set([...out.values()].flat());
  for (const finding of flagged) {
    if (covered.has(finding)) continue;
    let added = 0;
    for (const c of catalog) {
      if (added >= perFinding) break;
      const rule = ruleFor(c.name);
      if (!rule || !rule.fixes.test(finding)) continue;
      out.set(c.id, [...(out.get(c.id) ?? []), finding]);
      added += 1;
    }
  }
  return out;
}

export type SuggestionItem = {
  product_id: number;
  name: string;
  priority: "high" | "medium";
  price_with_gst_paise: number | null;
  reasons: string[];
};

/** /suggestions items re-checked by alignRecommendations (same pairs as the Requests page). */
export function alignSuggestionItems(
  items: SuggestionItem[],
  catalog: Pick<FamilyProduct, "id" | "name" | "kind" | "price_with_gst_paise">[],
  /** Urgent finding labels: each gets a product when the catalog has one (smoke alarm → smoke detector). */
  urgentFindings: string[] = [],
): SuggestionItem[] {
  const products = catalog.filter((c) => c.kind === "product");
  const map = alignRecommendations(
    items.map((i) => ({ id: i.product_id, name: i.name, reasons: i.reasons })),
    products,
    2,
    urgentFindings,
  );
  const out: SuggestionItem[] = [];
  for (const [id, reasons] of map) {
    const s = items.find((i) => i.product_id === id);
    const c = products.find((p) => p.id === id);
    if (!s && !c) continue;
    out.push({
      product_id: id,
      name: s?.name ?? c!.name,
      priority: s?.priority ?? (reasons.some((r) => urgentFindings.includes(r)) ? "high" : "medium"),
      price_with_gst_paise: s ? s.price_with_gst_paise : c!.price_with_gst_paise || null,
      reasons,
    });
  }
  return out;
}

/** Family catalog with `recommended` / `reasons` re-checked by alignRecommendations. */
export function withAlignedRecommendations<T extends FamilyProduct>(products: T[]): T[] {
  const map = alignRecommendations(
    products.filter((p) => p.recommended),
    products.filter((p) => p.kind === "product"),
  );
  return products.map((p) => ({ ...p, recommended: map.has(p.id), reasons: map.get(p.id) ?? [] }));
}
