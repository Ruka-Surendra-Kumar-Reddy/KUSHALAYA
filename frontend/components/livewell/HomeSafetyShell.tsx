"use client";

import Link from "next/link";
import { PublicBrandMark } from "@/components/BrandLogo";
import { publicBrandName } from "@/lib/public-brand";

export function HomeSafetyShell({
  title,
  subtitle,
  children,
  backHref,
  showNav = true,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  backHref?: string;
  showNav?: boolean;
}) {
  function handleNewAssessment() {
    window.location.assign("/kushalaya/assessments");
  }

  return (
    <div className="home-safety-app">
      <header className="home-safety-header">
        <div className="home-safety-header-top">
          {backHref ? (
            /* Plain <a> — Next.js Link soft-nav can fail in the assessor PWA. */
            <a href={backHref} className="home-safety-back">
              ← Back
            </a>
          ) : (
            <span className="home-safety-brand">
              <PublicBrandMark variant="icon" className="home-safety-brand-icon" alt="" />
              {publicBrandName()}
            </span>
          )}
        </div>
        <h1>{title}</h1>
        {subtitle && <p className="home-safety-subtitle">{subtitle}</p>}
      </header>
      <main className="home-safety-main">{children}</main>
      {showNav && !backHref && (
        <nav className="home-safety-bottom-nav" aria-label="Home safety">
          <Link href="/kushalaya" className="home-safety-nav-link">
            Assessments
          </Link>
          <Link href="/kushalaya/showcase" className="home-safety-nav-link">
            Showcase
          </Link>
          <button
            type="button"
            onClick={handleNewAssessment}
            className="home-safety-nav-link home-safety-nav-primary"
          >
            + New
          </button>
        </nav>
      )}
    </div>
  );
}
