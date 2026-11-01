"use client";

import { fetchBackupStatus } from "@/lib/livewell/privacyApi";
import { getBusinessDetails } from "@/lib/business";
import Link from "next/link";
import "@/components/ops/settings.css";
import { FormEvent, useEffect, useState } from "react";
import { api, getStoredAuth } from "@/lib/api";
import { canAccessSettings, canManageTenantBranding, canManageTenants, canManageUsers } from "@/lib/auth";
import { fetchThemes, updateBranding, type ThemeOption } from "@/lib/branding";
import { useBranding, useBrandingRefresh } from "@/components/BrandingProvider";
import { CustomFieldBuilder } from "@/components/CustomFieldBuilder";
import {
  fetchFieldSchemas,
  schemasFromBranding,
  updateFieldSchemas,
  type CustomFieldDef,
} from "@/lib/customFields";
import { Flash } from "@/components/Flash";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { TranslatedPageHeader } from "@/components/TranslatedPageHeader";
import { PageHeader } from "@/components/PageHeader";
import { canOpen } from "@/lib/roles";
import { ThemePicker } from "@/components/ThemePicker";
import { useTranslation } from "@/lib/i18n/context";
import { normalizeMarket } from "@/lib/markets";
import { verticalHasFeature } from "@/lib/features";
import {
  demandEntityLabel,
  supplyEntityLabel,
} from "@/lib/terminology";
import { verticalNavLayout } from "@/lib/verticalUx";
import { publicBrandName } from "@/lib/public-brand";
import { navIcon } from "@/components/ops/OpsShell";
import { useRouter } from "next/navigation";
import {
  fetchPlatformModules,
  type PlatformModule,
} from "@/lib/platform-modules";

function parseBenchCost(value: string): number | null {
  const cost = Number(value);
  if (!Number.isFinite(cost) || cost < 1000 || cost > 1_000_000) {
    return null;
  }
  return cost;
}

/**
 * Kushalaya Settings: set-up pages only, as tiles. Pages with their own menu
 * item (Team, Hiring, Alerts, Assessments, Owner dashboard, Invoices) are not
 * repeated here. Tile names are the page titles; icons come from the menu set.
 */
const SETTINGS_TILES = [
  { href: "/settings/notifications", title: "Notifications & SOS", blurb: "Who gets alerts and SOS calls" },
  { href: "/settings/website", title: "Website", blurb: "Areas, prices, banner and footer" },
  { href: "/settings/business", title: "Business details", blurb: "Legal name, GSTIN and invoice codes", adminOnly: true },
  { href: "/settings/privacy", title: "Privacy & backups", blurb: "Data-delete requests and nightly backup", adminOnly: true },
  { href: "/settings/security", title: "Security", blurb: "Sessions don't time out when idle", adminOnly: true },
  { href: "/kushalaya/activity", title: "Activity log", blurb: "Who signed in and what changed" },
];

