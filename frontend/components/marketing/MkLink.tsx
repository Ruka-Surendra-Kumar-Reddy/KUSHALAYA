"use client";

import Link, { type LinkProps } from "next/link";
import { forwardRef, useEffect, useState, type AnchorHTMLAttributes, type ReactNode } from "react";

/**
 * next/link for the public site. On www.kushalaya.com middleware rewrites the
 * clean paths (/founder, /packages …) to /marketing/*. Anywhere else (local
 * dev, the ops host) the site is only reachable under /marketing, so the same
 * links would go nowhere. After mount, if the page is being viewed under
 * /marketing, site-relative hrefs get that prefix. SSR and the first render
 * use the clean href, so hydration always matches.
 */
export function useMkHref(): (href: string) => string {
  const [prefixed, setPrefixed] = useState(false);
  useEffect(() => {
    setPrefixed(window.location.pathname.startsWith("/marketing"));
  }, []);
  return (href: string) => {
    if (!prefixed || !href.startsWith("/") || href.startsWith("/marketing") || href.startsWith("/kushalaya")) {
      return href;
    }
    if (href === "/") return "/marketing";
    if (href.startsWith("/#")) return `/marketing${href.slice(1)}`;
    return `/marketing${href}`;
  };
}

type Props = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> &
  Omit<LinkProps, "href"> & { href: string; children?: ReactNode };

export const MkLink = forwardRef<HTMLAnchorElement, Props>(function MkLink({ href, ...rest }, ref) {
  const resolve = useMkHref();
  return <Link ref={ref} href={resolve(href)} {...rest} />;
});
