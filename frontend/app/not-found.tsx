import Link from "next/link";
import { PublicBrandMark } from "@/components/BrandLogo";
import { MarketingNotFound } from "@/components/marketing/MarketingNotFound";
import { NotFoundSwitch } from "@/components/NotFoundSwitch";
import { publicBrandName } from "@/lib/public-brand";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: `Page not found | ${publicBrandName()}`,
  robots: { index: false, follow: true },
};

/**
 * Branded 404. Without this, Next's built-in not-found page is used, and in a
 * dark-mode browser that page is black with white text — a stale bookmark or
 * app icon pointing at a retired URL looked like "a blank dark page". Old
 * `/livewell/*` URLs deliberately 404 here (removed at the owner's request,
 * Sept 2026 — see CLAUDE.md "URLs"), so this page is what those stale links
 * land on: it stays light and offers the right doors.
 */
export default function NotFound() {
  // www: the marketing header/footer with Home, Plans and Contact. Ops (and
  // anything else) keeps the portal doors below; the family host never gets
  // here — middleware sends unknown family paths to "/". Signed-in staff
  // (routing cookie, not a credential) get one obvious way back. The choice is
  // made in the browser so that no page has to be rendered per request.
  const staff = (
      <main className="not-found">
        <PublicBrandMark variant="lockup" className="not-found-mark" alt={publicBrandName()} />
        <p className="not-found-code">404</p>
        <h1>We couldn’t find that page</h1>
        <p className="not-found-lede">The link may be old or mistyped.</p>
        <div className="not-found-actions">
          <Link className="not-found-btn primary" href="/dashboard">
            Back to dashboard
          </Link>
        </div>
      </main>
  );
  const other = (
    <main className="not-found">
      <PublicBrandMark variant="lockup" className="not-found-mark" alt={publicBrandName()} />
      <p className="not-found-code">404</p>
      <h1>We couldn’t find that page</h1>
      <p className="not-found-lede">
        The link may be old or mistyped. Choose where you’d like to go:
      </p>
      <div className="not-found-actions">
        <a className="not-found-btn primary" href="https://family.kushalaya.com/login">
          Family portal
        </a>
        <Link className="not-found-btn" href="/login">
          Staff sign-in
        </Link>
        <a className="not-found-btn" href="https://www.kushalaya.com/">
          {publicBrandName()} home
        </a>
      </div>
    </main>
  );
  return <NotFoundSwitch marketing={<MarketingNotFound />} staff={staff} other={other} />;
}
