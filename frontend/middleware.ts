import { NextResponse } from "next/server";
import { isRetiredOpsPath } from "./lib/ops-retired";
import type { NextRequest } from "next/server";

import { hostname, isCaregiverHost, isFamilyHost, isMarketingHost } from "@/lib/hosts";

/**
 * Which portal this browser last signed in to (set by lib/portal-cookie.ts).
 * A hint for routing only — the client guards and the API still check the
 * real session. Without it every portal URL rendered "Loading…" and only
 * bounced to /login after the JS had loaded, which on a cold phone was 3–5s
 * of a blank page before the sign-in form appeared.
 */
const PORTAL_COOKIE = "ks_portal";

/**
 * First path segments the family host serves (app/kushalaya/family/login plus
 * every page under app/kushalaya/family/(portal)). Anything else on that host
 * is sent to "/" — which resolves to the dashboard or the sign-in page — so an
 * old bookmark or a typo never lands on a 404 there.
 */
const FAMILY_SEGMENTS = new Set(["login", "reset-password", "alerts", "circle", "contacts", "dashboard", "details", "digests", "documents", "messages", "more", "photos", "plan", "privacy", "receipts", "safety", "schedule", "services", "sign", "track", "updates", "visits", "wallet", "wellness"]);

function firstSegment(pathname: string): string {
  return pathname.split("/")[1] || "";
}

/** Staff portal routes that should never show "Loading…" to a signed-out visitor. */
const STAFF_PREFIXES = ["/dashboard", "/prospects", "/users", "/settings", "/documents", "/tenants"];

/**
 * Client-side navigations and prefetches fetch RSC payloads for the same
 * paths. Redirecting those breaks navigation: the router caches the redirect
 * target, so after sign-in `router.push(...)` replayed it and landed back on
 * /login with the button stuck on "Signing in…".
 *
 * Detecting them is fiddly, because Next strips its own markers before
 * middleware runs. Dumping the real request showed, for a client fetch of
 * /dashboard?_rsc=abc123:
 *
 *   rsc header ............ null      (stripped)
 *   next-router-prefetch .. null      (stripped)
 *   request.url ........... .../dashboard   (_rsc stripped from the URL too,
 *   nextUrl.search ........ ""         so searchParams.has("_rsc") is false)
 *   accept ................ text/x-component   <- survives
 *   sec-fetch-dest ........ empty              <- survives
 *
 * So the check keys off the two headers that do survive. A real page load is
 * `sec-fetch-dest: document`; an RSC fetch is `empty` and asks for
 * text/x-component. Clients that send neither (curl, uptime checks) are
 * treated as documents, which is the old behaviour.
 */
function isRscFetch(request: NextRequest): boolean {
  if (request.headers.get("accept")?.includes("text/x-component")) return true;
  // A navigation is a navigation whatever `sec-fetch-dest` says: a request
  // forwarded by a service worker (`fetch(event.request)` for a navigation)
  // arrives with mode "navigate" but not dest "document", and used to slip
  // past the `/` redirect below onto the statically prerendered page-level
  // redirect — whose HTML body (root shell + footer) the browser then showed.
  if (request.headers.get("sec-fetch-mode") === "navigate") return false;
  const dest = request.headers.get("sec-fetch-dest");
  return dest !== null && dest !== "document";
}

/**
 * 307 with a self-navigating body. NextResponse.redirect() sends no body, and
 * a client that renders the response instead of following it (an old service
 * worker in the way, some in-app browsers) would sit on a blank page. With
 * this body it hops on immediately, with or without JavaScript. Never cached.
 */
