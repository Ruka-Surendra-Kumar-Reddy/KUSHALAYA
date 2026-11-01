"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createSubNav, type SubNavLinkProps } from "@workforceos/contracts/shell";

import { useBranding } from "@/components/BrandingProvider";
import { useTranslation } from "@/lib/i18n/context";

const NextSubNavLink = ({ href, className, children }: SubNavLinkProps) => (
  <Link href={href} className={className}>
    {children}
  </Link>
);

const OperationsSubNav = createSubNav(NextSubNavLink);
const AttendanceSubNav = createSubNav(NextSubNavLink);
const MonitoringSubNav = createSubNav(NextSubNavLink);

export function OperationsNav() {
  const pathname = usePathname();
  const { t } = useTranslation();
  const branding = useBranding();
  return (
    <OperationsSubNav
      subnavId="operations"
      pathname={pathname}
      vertical={branding.vertical}
      t={t}
    />
  );
}

export function AttendanceNav() {
  const pathname = usePathname();
  const { t } = useTranslation();
  const branding = useBranding();
  return (
    <AttendanceSubNav
      subnavId="attendance"
      pathname={pathname}
      vertical={branding.vertical}
      t={t}
    />
  );
}

export function MonitoringNav() {
  const pathname = usePathname();
  const { t } = useTranslation();
  const branding = useBranding();
  return (
    <MonitoringSubNav
      subnavId="monitoring"
      pathname={pathname}
      vertical={branding.vertical}
      t={t}
    />
  );
}
