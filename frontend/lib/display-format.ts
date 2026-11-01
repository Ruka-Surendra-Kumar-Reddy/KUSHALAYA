/** Display-only tidy-ups for names and phone numbers typed in different ways. Stored values are unchanged. */

/** "surendra ruka" → "Surendra Ruka"; names that already have capitals are left alone ("McDonald", "KUMAR"). */
export function displayName(first?: string | null, last?: string | null): string {
  const full = `${first || ""} ${last || ""}`.replace(/\s+/g, " ").trim();
  if (!full || /[A-Z]/.test(full)) return full;
  return full.replace(/(^|[\s'-])([a-z])/g, (_m, sep: string, ch: string) => sep + ch.toUpperCase());
}

/** Indian mobiles as "+91 63044 80702"; anything else as typed. */
export function displayPhone(raw?: string | null): string {
  const v = (raw || "").trim();
  const d = v.replace(/\D/g, "");
  const ten = d.length === 10 ? d : d.length === 12 && d.startsWith("91") ? d.slice(2) : d.length === 11 && d.startsWith("0") ? d.slice(1) : "";
  return ten && /^[6-9]/.test(ten) ? `+91 ${ten.slice(0, 5)} ${ten.slice(5)}` : v;
}
