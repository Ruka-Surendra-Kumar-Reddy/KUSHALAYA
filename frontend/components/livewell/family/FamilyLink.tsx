"use client";

import Link, { type LinkProps } from "next/link";
import { forwardRef, useEffect, useState, type AnchorHTMLAttributes, type ReactNode } from "react";

const FAMILY_PREFIX = "/kushalaya/family";

/**
 * Drop-in for next/link inside the family portal that keeps the address bar
 * clean on family.kushalaya.com.
 *
 * Pages link to the internal `/kushalaya/family/...` paths. On the family
 * host the middleware rewrites the clean URL to that path for real page loads
 * but deliberately leaves client-side navigations alone (redirecting a router
 * fetch breaks the router), so a plain <Link> to the internal path puts
 * `family.kushalaya.com/kushalaya/family/alerts` in the address bar — the
 * repeated-brand URL the owner asked us to remove.
 *
 * Mount-aware on purpose: the server (and the first client render) cannot
 * know the host, so both use the internal path and the HTML matches; after
 * mount the href switches to the clean form when the current URL is already
 * clean. Every real click happens after mount. On the ops host, where the
 * portal really lives under /kushalaya/family, nothing changes.
 */
export function useFamilyHref(): (href: string) => string {
  const [clean, setClean] = useState(false);
  useEffect(() => {
    setClean(!window.location.pathname.startsWith(FAMILY_PREFIX));
  }, []);
  return (href: string) => {
    if (!clean || !href.startsWith(FAMILY_PREFIX)) return href;
    const rest = href.slice(FAMILY_PREFIX.length);
    return rest === "" ? "/" : rest;
  };
}

type Props = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> &
  Omit<LinkProps, "href"> & { href: string; children?: ReactNode };

export const FamilyLink = forwardRef<HTMLAnchorElement, Props>(function FamilyLink(
  { href, ...rest },
  ref,
) {
  const resolve = useFamilyHref();
  return <Link ref={ref} href={resolve(href)} {...rest} />;
});