export default function SettingsPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const auth = getStoredAuth();
  const branding = useBranding();
  const refreshBranding = useBrandingRefresh();
  const showClientProfiles =
    verticalHasFeature(branding.vertical, "elders") ||
    verticalHasFeature(branding.vertical, "customer_spine");
  // nav.json maps both LIVEWELL360 and SAFEHOME360 to the "livewell360" layout,
  // so a check for "safehome360" alone was always false and the platform-only
  // cards (module maturity, workflows, bench economics) leaked onto Kushalaya.
  const navLayout = verticalNavLayout(branding.vertical);
  const isSafeHome =
    navLayout === "livewell360" ||
    navLayout === "safehome360" ||
    verticalHasFeature(branding.vertical, "livewell");
  const demandLabel = demandEntityLabel(branding.vertical, branding.market);
  const supplyLabel = supplyEntityLabel(branding.vertical, branding.market);
  const manageBranding = canManageTenantBranding(auth?.role || "");
  const [themes, setThemes] = useState<ThemeOption[]>([]);
  const [selectedTheme, setSelectedTheme] = useState(branding.theme);
  const [portalTitle, setPortalTitle] = useState(branding.portal_title);
  const [logoUrl, setLogoUrl] = useState(branding.logo_url || "");
  const [benchCost, setBenchCost] = useState(
    String(branding.bench_cost_per_caregiver_month_inr ?? 15_000),
  );
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  // Status on the hub tiles, so missing setup is visible without opening each page.
  const [tileStatus, setTileStatus] = useState<Record<string, { text: string; tone: "ok" | "warn" }>>({});
  useEffect(() => {
    const put = (href: string, text: string, tone: "ok" | "warn") =>
      setTileStatus((prev) => ({ ...prev, [href]: { text, tone } }));
    api<{ sms_connected: boolean }>("/api/v1/team/channels/status")
      .then((st) => put("/settings/notifications", st.sms_connected ? "SMS: On" : "SMS: Off", st.sms_connected ? "ok" : "warn"))
      .catch(() => undefined);
    if (!canManageUsers(getStoredAuth()?.role || "")) return;
    fetchBackupStatus()
      .then((b) => put("/settings/privacy", b.configured ? (b.ok ? "Backups: OK" : "Backups: failing") : "Backups: Not set up", b.configured && b.ok ? "ok" : "warn"))
      .catch(() => undefined);
    getBusinessDetails()
      .then((d) => (d.gstin?.trim() ? put("/settings/business", "GSTIN set", "ok") : put("/settings/business", "GSTIN missing", "warn")))
      .catch(() => undefined);
  }, []);
  const [previewTheme, setPreviewTheme] = useState(branding.theme);
  const [elderFields, setElderFields] = useState<CustomFieldDef[]>([]);
  const [caregiverFields, setCaregiverFields] = useState<CustomFieldDef[]>([]);
  const [fieldTab, setFieldTab] = useState<"elder" | "caregiver">(
    showClientProfiles ? "elder" : "caregiver",
  );
  const [modules, setModules] = useState<PlatformModule[]>([]);

  useEffect(() => {
    if (!canAccessSettings(auth?.role || "")) {
      router.replace("/unauthorized");
      return;
    }
    fetchPlatformModules()
      .then(setModules)
      .catch(() => setModules([]));
    if (manageBranding) {
      fetchThemes().then(setThemes);
      fetchFieldSchemas()
        .then((s) => {
          setElderFields(s.elder_fields);
          setCaregiverFields(s.caregiver_fields);
        })
        .catch(() => {
          const s = schemasFromBranding(branding);
          setElderFields(s.elder_fields);
          setCaregiverFields(s.caregiver_fields);
        });
    }
  }, [auth?.role, router, branding, manageBranding]);

  useEffect(() => {
    setSelectedTheme(branding.theme);
    setPortalTitle(branding.portal_title);
    setLogoUrl(branding.logo_url || "");
    setBenchCost(String(branding.bench_cost_per_caregiver_month_inr ?? 15_000));
    setPreviewTheme(branding.theme);
  }, [branding]);

  function handlePreviewTheme(id: string) {
    setPreviewTheme(id);
    document.documentElement.setAttribute("data-theme", id);
  }

  async function onSaveEconomics(e: FormEvent) {
    e.preventDefault();
    setError("");
    const cost = parseBenchCost(benchCost);
    if (cost === null) {
      setError("Bench cost must be between ₹1,000 and ₹10,00,000 per month.");
      return;
    }
    try {
      const result = await updateBranding({
        bench_cost_per_caregiver_month_inr: cost,
      });
      await refreshBranding();
      setMessage(
        `Bench cost saved: ₹${result.bench_cost_per_caregiver_month_inr?.toLocaleString("en-IN")}/month per caregiver.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  }

  async function onSaveBranding(e: FormEvent) {
    e.preventDefault();
    setError("");
    const cost = isSafeHome ? undefined : parseBenchCost(benchCost);
    if (!isSafeHome && cost === null) {
      setError("Bench cost must be between ₹1,000 and ₹10,00,000 per month.");
      return;
    }
    try {
      const result = await updateBranding({
        theme: selectedTheme,
        portal_title: portalTitle || null,
        logo_url: logoUrl.trim() || null,
        ...(cost != null ? { bench_cost_per_caregiver_month_inr: cost } : {}),
      });
      await refreshBranding();
      setMessage(
        isSafeHome
          ? "Settings saved (theme and branding)."
          : `Settings saved (theme, branding, bench cost ₹${result.bench_cost_per_caregiver_month_inr?.toLocaleString("en-IN")}/mo).`,
      );
      setPreviewTheme(selectedTheme);
    } catch (err) {
      document.documentElement.setAttribute("data-theme", branding.theme);
      setError(err instanceof Error ? err.message : "Save failed");
    }
  }

  function onCancelPreview() {
    setSelectedTheme(branding.theme);
    setPreviewTheme(branding.theme);
    document.documentElement.setAttribute("data-theme", branding.theme);
  }

  return (
    <>
      {canManageUsers(auth?.role || "") ? (
        <TranslatedPageHeader pageKey="settings" />
      ) : (
        <PageHeader title={t("pages.settings.title")} subtitle={t("pages.settings.subtitleManager")} />
      )}
      <Flash error={error} message={message} onClear={() => { setError(""); setMessage(""); }} />
      {isSafeHome ? (
        <>
          {!canManageUsers(auth?.role || "") && (
            <p className="card st-viewonly" role="note">
              <strong>View only.</strong> These are the current settings.
            </p>
          )}
          <ul className="st-grid">
            {SETTINGS_TILES.filter((t) => canOpen(t.href)).map((t) => (
              <li key={t.href}>
                <Link href={t.href} className="st-tile">
                  <span className="st-tile-head">
                    <span className="st-ico" aria-hidden="true">{navIcon(t.href)}</span>
                    <strong>{t.title}</strong>
                  </span>
                  <span className="st-desc">{t.blurb}</span>
                  {tileStatus[t.href] ? (
                    <em className={`st-status is-${tileStatus[t.href].tone}`}>{tileStatus[t.href].text}</em>
                  ) : null}
                </Link>
              </li>
            ))}
          </ul>
          <div className="card st-lang">
            <span className="st-ico" aria-hidden="true">{navIcon("/settings/language")}</span>
            <div>
              <h2>{t("settings.languageSection")}</h2>
              <p className="muted">{t("common.languageHint")}</p>
            </div>
            <LocaleSwitcher />
          </div>
        </>
      ) : (
        <>
          <div className="card" style={{ marginBottom: "1rem" }}>
            <h2>Workflow automation</h2>
            <p className="muted" style={{ marginBottom: "0.75rem" }}>
              Configure platform workflows, review open tasks, and run compliance scans.
            </p>
            <Link href="/settings/workflows">Manage workflows →</Link>
          </div>
        </>
      )}

      {modules.length > 0 && !isSafeHome && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h2>WorkforceOS platform</h2>
          <p className="muted" style={{ marginBottom: "0.75rem" }}>
            Module maturity across WorkforceOS platform modules.
          </p>
          <table className="table">
            <thead>
              <tr>
                <th>Module</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {modules.map((m) => (
                <tr key={m.id}>
                  <td>
                    <strong>{m.label}</strong>
                    <div className="muted" style={{ fontSize: "0.8rem" }}>
                      {m.description}
                    </div>
                  </td>
                  <td>{m.maturity}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ marginTop: "0.75rem" }}>
            <Link href="/scheduling">Scheduling (auto-schedule) →</Link>
          </p>
        </div>
      )}

      {!isSafeHome && normalizeMarket(branding.market) !== "US" && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h2>{t("settings.languageSection")}</h2>
          <p className="muted" style={{ fontSize: "0.85rem", marginBottom: "0.75rem" }}>
            {t("common.languageHint")}
          </p>
          <LocaleSwitcher />
        </div>
      )}

      {/* Kushalaya uses one fixed brand mark, so no title / logo fields here. */}
      {!isSafeHome && (
      <form onSubmit={manageBranding ? onSaveBranding : onSaveEconomics}>
        {!isSafeHome && (
          <div className="card" style={{ marginBottom: "1rem" }}>
            <h2>{t("settings.workforceEconomics")}</h2>
            <div>
              <label>{t("settings.benchCostLabel")}</label>
              <input
                type="number"
                min={1000}
                max={1000000}
                step={500}
                value={benchCost}
                onChange={(e) => setBenchCost(e.target.value)}
                style={{ maxWidth: "16rem" }}
              />
              <p className="muted" style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
                {t("settings.benchCostHint")}
              </p>
            </div>
          </div>
        )}

        {manageBranding && (
          <>
            <div className="card" style={{ marginBottom: "1rem" }}>
              <h2>{t("settings.brandingSection")}</h2>
              <div className="grid-2">
                <div>
                  <label>Portal title</label>
                  <input
                    value={portalTitle}
                    onChange={(e) => setPortalTitle(e.target.value)}
                    placeholder={publicBrandName()}
                  />
                  <p className="muted" style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
                    Shown in the sidebar when no logo is set
                  </p>
                </div>
                <div>
                  <label>Logo URL</label>
                  <input
                    value={logoUrl}
                    onChange={(e) => setLogoUrl(e.target.value)}
                    placeholder="https://example.com/logo.png"
                  />
                  <p className="muted" style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
                    PNG or SVG recommended, max height ~40px
                  </p>
                </div>
              </div>
            </div>
          </>
        )}

        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button type="submit">
            {manageBranding ? t("settings.saveBranding") : t("settings.saveBenchCost")}
          </button>
        </div>
      </form>
      )}
    </>
  );
}
