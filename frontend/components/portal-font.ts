import { Manrope } from "next/font/google";

/**
 * Typeface shared by the Kushalaya portals (family Care Hub, KushAlaya Ops and
 * both sign-in pages). One instance here so every page shares the same font
 * files; the CSS reads it through `--fh-font`.
 */
export const portalFont = Manrope({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  display: "swap",
  variable: "--fh-font",
});
