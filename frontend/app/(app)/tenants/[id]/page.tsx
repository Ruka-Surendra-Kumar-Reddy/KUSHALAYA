"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getStoredAuth } from "@/lib/api";
import { canManageTenants } from "@/lib/auth";
import { fetchThemes, type ThemeOption } from "@/lib/branding";
import {
  deleteTenant,
  fetchTenant,
  fetchTenantBranding,
  fetchTenantFieldSchemas,
  fetchMarkets,
  fetchVerticals,
  updateTenant,
  updateTenantBranding,
  updateTenantFieldSchemas,
} from "@/lib/tenants";
import {
  DEFAULT_VERTICAL,
  normalizeVertical,
  type VerticalId,
} from "@/lib/platform";
import type { MarketInfo } from "@/lib/markets";
import type { VerticalInfo } from "@/lib/types";
import type { CustomFieldDef } from "@/lib/customFields";
import { CustomFieldBuilder } from "@/components/CustomFieldBuilder";
import { Flash } from "@/components/Flash";
import { PageHeader } from "@/components/PageHeader";
import { ThemePicker } from "@/components/ThemePicker";
import type { Tenant } from "@/lib/types";
import {
  assignTenantSubscription,
  fetchSubscriptionInvoices,
  fetchSubscriptionPlans,
  fetchTenantSubscription,
  generateSubscriptionInvoice,
  issueSubscriptionInvoice,
  recordSubscriptionPayment,
  type SubscriptionInvoice,
  type SubscriptionPlan,
  type TenantSubscription,
} from "@/lib/subscriptions";

