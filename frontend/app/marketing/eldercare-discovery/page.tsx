import { permanentRedirect } from "next/navigation";

/** Renamed "KushCare Discovery" (27 Oct 2026). The middleware 301s /eldercare-discovery; this is the fallback. */
export default function EldercareDiscoveryPage({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(searchParams || {})) {
    for (const one of Array.isArray(v) ? v : v === undefined ? [] : [v]) q.append(k, one);
  }
  const qs = q.toString();
  permanentRedirect(`/kushcare-discovery${qs ? `?${qs}` : ""}`);
}
