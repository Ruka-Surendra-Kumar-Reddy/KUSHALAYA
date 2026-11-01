/**
 * /elder-care/<city> pages: one template (components/marketing/SeoPages.tsx),
 * one entry per city here.
 *
 * Rules (owner, Oct 2026): every city's copy must be genuinely different and
 * factual (homes, climate, where families usually live). NO local offices,
 * addresses, staff, hospital partners, response times or statistics. We work
 * with families across India and arrange visits in the city.
 */

export type SeoCity = {
  slug: string;
  name: string;
  /** Other spellings people search for. */
  alsoKnownAs?: string;
  state: string;
  /** <title>, 60 chars max. */
  metaTitle: string;
  /** Meta description, 155 chars max. */
  metaDescription: string;
  lede: string;
  homes: { intro: string; points: readonly string[] };
  climate: { intro: string; points: readonly string[] };
  family: string;
  /** What we usually look at first in homes in this city. */
  firstChecks: readonly string[];
  /** Only a slug known to exist on the blog (seeded or published). */
  blogSlug?: string;
  blogTitle?: string;
};

export const SEO_CITIES: readonly SeoCity[] = [
  {
    slug: "bengaluru",
    blogSlug: "caring-for-ageing-parents-in-bengaluru-from-abroad",
    blogTitle: "Caring for ageing parents in Bengaluru when you live abroad",
    name: "Bengaluru",
    alsoKnownAs: "Bangalore",
    state: "Karnataka",
    metaTitle: "Elder Care in Bengaluru for Ageing Parents | KushAlaya",
    metaDescription:
      "Home safety checks, fall-prevention fixes and caregiver visits for ageing parents in Bengaluru, with updates for family in India or abroad.",
    lede: "Home safety checks, fixes and regular caregiver visits for parents living in Bengaluru, with updates wherever the family lives.",
    homes: {
      intro:
        "Bengaluru has everything from large gated apartment complexes to older independent houses in established neighbourhoods, many of them built over two or three floors as the family grew.",
      points: [
        "Independent houses where the bedroom is upstairs and the stairs have no second rail",
        "Polished granite and vitrified tile floors that are slippery when wet",
        "Apartments with lifts, but steps at the entrance, balcony and bathroom",
        "Parents who moved to the city late in life and do not yet know the home well",
      ],
    },
    climate: {
      intro:
        "The weather is milder than most Indian cities, but Bengaluru gets rain from both the south-west monsoon (June to September) and the north-east monsoon (October to November).",
      points: [
        "Wet entrances, balconies and utility areas for months at a time",
        "Cool early mornings when stiff joints make the first walk of the day harder",
        "Power cuts during storms that leave stairs and corridors dark",
      ],
    },
    family:
      "Many parents in Bengaluru have children working in other cities or abroad, often in the US or Europe, and some parents moved here to be closer to a child who later relocated. Either way, the people who worry most are often a long flight away.",
    firstChecks: [
      "Stair rails and lighting in multi-floor houses",
      "Anti-slip work on granite and tiled bathroom floors",
      "Backup lighting for the night-time path to the toilet",
    ],
  },
  {
    slug: "chennai",
    blogSlug: "caring-for-ageing-parents-in-chennai-from-far-away",
    blogTitle: "Caring for ageing parents in Chennai when you live far away",
    name: "Chennai",
    alsoKnownAs: "Madras",
    state: "Tamil Nadu",
    metaTitle: "Elder Care in Chennai for Ageing Parents | KushAlaya",
    metaDescription:
      "Home safety assessments, bathroom fixes and caregiver visits for elderly parents in Chennai, with updates for family across India or abroad.",
    lede: "Safer homes and regular caregiver visits for parents living in Chennai, with an update for the family after every visit.",
    homes: {
      intro:
        "Chennai has a mix of older independent houses, often with a raised entrance and steps up from the street, and apartment buildings of every age.",
      points: [
        "Raised plinths and entrance steps built to keep rainwater out",
        "Older apartment buildings with stairs and no lift",
        "Bathrooms with a step or ledge between the wet and dry areas",
        "Terraces and open courtyards that parents still use every day",
      ],
    },
    climate: {
      intro:
        "Chennai is hot and humid for most of the year. Most of its rain comes with the north-east monsoon, roughly October to December, and heavy spells can flood streets.",
      points: [
        "Heat that makes dehydration and dizziness a real fall risk",
        "Damp, slippery floors and steps during the rainy months",
        "Days when parents cannot easily go out, so the home has to work well on its own",
      ],
    },
    family:
      "Families from Chennai are spread widely: children in Bengaluru or Hyderabad, and many abroad in the US, Singapore, the Gulf or the UK. Parents often prefer to stay in the home they know rather than move in with a child.",
    firstChecks: [
      "Entrance steps and rails, especially where the plinth is raised",
      "Bathroom ledges, floor grip and support near the toilet",
      "Cool, well-lit rooms and easy access to water in hot months",
    ],
  },
  {
    slug: "hyderabad",
    name: "Hyderabad",
    state: "Telangana",
    metaTitle: "Elder Care in Hyderabad for Ageing Parents | KushAlaya",
    metaDescription:
      "Home safety checks, fall-prevention products and caregiver visits for ageing parents in Hyderabad, with updates for family near or far.",
    lede: "Home safety checks, fixes and regular caregiver visits for parents in Hyderabad and Secunderabad, with updates wherever the family lives.",
    homes: {
      intro:
        "Hyderabad has many independent houses built over two or more floors, often with an outside staircase, alongside a fast-growing number of apartment communities.",
      points: [
        "Outside staircases to upper floors, open to sun and rain",
        "Ground-floor parents with the only Western toilet upstairs, or the other way round",
        "Marble and granite floors that turn slippery with water or dust",
        "New apartment complexes where parents have recently moved from an older house",
      ],
    },
    climate: {
      intro:
        "Summers, roughly March to June, are hot and dry. The south-west monsoon brings rain from about June to September, and winters are short and mild.",
      points: [
        "Intense summer heat, when dehydration adds to the risk of a fall",
        "Wet outside stairs and terraces during the monsoon",
        "Dust that makes smooth stone floors slippery even when dry",
      ],
    },
    family:
      "It is very common for children of Hyderabad families to work in the US, especially in technology, or in Bengaluru, Pune and the Gulf. Parents often stay on in the family house, and the children manage things from a different time zone.",
    firstChecks: [
      "Outside staircases: rails, edges and lighting",
      "Bathroom floors and grab bars, wherever the parent's toilet is",
      "Summer routines: water, rest and cool rooms",
    ],
    blogSlug: "caring-for-ageing-parents-in-hyderabad-from-far-away",
    blogTitle: "Caring for ageing parents in Hyderabad from far away",
  },
  {
    slug: "pune",
    blogSlug: "caring-for-ageing-parents-in-pune-from-far-away",
    blogTitle: "Caring for ageing parents in Pune when you live far away",
    name: "Pune",
    state: "Maharashtra",
    metaTitle: "Elder Care in Pune for Ageing Parents | KushAlaya",
    metaDescription:
      "Home safety assessments, fall-prevention fixes and caregiver visits for elderly parents in Pune, with updates for family in Mumbai or abroad.",
    lede: "Safer homes and regular caregiver visits for parents in Pune, with updates for the family in Mumbai, another city or abroad.",
    homes: {
      intro:
        "Much of Pune lives in cooperative housing societies, from older low-rise buildings to newer towers, with independent bungalows in older parts of the city.",
      points: [
        "Older society buildings with three or four floors and no lift",
        "Bungalows with garden steps and a separate outhouse or utility area",
        "Newer flats with sliding balcony doors and raised door frames",
        "Retired parents who chose Pune and now live on their own",
      ],
    },
    climate: {
      intro:
        "Pune gets most of its rain from the south-west monsoon, roughly June to September, and has pleasant winters that can be cool at night.",
      points: [
        "Wet staircases and building entrances through the monsoon",
        "Moss and algae on outside steps and garden paths",
        "Cool winter mornings when getting out of bed and walking is slower",
      ],
    },
    family:
      "Pune parents often have children close by in Mumbai, or further away in Bengaluru, the US, the UK or the Gulf. Even a child three hours away cannot drop in every week, and that is where regular visits help.",
    firstChecks: [
      "Stairs in buildings without a lift: rails and lighting on every landing",
      "Balcony and door thresholds",
      "Outside steps and paths that stay slippery after the rains",
    ],
  },
  {
    slug: "mumbai",
    blogSlug: "caring-for-ageing-parents-in-mumbai-from-far-away",
    blogTitle: "Caring for ageing parents in Mumbai when you live far away",
    name: "Mumbai",
    alsoKnownAs: "Bombay",
    state: "Maharashtra",
    metaTitle: "Elder Care in Mumbai for Ageing Parents | KushAlaya",
    metaDescription:
      "Home safety checks, bathroom fixes and caregiver visits for ageing parents in Mumbai flats, with updates for family in India or abroad.",
    lede: "Home safety checks, fixes and regular caregiver visits for parents living in Mumbai, with an update for the family after every visit.",
    homes: {
      intro:
        "Most Mumbai parents live in flats, and space is tight. Small bathrooms, narrow passages and furniture close together leave little room to move safely.",
      points: [
        "Compact bathrooms with no space for a shower chair unless planned well",
        "Older buildings with narrow stairs, small lifts or no lift at all",
        "Raised bathroom and kitchen thresholds to stop water spreading",
        "Rooms full of furniture and storage, which narrows the walking path",
      ],
    },
    climate: {
      intro:
        "Mumbai has a heavy south-west monsoon, roughly June to September, and stays humid for much of the year.",
      points: [
        "Damp, slippery floors and mould in bathrooms and corners",
        "Monsoon weeks when parents stay indoors and move less",
        "Humidity that loosens tiles, mats and fittings over time",
      ],
    },
    family:
      "Mumbai families are often spread across Pune, Bengaluru, the Gulf, the UK and the US. In a busy city even children who live nearby find it hard to visit as often as they would like.",
    firstChecks: [
      "Bathroom layout: grab bars and anti-slip work that fit a small space",
      "Clear walking paths through crowded rooms",
      "Damp and mould that make floors and mats slippery",
    ],
  },
  {
    slug: "delhi",
    blogSlug: "caring-for-ageing-parents-in-delhi-from-far-away",
    blogTitle: "Caring for ageing parents in Delhi when you live far away",
    name: "Delhi",
    alsoKnownAs: "New Delhi and the NCR",
    state: "Delhi",
    metaTitle: "Elder Care in Delhi NCR for Ageing Parents | KushAlaya",
    metaDescription:
      "Home safety checks, fall-prevention fixes and caregiver visits for elderly parents in Delhi and the NCR, with updates for family far away.",
    lede: "Safer homes and regular caregiver visits for parents in Delhi and the NCR, with updates wherever the family lives.",
    homes: {
      intro:
        "Delhi homes range from independent houses and builder floors to government-built and society flats, and many have been extended upwards over the years.",
      points: [
        "Builder floors where each storey is a separate home reached by a shared staircase",
        "Steep internal stairs in older houses, often without a second rail",
        "Rooftop terraces used for sun in winter",
        "Marble and stone floors throughout",
      ],
    },
    climate: {
      intro:
        "Delhi has very hot summers, a monsoon from about July to September, and cold winters with short days and fog.",
      points: [
        "Summer heat, when dehydration raises the risk of dizziness and falls",
        "Cold winter nights and early mornings, with room heaters and heavy blankets in use",
        "Days of poor air quality when parents stay indoors and walk less",
      ],
    },
    family:
      "Children of Delhi families often work in Gurugram, Noida, Bengaluru or abroad in the US, Canada, the UK or Australia. Parents frequently stay in the family home even when it has become too big or too vertical for them.",
    firstChecks: [
      "Stairs and rails, inside the house and on shared builder-floor staircases",
      "Winter safety: heaters, cables and the walk to the toilet at night",
      "Lighting for short winter days and foggy mornings",
    ],
  },
  {
    slug: "kolkata",
    name: "Kolkata",
    alsoKnownAs: "Calcutta",
    state: "West Bengal",
    metaTitle: "Elder Care in Kolkata for Ageing Parents | KushAlaya",
    metaDescription:
      "Home safety assessments, fall-prevention fixes and caregiver visits for ageing parents in Kolkata, with updates for family across India or abroad.",
    lede: "Home safety checks, fixes and regular caregiver visits for parents living in Kolkata, with an update for the family after every visit.",
    homes: {
      intro:
        "Kolkata has many old houses and buildings, some several generations old, alongside newer apartment blocks in the growing parts of the city.",
      points: [
        "Old houses with high ceilings, steep stairs and tall steps",
        "Red oxide and mosaic floors that are smooth and slippery when wet",
        "Bathrooms added later, sometimes up or down a step from the bedroom",
        "Buildings without lifts where parents live on an upper floor",
      ],
    },
    climate: {
      intro:
        "Kolkata is hot and humid for much of the year, with a heavy south-west monsoon from about June to September and waterlogging in some areas.",
      points: [
        "Humidity and damp that keep floors and walls wet",
        "Waterlogged streets that keep parents indoors for days",
        "Hot, sticky summers that tire older people quickly",
      ],
    },
    family:
      "Many Kolkata families have children who moved to Bengaluru, Delhi, Mumbai or abroad for work, while parents stay on in a home full of history. Getting home quickly is rarely easy.",
    firstChecks: [
      "Steep stairs and tall steps: rails and edge marking",
      "Smooth old floors and damp bathrooms",
      "Upper-floor living without a lift: daily routine and SOS options",
    ],
  },
  {
    slug: "kochi",
    name: "Kochi",
    alsoKnownAs: "Cochin",
    state: "Kerala",
    metaTitle: "Elder Care in Kochi for Ageing Parents | KushAlaya",
    metaDescription:
      "Home safety checks, fall-prevention fixes and caregiver visits for elderly parents in Kochi, with updates for family in the Gulf or abroad.",
    lede: "Safer homes and regular caregiver visits for parents in Kochi, with updates for the family in the Gulf, Europe, North America or anywhere else.",
    homes: {
      intro:
        "Many Kochi parents live in independent houses with a courtyard, sit-out or compound, and more are moving into apartments in the city.",
      points: [
        "Open sit-outs, courtyards and verandas with steps down to the compound",
        "Outside bathrooms or wash areas in older houses",
        "Large houses built for a big family, now home to two people",
        "Tiled roofs and open areas that let rain in at the edges",
      ],
    },
    climate: {
      intro:
        "Kochi gets very heavy rain from the south-west monsoon, roughly June to September, more rain from the north-east monsoon later in the year, and high humidity throughout.",
      points: [
        "Moss and algae on steps, courtyards and compound paths",
        "Floors that stay damp for weeks at a time",
        "Long wet spells when parents move less and stay indoors",
      ],
    },
    family:
      "It is very common in Kerala for children to work in the Gulf, the UK, Europe, Canada or the US. Parents in Kochi often live alone in a big house, and the family manages from abroad.",
    firstChecks: [
      "Steps, verandas and courtyard paths that grow moss in the rains",
      "Outside or older bathrooms: floor grip, lighting and support",
      "SOS and daily check-ins for parents living alone in a large house",
    ],
  },
];

export function seoCityBySlug(slug: string): SeoCity | undefined {
  return SEO_CITIES.find((c) => c.slug === slug);
}