function redirectTo(url: URL): NextResponse {
  const href = url.href;
  const attr = href.replace(/"/g, "&quot;");
  const html =
    `<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=${attr}">` +
    `<script>location.replace(${JSON.stringify(href)})</script>`;
  return new NextResponse(html, {
    status: 307,
    headers: {
      location: href,
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function startsWithAny(pathname: string, prefixes: string[]): boolean {
  return prefixes.some((p) => pathname === p || pathname.startsWith(p + "/"));
}

/** Absolute URL on the PUBLIC host: behind nginx request.nextUrl is 127.0.0.1:3010. */
function publicUrl(request: NextRequest, hostHeader: string, path: string): URL {
  const h = hostname(hostHeader);
  const proto =
    request.headers.get("x-forwarded-proto")?.split(",")[0]?.trim() ||
    (h.includes("localhost") ? "http" : "https");
  return new URL(path, `${proto}://${hostHeader}`);
}

/** Family pages merged into others (Phase 2E) -> where they live now. */
const FAMILY_MERGED_ROUTES: Record<string, string> = {
  "/visits": "/updates",
  "/wellness": "/updates",
  "/schedule": "/services",
  "/photos": "/safety#photos",
  "/receipts": "/wallet#history",
};

/** Marks a request the family-host rewrite already handled. */
const FAMILY_REWRITE_MARK = "x-ks-family-rewrite";

// Host classification (family / marketing / ops) lives in lib/hosts.ts so it
// can be unit-tested and so staging hostnames are listed in one place.

/** Paths the middleware must never rewrite. */
function isPassThrough(pathname: string): boolean {
  return (
    pathname.startsWith("/api") ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/kushalaya") ||
    pathname.startsWith("/marketing") ||
    pathname.includes(".")
  );
}

export function middleware(request: NextRequest) {
  const hostHeader = request.headers.get("host") || "";

  // family.kushalaya.com/<path>  ->  /kushalaya/family/<path>
  if (isFamilyHost(hostHeader)) {
    const { pathname } = request.nextUrl;

    // Our own rewrite re-enters middleware. Without this guard the
    // normalisation below would redirect /login -> /login forever.
    const alreadyRewritten = request.headers.get(FAMILY_REWRITE_MARK) === "1";

    // In-app links still point at /kushalaya/family/*. Normalise the URL for
    // real page loads only.
    //
    // Next's client router fetches RSC payloads for the same paths; redirecting
    // those breaks navigation (the fetch fails and the app falls back to a full
    // load that then errors). Those requests carry an `RSC` header, so they are
    // served in place instead.
    const isRscRequest = isRscFetch(request);
    if (
      !alreadyRewritten &&
      !isRscRequest &&
      (pathname === "/kushalaya/family" || pathname.startsWith("/kushalaya/family/"))
    ) {
      const stripped = pathname.slice("/kushalaya/family".length) || "/";
      // Build from the public Host, NOT request.nextUrl: behind nginx its
      // origin is 127.0.0.1:3010, so redirecting to it sends the browser to an
      // address it cannot reach (ERR_FAILED).
      const h = hostname(hostHeader);
      const redirectProto =
        request.headers.get("x-forwarded-proto")?.split(",")[0]?.trim() ||
        (h.includes("localhost") ? "http" : "https");
      const target = new URL(stripped, `${redirectProto}://${hostHeader}`);
      target.search = request.nextUrl.search;
      return redirectTo(target);
    }

    if (alreadyRewritten || isPassThrough(pathname)) return NextResponse.next();

    // Merged family pages (Phase 2E): old addresses keep working. Page loads
    // only; detail pages such as /visits/<id> are left alone.
    const merged = !isRscRequest ? FAMILY_MERGED_ROUTES[pathname.replace(/\/+$/, "")] : undefined;
    if (merged) {
      return redirectTo(publicUrl(request, hostHeader, merged));
    }

    // Real page loads only (client navigations carry the RSC header and are
    // gated by RequireFamilyAuth as before).
    const signedInHere = request.cookies.get(PORTAL_COOKIE)?.value === "family";
    // Unknown address on the family host (page loads only): straight to "/",
    // i.e. the dashboard when signed in. No 404s and no legacy URL handling.
    if (!isRscRequest && pathname !== "/" && !FAMILY_SEGMENTS.has(firstSegment(pathname))) {
      return redirectTo(publicUrl(request, hostHeader, "/"));
    }
    // `/` is decided on the server for EVERY request shape. Nothing fetches it
    // as an RSC payload except a link to "/", and a redirect is the right
    // answer there too (the router follows it). Leaving it to the page-level
    // redirect() produced a year-cached 307 with an HTML body.
    if (pathname === "/") {
      return redirectTo(publicUrl(request, hostHeader, signedInHere ? "/dashboard" : "/login"));
    }
    // Other portal pages: real page loads only (router fetches are gated by
    // RequireFamilyAuth as before — redirecting them poisons the router cache).
    // /track/<token>: the live tracking link from an "on the way" message — no login.
    // /sign/<token>: a contract signing link (vendor / client) — no login either.
    if (!isRscRequest && pathname !== "/login" && pathname !== "/reset-password" && !pathname.startsWith("/track/") && !pathname.startsWith("/sign/") && !signedInHere) {
      return redirectTo(publicUrl(request, hostHeader, "/login"));
    }

    const h = hostname(hostHeader);
    const proto =
      request.headers.get("x-forwarded-proto")?.split(",")[0]?.trim() ||
      (h.includes("localhost") ? "http" : "https");
    const suffix = pathname === "/" ? "" : pathname;
    const rewriteUrl = new URL(`/kushalaya/family${suffix}`, `${proto}://${hostHeader}`);
    rewriteUrl.search = request.nextUrl.search;
    const headers = new Headers(request.headers);
    headers.set(FAMILY_REWRITE_MARK, "1");
    return NextResponse.rewrite(rewriteUrl, { request: { headers } });
  }

  if (!isMarketingHost(hostHeader)) {
    // Ops host. `/` and the staff pages decide on the server whether to show
    // the sign-in form or the portal — no "Loading…" page in between.
    const { pathname } = request.nextUrl;
    const signedInHere = request.cookies.get(PORTAL_COOKIE)?.value === "staff";
    // caregiver.kushalaya.com: only the field app, sign-in and password reset.
    if (isCaregiverHost(hostHeader) && !isRscFetch(request) && !isPassThrough(pathname)) {
      const allowed = ["/caregiver", "/login", "/reset-password", "/forgot-password"];
      if (pathname === "/" || !startsWithAny(pathname, allowed)) {
        // A caregiver's cookie says "caregiver", not "staff" — both count as signed in here.
        const portal = request.cookies.get(PORTAL_COOKIE)?.value;
        if (portal === "staff" || portal === "caregiver") return redirectTo(publicUrl(request, hostHeader, "/caregiver"));
        const login = publicUrl(request, hostHeader, "/login");
        login.searchParams.set("redirect", "/caregiver");
        return redirectTo(login);
      }
    }
    if (pathname === "/") {
      return redirectTo(publicUrl(request, hostHeader, signedInHere ? "/dashboard" : "/login"));
    }
    // The old stand-alone assessor home (no Ops sidebar) → the same list inside Ops.
    if (!isRscFetch(request) && pathname === "/kushalaya") {
      return redirectTo(publicUrl(request, hostHeader, "/kushalaya/assessments"));
    }
    // Retired pages (partners, suppliers, tenants, …) — see lib/ops-retired.ts.
    if (!isRscFetch(request) && isRetiredOpsPath(pathname)) {
      return redirectTo(publicUrl(request, hostHeader, "/dashboard"));
    }
    if (!isRscFetch(request) && !signedInHere && startsWithAny(pathname, STAFF_PREFIXES)) {
      const login = publicUrl(request, hostHeader, "/login");
      login.searchParams.set("redirect", pathname + request.nextUrl.search);
      return redirectTo(login);
    }
    return NextResponse.next();
  }

  const { pathname } = request.nextUrl;
  if (
    pathname.startsWith("/api") ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/marketing") ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  if (pathname === "/" || pathname === "") {
    // Build from public Host — behind nginx, nextUrl.origin is often localhost:3010,
    // and rewriting to that absolute URL causes a 500 on /.
    const hostname = hostHeader.toLowerCase().split(":")[0];
    const proto =
      request.headers.get("x-forwarded-proto")?.split(",")[0]?.trim() ||
      (hostname.includes("localhost") ? "http" : "https");
    const rewriteUrl = new URL("/marketing", `${proto}://${hostHeader}`);
    rewriteUrl.search = request.nextUrl.search;
    return NextResponse.rewrite(rewriteUrl);
  }

  // "Parent Care Check" → "Eldercare Discovery" → "KushCare Discovery" (27 Oct 2026): old links
  // and printed QR codes keep working, query (?src=qr, UTM) included.
  if (
    pathname === "/parent-care-check" ||
    pathname === "/marketing/parent-care-check" ||
    pathname === "/eldercare-discovery" ||
    pathname === "/eldercare-discovery/"
  ) {
    const target = publicUrl(request, hostHeader, "/kushcare-discovery");
    target.search = request.nextUrl.search;
    return NextResponse.redirect(target, 301);
  }

  // A family's referral link (FIX 108): /r/<code> → KushCare Discovery with the code pre-filled.
  const referral = /^\/r\/([0-9A-Za-z]{6,20})\/?$/.exec(pathname);
  if (referral) {
    const target = publicUrl(request, hostHeader, "/kushcare-discovery");
    target.search = request.nextUrl.search;
    target.searchParams.set("ref", referral[1].toUpperCase());
    if (!target.searchParams.get("utm_source")) target.searchParams.set("utm_source", "referral");
    return NextResponse.redirect(target, 302);
  }

  // Clean public partner / packages URLs → App Router under /marketing/...
  if (
    pathname === "/partners" ||
    pathname === "/become-a-partner" ||
    pathname === "/packages" ||
    pathname === "/safe-homes" ||
    pathname === "/kushcare-discovery" ||
    pathname === "/vision" ||
    pathname === "/services" ||
    pathname === "/brochure" ||
    pathname === "/founder" ||
    pathname === "/contact" ||
    pathname === "/kushlife" ||
    pathname === "/about" ||
    // SEO landing pages (www only): FAQ, services and city pages. Unknown slugs
    // 404 (dynamicParams = false in their routes).
    pathname === "/faq" ||
    /^\/services\/[a-z0-9-]{1,60}\/?$/.test(pathname) ||
    /^\/elder-care\/[a-z0-9-]{1,40}\/?$/.test(pathname) ||
    // Legal pages (www). The family host keeps its own /privacy (handled above).
    pathname === "/privacy" ||
    pathname === "/terms" ||
    pathname === "/refund-policy" ||
    // Blog list and articles (/blog/<slug>) — www only; the family host sends
    // unknown paths to "/" and the ops host has no /blog page.
    pathname === "/blog" ||
    /^\/blog\/[a-z0-9-]{1,100}\/?$/.test(pathname)
  ) {
    const hostname = hostHeader.toLowerCase().split(":")[0];
    const proto =
      request.headers.get("x-forwarded-proto")?.split(",")[0]?.trim() ||
      (hostname.includes("localhost") ? "http" : "https");
    const rewriteUrl = new URL(`/marketing${pathname}`, `${proto}://${hostHeader}`);
    rewriteUrl.search = request.nextUrl.search;
    return NextResponse.rewrite(rewriteUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
