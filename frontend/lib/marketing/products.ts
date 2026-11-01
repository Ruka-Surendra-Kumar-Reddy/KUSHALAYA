/**
 * Safety products Kushalaya fits in Indian homes.
 *
 * Content comes from the Elder Safety Products photo guide — the same
 * selection notes assessors use — so the public page and the assessment agree
 * on what "good" looks like. Deliberately no prices here: everything is quoted
 * after the home visit, because the right product depends on the wall, the
 * user's weight and the layout.
 */

export type ProductRoom = "bathroom" | "bedroom";

export interface SafetyProduct {
  id: string;
  name: string;
  room: ProductRoom;
  image: string;
  /** What it does, in a sentence a family would say. */
  use: string;
  /** What we check before recommending it — the value we add over a shop. */
  check: string;
  /** Short badge, e.g. "Quick win" or "Needs solid wall". */
  tag?: string;
}

export const ROOM_LABEL: Record<ProductRoom, string> = {
  bathroom: "Bathroom",
  bedroom: "Bedroom",
};

export const SAFETY_PRODUCTS: SafetyProduct[] = [
  {
    id: "grab-bar",
    name: "Fixed grab bar",
    room: "bathroom",
    image: "/marketing/products/grab-bar.webp",
    use: "A solid handhold beside the toilet or at the shower entry, for steadying and standing up.",
    check:
      "Stainless steel that will not rust, a documented load rating, and fixings into solid wall — never tile alone.",
    tag: "Needs a solid wall",
  },
  {
    id: "toilet-rail",
    name: "Fold-up toilet rail",
    room: "bathroom",
    image: "/marketing/products/toilet-rail.webp",
    use: "Support for sitting down and standing up, which folds flat against the wall when it is not needed.",
    check:
      "Load rating, solid-wall anchors, the gap left beside the toilet, and that the hinge still works easily for them.",
    tag: "Needs a solid wall",
  },
  {
    id: "shower-chair",
    name: "Shower chair",
    room: "bathroom",
    image: "/marketing/products/shower-chair.webp",
    use: "Lets them bathe sitting down — the single biggest change for anyone who tires or feels unsteady standing.",
    check:
      "Height adjusts to them, drainage slots, non-slip feet, a backrest, and a weight capacity with room to spare.",
  },
  {
    id: "anti-slip-mat",
    name: "Anti-slip bath mat",
    room: "bathroom",
    image: "/marketing/products/anti-slip-mat.webp",
    use: "The fastest, cheapest way to make a smooth wet floor safer — often fitted on the day we visit.",
    check:
      "Suction cups that hold on your actual tile, and replacing it as soon as the edges curl or the grip weakens.",
    tag: "Quick win",
  },
  {
    id: "anti-slip-gel",
    name: "Anti-slip floor treatment",
    room: "bathroom",
    image: "/marketing/products/anti-slip-gel.webp",
    use: "A clear treatment for existing tiles that improves grip underfoot when the floor is wet, changing nothing visually.",
    check:
      "Tested on a small patch first for tile compatibility, then checked wet, barefoot, before we call it done.",
  },
  {
    id: "pull-cord",
    name: "Bathroom emergency pull cord",
    room: "bathroom",
    image: "/marketing/products/pull-cord.webp",
    use: "A cord they can reach after a fall — including from the floor — that calls for help when a phone is out of reach.",
    check:
      "A bathroom-rated unit, positioned to be reachable from the toilet, the shower and floor level, and priced with its receiver.",
  },
  {
    id: "bed-rail",
    name: "Adult bed rail",
    room: "bedroom",
    image: "/marketing/products/bed-rail.webp",
    use: "Something firm to hold when getting in and out of bed, and a partial barrier on the open side.",
    check:
      "Fit to the mattress and frame, and every entrapment gap measured. A rail is a handhold, never a restraint.",
  },
];

export function productsByRoom(room: ProductRoom): SafetyProduct[] {
  return SAFETY_PRODUCTS.filter((p) => p.room === room);
}

export const PRODUCT_ROOMS: ProductRoom[] = ["bathroom", "bedroom"];

/**
 * Catalog category prefixes each product belongs to, so the services section
 * can show the real items relevant to a service instead of catalog rows.
 * A service whose prefixes match nothing simply shows no products.
 */
const PREFIX_BY_ROOM: Record<ProductRoom, string[]> = {
  bathroom: ["BTH"],
  bedroom: ["BED"],
};

export function productsForPrefixes(prefixes: readonly string[]): SafetyProduct[] {
  const want = new Set(prefixes.map((p) => p.toUpperCase()));
  return SAFETY_PRODUCTS.filter((p) =>
    PREFIX_BY_ROOM[p.room].some((prefix) => want.has(prefix)),
  );
}
