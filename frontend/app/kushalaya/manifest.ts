import { publicBrandName, withPublicBrand } from "@/lib/public-brand";
import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: withPublicBrand("LiveWell360 Assessor"),
    short_name: publicBrandName(),
    description: "Score home safety risk on site",
    start_url: "/kushalaya",
    display: "standalone",
    background_color: "#0d6e6e",
    theme_color: "#0d6e6e",
    orientation: "any",
    icons: [
      { src: "/brand/kushalaya-icon.png", sizes: "512x512", type: "image/png" },
      { src: "/brand/apple-touch-icon.png", sizes: "180x180", type: "image/png" },
    ],
  };
}
