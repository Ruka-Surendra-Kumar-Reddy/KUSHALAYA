/**
 * Strip rupee figures and Hyderabad rate lines from catalog copy on public marketing pages.
 */
export function withoutMarketingPrices(text: string): string {
  if (!text) return text;
  return text
    .replace(/\s*Hyderabad:\s*[^.]*(?:\.|$)/gi, " ")
    .replace(/₹[\d,.]+(?:\s*[–—-]\s*₹?[\d,.]+)?(?:\s*\/\w+)?/g, "")
    .replace(/\s*[·•]\s*(?=[·•]|\s|$)/g, " ")
    .replace(/\s{2,}/g, " ")
    .replace(/\s+([.,;:])/g, "$1")
    .trim();
}
