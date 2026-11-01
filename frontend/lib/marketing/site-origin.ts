import { hostname } from "@/lib/hosts";

/** Public origin of the www site for the host a request arrived on. */
export function siteOrigin(host: string): string {
  const h = hostname(host);
  return `${h.includes("localhost") ? "http" : "https"}://${h === "kushalaya.com" ? "www.kushalaya.com" : h}`;
}
