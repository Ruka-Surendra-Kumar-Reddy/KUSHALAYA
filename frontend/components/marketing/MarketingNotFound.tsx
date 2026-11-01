import { portalFont } from "@/components/portal-font";
import { CONTACT_HREF, PACKAGES_HREF, PARENT_CARE_CHECK_HREF } from "@/lib/marketing/family-contacts";
import "@/app/marketing/marketing.css";
import { MarketingShell } from "./MarketingShell";
import { MkLink as Link } from "./MkLink";

/** www 404: the normal site header, footer and three ways back — no portal sign-in buttons. */
export function MarketingNotFound() {
  return (
    <div className={`mk-root ${portalFont.variable}`}>
      <MarketingShell>
        <section className="mk-band" aria-labelledby="mk-404-title">
          <div className="mk-wrap" style={{ textAlign: "center", maxWidth: "40rem" }}>
            <p className="mk-eyebrow" style={{ justifyContent: "center" }}>
              404
            </p>
            <h1 id="mk-404-title">We couldn&rsquo;t find that page</h1>
            <p className="mk-sub" style={{ margin: "0.75rem auto 1.5rem" }}>
              The link may be old or mistyped. These will get you back on track:
            </p>
            <div className="mk-actions" style={{ justifyContent: "center" }}>
              <Link className="mk-btn mk-btn-primary mk-btn-lg" href="/">
                Home
              </Link>
              <Link className="mk-btn mk-btn-outline mk-btn-lg" href={PACKAGES_HREF}>
                Plans &amp; pricing
              </Link>
              <Link className="mk-btn mk-btn-outline mk-btn-lg" href={CONTACT_HREF}>
                Contact us
              </Link>
            </div>
            <p className="mk-note" style={{ marginTop: "1.5rem" }}>
              Or try: <Link href={PARENT_CARE_CHECK_HREF}>Book a KushCare Discovery</Link> ·{" "}
              <Link href="/blog">Read the blog</Link> · <Link href="/faq">FAQ</Link>
            </p>
          </div>
        </section>
      </MarketingShell>
    </div>
  );
}