export default function EditTenantPage() {
  const params = useParams();
  const router = useRouter();
  const auth = getStoredAuth();
  const tenantId = Number(params.id);

  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [themes, setThemes] = useState<ThemeOption[]>([]);
  const [verticals, setVerticals] = useState<VerticalInfo[]>([]);
  const [markets, setMarkets] = useState<MarketInfo[]>([]);
  const [profile, setProfile] = useState<{
    name: string;
    email: string;
    phone: string;
    address: string;
    city: string;
    state: string;
    country: string;
    market: string;
    status: string;
    vertical: VerticalId;
  }>({
    name: "",
    email: "",
    phone: "",
    address: "",
    city: "",
    state: "",
    country: "India",
    market: "IN",
    status: "ACTIVE",
    vertical: DEFAULT_VERTICAL,
  });
  const [portalTitle, setPortalTitle] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [benchCost, setBenchCost] = useState("15000");
  const [selectedTheme, setSelectedTheme] = useState("classic");
  const [previewTheme, setPreviewTheme] = useState("classic");
  const [elderFields, setElderFields] = useState<CustomFieldDef[]>([]);
  const [caregiverFields, setCaregiverFields] = useState<CustomFieldDef[]>([]);
  const [fieldTab, setFieldTab] = useState<"elder" | "caregiver">("elder");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [deleteConfirmName, setDeleteConfirmName] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [subscription, setSubscription] = useState<TenantSubscription | null>(null);
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [subInvoices, setSubInvoices] = useState<SubscriptionInvoice[]>([]);
  const [planCode, setPlanCode] = useState("STARTER");
  const [subStatus, setSubStatus] = useState("ACTIVE");
  const [invPeriod, setInvPeriod] = useState({ start: "", end: "" });

  useEffect(() => {
    if (!canManageTenants(auth?.role || "")) {
      router.replace("/unauthorized");
      return;
    }
    if (!tenantId) return;

    const now = new Date();
    const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
    setInvPeriod({
      start: monthStart.toISOString().slice(0, 10),
      end: now.toISOString().slice(0, 10),
    });

    Promise.all([
      fetchTenant(tenantId),
      fetchTenantBranding(tenantId),
      fetchTenantFieldSchemas(tenantId),
      fetchThemes(),
      fetchVerticals(),
      fetchMarkets(),
      fetchSubscriptionPlans(),
      fetchTenantSubscription(tenantId).catch(() => null),
      fetchSubscriptionInvoices(tenantId).catch(() => []),
    ])
      .then(([t, branding, schemas, themeList, verticalList, marketList, planList, sub, invs]) => {
        setTenant(t);
        setThemes(themeList);
        setVerticals(verticalList);
        setMarkets(marketList);
        setProfile({
          name: t.name,
          email: t.email,
          phone: t.phone,
          address: t.address,
          city: t.city,
          state: t.state,
          country: t.country || "India",
          market: t.market || branding.market || "IN",
          status: t.status,
          vertical: normalizeVertical(t.vertical),
        });
        setPortalTitle(branding.portal_title || t.name);
        setLogoUrl(branding.logo_url || "");
        setBenchCost(
          String(branding.bench_cost_per_caregiver_month_inr ?? 15_000),
        );
        setSelectedTheme(branding.theme || t.theme || "classic");
        setPreviewTheme(branding.theme || t.theme || "classic");
        setElderFields(branding.elder_field_schema || schemas.elder_fields);
        setCaregiverFields(
          branding.caregiver_field_schema || schemas.caregiver_fields,
        );
        setPlans(planList);
        setSubscription(sub);
        setSubInvoices(invs);
        if (sub) {
          setPlanCode(sub.plan.code);
          setSubStatus(sub.status);
        }
      })
      .catch((e) => setError(String(e)));
  }, [tenantId, auth?.role, router]);

  function handlePreviewTheme(id: string) {
    setPreviewTheme(id);
    document.documentElement.setAttribute("data-theme", id);
  }

  async function onSaveAll(e: FormEvent) {
    e.preventDefault();
    if (!tenantId) return;
    setError("");
    try {
      const cost = Number(benchCost);
      if (!Number.isFinite(cost) || cost < 1000 || cost > 1_000_000) {
        setError("Bench cost must be between ₹1,000 and ₹10,00,000 per month.");
        return;
      }
      await updateTenant(tenantId, profile);
      await updateTenantBranding(tenantId, {
        theme: selectedTheme,
        portal_title: portalTitle || null,
        logo_url: logoUrl.trim() || null,
        bench_cost_per_caregiver_month_inr: cost,
      });
      await updateTenantFieldSchemas(tenantId, {
        elder_fields: elderFields,
        caregiver_fields: caregiverFields,
      });
      const refreshed = await fetchTenant(tenantId);
      setTenant(refreshed);
      setMessage("Tenant updated (profile, branding, and custom fields)");
      setPreviewTheme(selectedTheme);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  }

  if (!tenant) return <p>Loading…</p>;

  return (
    <>
      <PageHeader
        title={`Edit tenant · ${tenant.name}`}
        subtitle="Agency profile, portal branding, and custom elder/caregiver fields"
        action={
          <Link href="/tenants">
            <button type="button" className="secondary">
              Back to tenants
            </button>
          </Link>
        }
      />
      <Flash
        error={error}
        message={message}
        onClear={() => {
          setError("");
          setMessage("");
        }}
      />

      <form onSubmit={onSaveAll}>
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h2>Agency profile</h2>
          <div className="grid-2">
            <div>
              <label>Name</label>
              <input
                value={profile.name}
                onChange={(e) =>
                  setProfile({ ...profile, name: e.target.value })
                }
                required
              />
            </div>
            <div>
              <label>Status</label>
              <select
                value={profile.status}
                onChange={(e) =>
                  setProfile({ ...profile, status: e.target.value })
                }
              >
                <option value="ACTIVE">Active</option>
                <option value="INACTIVE">Inactive</option>
              </select>
            </div>
            <div>
              <label>Industry vertical</label>
              <select
                value={profile.vertical}
                onChange={(e) =>
                  setProfile({
                    ...profile,
                    vertical: normalizeVertical(e.target.value),
                  })
                }
              >
                {verticals.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.label}
                  </option>
                ))}
              </select>
              <p className="muted" style={{ fontSize: "0.8rem", marginTop: "0.35rem" }}>
                {verticals.find((v) => v.id === profile.vertical)?.description}
              </p>
            </div>
            <div>
              <label>Market</label>
              <select
                value={profile.market}
                onChange={(e) =>
                  setProfile({
                    ...profile,
                    market: e.target.value,
                    country:
                      e.target.value === "US" ? "United States" : profile.country,
                  })
                }
              >
                {markets.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label} ({m.currency})
                  </option>
                ))}
              </select>
              <p className="muted" style={{ fontSize: "0.8rem", marginTop: "0.35rem" }}>
                Controls payroll regime, tax defaults, and subscription currency.
              </p>
            </div>
            <div>
              <label>Country</label>
              <input
                value={profile.country}
                onChange={(e) =>
                  setProfile({ ...profile, country: e.target.value })
                }
                required
              />
            </div>
            <div>
              <label>Email</label>
              <input
                type="email"
                value={profile.email}
                onChange={(e) =>
                  setProfile({ ...profile, email: e.target.value })
                }
                required
              />
            </div>
            <div>
              <label>Phone</label>
              <input
                value={profile.phone}
                onChange={(e) =>
                  setProfile({ ...profile, phone: e.target.value })
                }
                required
              />
            </div>
            <div>
              <label>City</label>
              <input
                value={profile.city}
                onChange={(e) =>
                  setProfile({ ...profile, city: e.target.value })
                }
                required
              />
            </div>
            <div>
              <label>State</label>
              <input
                value={profile.state}
                onChange={(e) =>
                  setProfile({ ...profile, state: e.target.value })
                }
                required
              />
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <label>Address</label>
              <input
                value={profile.address}
                onChange={(e) =>
                  setProfile({ ...profile, address: e.target.value })
                }
                required
              />
            </div>
          </div>
        </div>

        <div className="card" style={{ marginBottom: "1rem" }}>
          <h2>Workforce economics</h2>
          <p className="muted" style={{ marginBottom: "0.75rem" }}>
            Monthly bench carrying cost per caregiver (INR) for Executive Command Center.
          </p>
          <div>
            <label>Bench cost per caregiver (₹ / month)</label>
            <input
              type="number"
              min={1000}
              max={1000000}
              step={500}
              value={benchCost}
              onChange={(e) => setBenchCost(e.target.value)}
              style={{ maxWidth: "16rem" }}
            />
          </div>
        </div>

        <div className="card" style={{ marginBottom: "1rem" }}>
          <h2>Portal branding</h2>
          <p className="muted" style={{ marginBottom: "1rem" }}>
            Theme and logo apply to this agency&apos;s admin and elder portals.
          </p>
          <div className="grid-2" style={{ marginBottom: "1rem" }}>
            <div>
              <label>Portal title</label>
              <input
                value={portalTitle}
                onChange={(e) => setPortalTitle(e.target.value)}
                placeholder={tenant.name}
              />
            </div>
            <div>
              <label>Logo URL</label>
              <input
                value={logoUrl}
                onChange={(e) => setLogoUrl(e.target.value)}
                placeholder="https://example.com/logo.png"
              />
              {logoUrl && (
                <img
                  src={logoUrl}
                  alt="Logo preview"
                  className="brand-logo"
                  style={{ marginTop: "0.5rem" }}
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = "none";
                  }}
                />
              )}
            </div>
          </div>
          {themes.length > 0 && (
            <>
              <h3 style={{ marginBottom: "0.5rem" }}>Color theme</h3>
              <ThemePicker
                themes={themes}
                selected={previewTheme}
                onSelect={(id) => {
                  setSelectedTheme(id);
                  handlePreviewTheme(id);
                }}
              />
            </>
          )}
        </div>

        <div className="card" style={{ marginBottom: "1rem" }}>
          <h2>Custom profile fields</h2>
          <p className="muted" style={{ marginBottom: "1rem" }}>
            Extra attributes on client (demand) and worker (supply) profile forms.
            API aliases: <code>demand_fields</code> / <code>supply_fields</code>.
          </p>
          <div className="tabs" style={{ marginBottom: "1rem" }}>
            <button
              type="button"
              className={`tab ${fieldTab === "elder" ? "active" : ""}`}
              onClick={() => setFieldTab("elder")}
            >
              Elder attributes
            </button>
            <button
              type="button"
              className={`tab ${fieldTab === "caregiver" ? "active" : ""}`}
              onClick={() => setFieldTab("caregiver")}
            >
              Caregiver attributes
            </button>
          </div>
          {fieldTab === "elder" ? (
            <CustomFieldBuilder
              entityLabel="elder"
              fields={elderFields}
              onSave={async (fields) => {
                setElderFields(fields);
                setMessage(
                  "Elder fields updated in form — click Save all below to persist",
                );
              }}
            />
          ) : (
            <CustomFieldBuilder
              entityLabel="caregiver"
              fields={caregiverFields}
              onSave={async (fields) => {
                setCaregiverFields(fields);
                setMessage(
                  "Caregiver fields updated in form — click Save all below to persist",
                );
              }}
            />
          )}
          <p className="muted" style={{ fontSize: "0.85rem", marginTop: "0.5rem" }}>
            Use &quot;Add field&quot; above, then <strong>Save all changes</strong> to
            write custom attributes to the tenant.
          </p>
        </div>

        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button type="submit">Save all changes</button>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setSelectedTheme(tenant.theme || "classic");
              setPreviewTheme(tenant.theme || "classic");
              document.documentElement.setAttribute(
                "data-theme",
                tenant.theme || "classic",
              );
            }}
          >
            Reset theme preview
          </button>
        </div>
      </form>

      <section className="card" style={{ marginTop: "2rem" }}>
        <h2>Platform subscription</h2>
        {subscription ? (
          <p style={{ marginBottom: "0.75rem" }}>
            <strong>{subscription.plan.name}</strong> ({subscription.status}) ·{" "}
            {subscription.active_workers} active caregivers
          </p>
        ) : (
          <p className="muted">No subscription — assign a plan below.</p>
        )}
        <div className="grid-2" style={{ marginBottom: "0.75rem" }}>
          <label>
            Plan
            <select value={planCode} onChange={(e) => setPlanCode(e.target.value)}>
              {plans.map((p) => (
                <option key={p.code} value={p.code}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Status
            <select value={subStatus} onChange={(e) => setSubStatus(e.target.value)}>
              <option value="TRIAL">TRIAL</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="PAST_DUE">PAST_DUE</option>
              <option value="SUSPENDED">SUSPENDED</option>
              <option value="CANCELLED">CANCELLED</option>
            </select>
          </label>
        </div>
        <button
          type="button"
          className="secondary"
          onClick={async () => {
            const sub = await assignTenantSubscription(tenantId, {
              plan_code: planCode,
              status: subStatus,
            });
            setSubscription(sub);
            setMessage("Subscription updated");
          }}
        >
          Save subscription
        </button>

        <h3 style={{ marginTop: "1.25rem" }}>Generate platform invoice</h3>
        <div className="grid-2">
          <label>
            Period start
            <input
              type="date"
              value={invPeriod.start}
              onChange={(e) =>
                setInvPeriod((p) => ({ ...p, start: e.target.value }))
              }
            />
          </label>
          <label>
            Period end
            <input
              type="date"
              value={invPeriod.end}
              onChange={(e) =>
                setInvPeriod((p) => ({ ...p, end: e.target.value }))
              }
            />
          </label>
        </div>
        <button
          type="button"
          style={{ marginTop: "0.5rem" }}
          onClick={async () => {
            const inv = await generateSubscriptionInvoice({
              tenant_id: tenantId,
              period_start: invPeriod.start,
              period_end: invPeriod.end,
            });
            setSubInvoices((prev) => [inv, ...prev]);
            setMessage(`Draft invoice ₹${inv.total_amount.toFixed(0)}`);
          }}
        >
          Generate invoice
        </button>

        {subInvoices.length > 0 && (
          <table className="table" style={{ marginTop: "1rem" }}>
            <thead>
              <tr>
                <th>Period</th>
                <th>Total</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {subInvoices.map((inv) => (
                <tr key={inv.id}>
                  <td>
                    {inv.period_start} – {inv.period_end}
                    <br />
                    <span className="muted" style={{ fontSize: "0.8rem" }}>
                      {inv.line_description}
                    </span>
                  </td>
                  <td>₹{inv.total_amount.toFixed(0)}</td>
                  <td>{inv.status}</td>
                  <td>
                    {inv.status === "DRAFT" && (
                      <button
                        type="button"
                        className="link-button"
                        onClick={async () => {
                          const issued = await issueSubscriptionInvoice(inv.id);
                          setSubInvoices((rows) =>
                            rows.map((r) => (r.id === inv.id ? issued : r)),
                          );
                          setMessage("Invoice issued");
                        }}
                      >
                        Issue
                      </button>
                    )}
                    {inv.status === "ISSUED" && (
                      <button
                        type="button"
                        className="link-button"
                        onClick={async () => {
                          const paid = await recordSubscriptionPayment(
                            inv.id,
                            inv.total_amount - inv.amount_paid,
                            "Admin payment",
                          );
                          setSubInvoices((rows) =>
                            rows.map((r) => (r.id === inv.id ? paid : r)),
                          );
                          setMessage("Payment recorded");
                        }}
                      >
                        Mark paid
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section
        id="purge"
        className="card"
        style={{
          marginTop: "2rem",
          borderColor: "var(--danger, #c62828)",
        }}
      >
        <h2 style={{ color: "var(--danger, #c62828)" }}>Delete agency (pilot cleanup)</h2>
        <p className="muted">
          Permanently removes this agency, all users, clients, assessments, visits,
          billing, and assessment documents. Cannot be undone. Demo tenant{" "}
          <strong>Sunrise Elder Care</strong> is protected.
        </p>
        <p className="muted">
          Shared product catalog and product photos are global and are{" "}
          <strong>not</strong> deleted.
        </p>
        {tenant && (
          <>
            <label htmlFor="delete-confirm-name">
              Type <strong>{tenant.name}</strong> to confirm
            </label>
            <input
              id="delete-confirm-name"
              type="text"
              value={deleteConfirmName}
              onChange={(e) => setDeleteConfirmName(e.target.value)}
              placeholder={tenant.name}
              autoComplete="off"
              style={{ maxWidth: "24rem", display: "block", marginTop: "0.5rem" }}
            />
            <button
              type="button"
              style={{
                marginTop: "1rem",
                background: "var(--danger, #c62828)",
                color: "#fff",
              }}
              disabled={
                deleting || deleteConfirmName !== tenant.name
              }
              onClick={async () => {
                if (
                  !window.confirm(
                    `Delete "${tenant.name}" and ALL its data? This cannot be undone.`,
                  )
                ) {
                  return;
                }
                setDeleting(true);
                setError("");
                try {
                  const result = await deleteTenant(tenantId, deleteConfirmName);
                  const total = Object.values(result.deleted_counts).reduce(
                    (a, b) => a + b,
                    0,
                  );
                  router.replace(
                    `/tenants?deleted=${encodeURIComponent(tenant.name)}&rows=${total}`,
                  );
                } catch (e) {
                  setError(String(e));
                } finally {
                  setDeleting(false);
                }
              }}
            >
              {deleting ? "Deleting…" : "Delete agency and all data"}
            </button>
          </>
        )}
      </section>
    </>
  );
}
