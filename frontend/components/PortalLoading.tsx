import { PublicBrandMark } from "@/components/BrandLogo";
import { publicBrandName } from "@/lib/public-brand";

/**
 * What a portal shows while the client-side session check runs. The mark is
 * inlined in the HTML, so this paints with the first frame instead of a bare
 * "Loading…" on an empty page.
 */
export function PortalLoading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="portal-loading" role="status" aria-live="polite">
      <PublicBrandMark variant="lockup" className="portal-loading-mark" alt={publicBrandName()} />
      <span className="portal-loading-bar" aria-hidden />
      <p>{label}</p>
    </div>
  );
}
