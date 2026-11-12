"use client";

import "@/components/ops/dashboard.css";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { api, getStoredAuth } from "@/lib/api";
import { greetingIST } from "@/lib/ist";
import { can } from "@/lib/roles";
import { useTranslation } from "@/lib/i18n/context";
import { listJobs, type CareJob } from "@/lib/jobs";
import { isStaleCheckIn } from "@/lib/run-sheet";
import { SmsOffBanner } from "@/components/ops/SmsOffBanner";
import { dashboardCounts, type DashboardCounts } from "@/lib/sales-pipeline";

/** Only the fields the count tiles read from /dashboard/attention. */
type Attention = {
  alerts: { kind: string }[];
  missed?: unknown[];
  viewer?: { first_name: string; role: string; is_admin: boolean };
  counts: { unread_messages: number; visits_today: number; reassessments?: number };
};

const ICON = {
  clients: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3 20a6 6 0 0 1 12 0" />
      <circle cx="17" cy="9" r="2.4" />
      <path d="M15 20a5 5 0 0 1 6-4.6" />
    </svg>
  ),
  assessments: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="5" y="4" width="14" height="17" rx="2" />
      <path d="M9 4V3h6v1M9 11l2 2 4-4M9 16h6" />
    </svg>
  ),
  visits: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M8 3v4M16 3v4M3 11h18" />
    </svg>
  ),
  catalog: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="3" width="8" height="8" rx="2" />
      <rect x="13" y="3" width="8" height="8" rx="2" />
      <rect x="3" y="13" width="8" height="8" rx="2" />
      <rect x="13" y="13" width="8" height="8" rx="2" />
    </svg>
  ),
  phone: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="6" y="2" width="12" height="20" rx="2.5" />
      <path d="M11 18h2" />
    </svg>
  ),
  heart: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" />
    </svg>
  ),
};

/** "manager@sunrise-care.example" -> "Manager" (only until the real name has loaded). */
function firstNameFromEmail(email: string): string {
  const local = (email || "").split("@")[0] || "";
  const word = local.split(/[._-]/)[0] || "";
  return word ? word[0]!.toUpperCase() + word.slice(1) : "";
}

export default function DashboardPage() {
  const { t } = useTranslation();
  const auth = getStoredAuth();
  const [data, setData] = useState<Attention | null>(null);
  const [failed, setFailed] = useState(false);
  const [stale, setStale] = useState<CareJob[]>([]);
  const [sales, setSales] = useState<DashboardCounts | null>(null);

  const load = useCallback(() => {
    dashboardCounts()
      .then(setSales)
      .catch(() => setSales(null));
    api<Attention>("/api/v1/home-safety/dashboard/attention")
      .then((d) => {
        setData(d);
        setFailed(false);
      })
      .catch(() => setFailed(true));
    // Check-ins more than 12 hours old that were never closed.
    listJobs({ open_only: true })
      .then((jobs) => setStale(jobs.filter((j) => isStaleCheckIn(j))))
      .catch(() => setStale([]));
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 60_000);
    return () => window.clearInterval(timer);
  }, [load]);

  const c = data?.counts;
  // View-only staff see Today + Care only; sales tiles would lead to pages they cannot use.
  const edit = can("edit");
  const openSos = data ? data.alerts.filter((a) => a.kind === "sos_button" || a.kind === "family_sos").length : undefined;
  const missedOrLate = data ? (data.missed?.length ?? 0) + stale.length : undefined;
  const tiles: Tile[] = [
    { href: "/kushalaya/alerts", label: "Open SOS", value: openSos, icon: ICON.phone, tone: "is-red" },
    { href: "/kushalaya/visits?tab=today", label: "Visits today", value: c?.visits_today, icon: ICON.visits, tone: "is-green" },
    { href: "/kushalaya/visits?tab=past", label: "Missed or late", value: missedOrLate, icon: ICON.visits, tone: "is-red" },
    { href: "/kushalaya/messages?filter=unread", label: "Unread messages", value: c?.unread_messages, icon: ICON.heart, tone: "" },
    { href: "/kushalaya/customers?filter=reassessment", label: "Assessments due", value: c?.reassessments, icon: ICON.assessments, tone: "is-gold" },
    ...(edit
      ? [
          { href: "/kushalaya/enquiries?stage=NEW", label: "New leads", value: sales?.leads.NEW, icon: ICON.clients, tone: "is-gold" },
          { href: "/kushalaya/customers?status=pending_approval", label: "Pending approval", value: sales?.pending_approval, icon: ICON.assessments, tone: "is-navy" },
          { href: "/kushalaya/customers?status=unpaid", label: "Unpaid plans", value: sales?.unpaid_plans, icon: ICON.assessments, tone: "is-navy" },
        ]
      : []),
  ];

  const who = data?.viewer?.first_name || firstNameFromEmail(auth?.email || "");

  return (
    <>
      <section className="ko-hero dash-hero" aria-label={t("pages.dashboard.title")}>
        <div>
          <p className="ko-hero-kicker">{greetingIST()}</p>
          <h1>{who ? `Hello, ${who}` : t("pages.dashboard.title")}</h1>
        </div>
      </section>

      <SmsOffBanner />


      {failed ? (
        <p className="dash-error" role="alert">
          Could not load today&apos;s counts.
          <button type="button" className="dash-act" onClick={load}>
            Retry
          </button>
        </p>
      ) : null}

      <div className="dash-action-grid dash-tiles">
        {tiles.map((tile) => (
          <Link key={tile.label} href={tile.href} className={`dash-action-card${tile.value === 0 ? " is-zero" : ""}`}>
            <span className={`dash-action-ico ${tile.tone}`}>{tile.icon}</span>
            <span className="dash-action-count">{tile.value ?? "—"}</span>
            <span className="dash-action-title">{tile.label}</span>
          </Link>
        ))}
      </div>
    </>
  );
}

type Tile = { href: string; label: string; value: number | undefined; icon: JSX.Element; tone: string };
