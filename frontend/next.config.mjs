/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Deploys build into a staging folder and swap it in (scripts/start-livewell.sh):
  // `next build` used to overwrite .next underneath the running server, which
  // served HTML pointing at chunk hashes that no longer existed — visitors got
  // 400s for CSS/JS and an unstyled page until the restart. Unset at runtime,
  // so `next start` reads the swapped-in .next as usual.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  transpilePackages: ["@workforceos/contracts"],
  // Keep recently visited admin routes compiled in `next dev` so navbar
  // clicks do not wait several seconds for webpack to rebuild the page.
  onDemandEntries: {
    maxInactiveAge: 60 * 60 * 1000,
    pagesBufferLength: 40,
  },
  experimental: {
    staleTimes: {
      dynamic: 30,
      static: 180,
    },
  },
  // Browsers and bots still ask for /favicon.ico; serve the brand icon.
  async rewrites() {
    return [{ source: "/favicon.ico", destination: "/brand/favicon-32.png" }];
  },
  async headers() {
    return [
      // Baseline security headers on every response. No strict CSP on purpose
      // (inline scripts and analytics would break); framing is limited to
      // our own origin.
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
        ],
      },
      // Files under public/ default to `max-age=0`, so the browser revalidates
      // them on every page load. The HTML and the JS chunks come back from
      // cache instantly (chunks are hashed and immutable), but the logo waited
      // on a round trip — which is why it appeared a beat after the page.
      //
      // Safe to cache hard because lib/brand-assets.ts appends `?v=`: a new
      // logo gets a new URL. Bump BRAND_ASSET_VERSION when you replace one.
      {
        source: "/brand/:path*",
        headers: [
          { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
        ],
      },
      // Marketing photography is not versioned, so it gets a modest fresh
      // window instead: instant on repeat views, and a replaced photo is picked
      // up within the hour rather than a year later.
      //
      // Image files only. www pages are rewritten to /marketing/<page> by the
      // middleware, so "/marketing/:path*" also matched the HTML and browsers
      // kept showing an old page (e.g. the old menu) for up to a day.
      {
        source: "/marketing/:path(.*\\.(?:webp|png|jpg|jpeg|avif|gif|svg))",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=3600, stale-while-revalidate=86400",
          },
        ],
      },
    ];
  },
  async redirects() {
    return [
      // Family portal moved to its own host so families never see an "ops" URL
      // and the brand is not repeated in the path. Temporary (307) while the
      // subdomain settles — switch to permanent once it has proven itself.
      // Scoped to the ops host on purpose. Without `has`, these also matched the
      // path the middleware rewrites to internally on family.kushalaya.com, so
      // the family portal redirected to itself instead of rendering.
      {
        source: "/kushalaya/family",
        has: [{ type: "host", value: "ops.kushalaya.com" }],
        destination: "https://family.kushalaya.com/",
        permanent: false,
      },
      {
        source: "/kushalaya/family/:path*",
        has: [{ type: "host", value: "ops.kushalaya.com" }],
        destination: "https://family.kushalaya.com/:path*",
        permanent: false,
      },
      // Staging mirrors the same split (see lib/hosts.ts and
      // deploy/nginx/staging.kushalaya.com.conf).
      {
        source: "/kushalaya/family",
        has: [{ type: "host", value: "staging-ops.kushalaya.com" }],
        destination: "https://staging-family.kushalaya.com/",
        permanent: false,
      },
      {
        source: "/kushalaya/family/:path*",
        has: [{ type: "host", value: "staging-ops.kushalaya.com" }],
        destination: "https://staging-family.kushalaya.com/:path*",
        permanent: false,
      },
      // The /livewell/* redirects were removed deliberately: the brand is
      // Kushalaya and those URLs are gone. Nearly all of the traffic they were
      // catching came from our own stale NEXT_PUBLIC_FAMILY_PORTAL_URL, which
      // now points at https://family.kushalaya.com/login. Old bookmarks and
      // crawler hits to /livewell/* now 404 — that is intended.
      // Older still: /home-safety predates /livewell. Left temporary, as it was.
      {
        source: "/home-safety",
        destination: "/kushalaya",
        permanent: false,
      },
      {
        source: "/home-safety/:path*",
        destination: "/kushalaya/:path*",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
