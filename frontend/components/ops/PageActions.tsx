import Link from "next/link";
import type { ReactNode } from "react";

/**
 * One pattern for page-level links (styles: "Page actions" block in components/ks-shell.css).
 *
 * - <PageActions>  secondary actions / related pages as pill buttons. Wraps on
 *   desktop, scrolls sideways on phones. Put primary buttons in as children.
 * - <SectionTabs>  sibling pages of one section as a segmented bar; the current
 *   page is highlighted (aria-current="page").
 * - <BackLink>     "← Settings" style link back to the parent page.
 *
 * Inline links inside sentences stay as plain links.
 */

export type PageAction = { href: string; label: string; icon?: ReactNode; title?: string };

export function PageActions({
  items = [],
  children,
  label = "Page actions",
  className = "",
}: {
  items?: PageAction[];
  children?: ReactNode;
  label?: string;
  className?: string;
}) {
  return (
    <div className={`ks-pa${className ? ` ${className}` : ""}`}>
      {children ? <div className="ks-pa-main">{children}</div> : null}
      {items.length ? (
        <nav className="ks-pa-links" aria-label={label}>
          {items.map((a) => (
            <Link key={a.href} href={a.href} className="ks-pa-item" title={a.title}>
              {a.icon ? <span className="ks-pa-icon" aria-hidden="true">{a.icon}</span> : null}
              {a.label}
            </Link>
          ))}
        </nav>
      ) : null}
    </div>
  );
}

export function SectionTabs({
  items,
  current,
  label,
}: {
  items: PageAction[];
  current: string;
  label: string;
}) {
  return (
    <nav className="ks-seg" aria-label={label}>
      {items.map((t) =>
        t.href === current ? (
          <span key={t.href} className="ks-seg-item is-on" aria-current="page" title={t.title}>
            {t.label}
          </span>
        ) : (
          <Link key={t.href} href={t.href} className="ks-seg-item" title={t.title}>
            {t.label}
          </Link>
        ),
      )}
    </nav>
  );
}

export function BackLink({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href} className="ks-back">
      <span aria-hidden="true">←</span> {label}
    </Link>
  );
}

/** Sub-pages of Visits (no longer shown as tabs; kept for reference). */
export const SCHEDULE_TABS: PageAction[] = [
  { href: "/kushalaya/visits", label: "Visits" },
  { href: "/kushalaya/visits/roster", label: "Weekly roster", title: "Weekly roster · repeating visits" },
  { href: "/kushalaya/visits/leave", label: "Leave and cover" },
];

export function ScheduleTabs({ current }: { current: string }) {
  return <SectionTabs items={SCHEDULE_TABS} current={current} label="Schedule pages" />;
}

const svg = (d: ReactNode) => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    {d}
  </svg>
);

/** Small stroke icons for page actions. */
export const PA_ICONS = {
  clock: svg(<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>),
  report: svg(<><path d="M7 3h7l5 5v13H7z" /><path d="M14 3v5h5M10 13h6M10 17h6" /></>),
  invoice: svg(<><path d="M6 3h12v18l-3-2-3 2-3-2-3 2z" /><path d="M9 8h6M9 12h6" /></>),
  building: svg(<><path d="M4 21V5l8-2v18M12 9h8v12" /><path d="M8 8v.01M8 12v.01M8 16v.01M16 13v.01M16 17v.01" /></>),
  letter: svg(<><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></>),
};
