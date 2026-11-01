"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getStoredAuth } from "@/lib/api";
import { canManageTenants } from "@/lib/auth";
import { Flash } from "@/components/Flash";
import { TranslatedPageHeader } from "@/components/TranslatedPageHeader";
import { DEFAULT_MARKET } from "@/lib/markets";
import { fetchMarkets, fetchVerticals } from "@/lib/tenants";
import type { MarketInfo } from "@/lib/markets";
import type { Tenant, VerticalInfo } from "@/lib/types";
import {
  DEFAULT_VERTICAL,
  normalizeVertical,
  type VerticalId,
} from "@/lib/platform";

export default function TenantsPage() {
  const router = useRouter();
  const auth = getStoredAuth();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [verticals, setVerticals] = useState<VerticalInfo[]>([]);
  const [markets, setMarkets] = useState<MarketInfo[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [form, setForm] = useState<{
    name: string;
    email: string;
    phone: string;
    address: string;
    city: string;
    state: string;
    country: string;
    market: string;
    theme: string;
    vertical: VerticalId;
    admin_email: string;
    admin_password: string;
    admin_first_name: string;
    admin_last_name: string;
  }>({
    name: "",
    email: "",
    phone: "",
    address: "",
    city: "",
    state: "",
    country: "India",
    market: DEFAULT_MARKET,
    theme: "classic",
    vertical: DEFAULT_VERTICAL,
    admin_email: "",
    admin_password: "",
    admin_first_name: "",
    admin_last_name: "",
  });

  useEffect(() => {
    if (!canManageTenants(auth?.role || "")) {
      router.replace("/unauthorized");
      return;
    }
    load().catch((e) => setError(String(e)));
  }, [auth?.role, router]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const deleted = params.get("deleted");
    const rows = params.get("rows");
    if (deleted) {
      setMessage(
        rows
          ? `Purged agency "${deleted}" (${rows} related rows removed). Global product catalog and photos were kept.`
          : `Purged agency "${deleted}". Global product catalog and photos were kept.`,
      );
      router.replace("/tenants", { scroll: false });
    }
  }, [router]);

  async function load() {
    const [tenantList, verticalList, marketList] = await Promise.all([
      api<Tenant[]>("/api/v1/tenants"),
      fetchVerticals(),
      fetchMarkets(),
    ]);
    setTenants(tenantList);
    setVerticals(verticalList);
    setMarkets(marketList);
  }

  function verticalLabel(id: string | undefined) {
    return verticals.find((v) => v.id === id)?.label ?? id ?? DEFAULT_VERTICAL;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const payload: Record<string, unknown> = {
        name: form.name,
        email: form.email,
        phone: form.phone,
        address: form.address,
        city: form.city,
        state: form.state,
        country: form.country,
        market: form.market,
        theme: form.theme,
        vertical: form.vertical,
      };
      if (form.admin_email.trim()) {
        payload.admin_email = form.admin_email;
        payload.admin_password = form.admin_password;
        payload.admin_first_name = form.admin_first_name;
        payload.admin_last_name = form.admin_last_name;
      }
      await api("/api/v1/tenants", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setMessage("Tenant created");
      setForm({
        name: "",
        email: "",
        phone: "",
        address: "",
        city: "",
        state: "",
        country: "India",
        market: DEFAULT_MARKET,
        theme: "classic",
        vertical: DEFAULT_VERTICAL,
        admin_email: "",
        admin_password: "",
        admin_first_name: "",
        admin_last_name: "",
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  async function setTenantStatus(tenant: Tenant, status: string) {
    setError("");
    try {
      await api(`/api/v1/tenants/${tenant.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setMessage(`${tenant.name} set to ${status}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    }
  }

  if (!canManageTenants(auth?.role || "")) {
    return null;
  }

  return (
    <>
      <TranslatedPageHeader pageKey="tenants" />
      <Flash
        error={error}
        message={message}
        onClear={() => {
          setError("");
          setMessage("");
        }}
      />
      <div className="card" style={{ marginBottom: "1rem" }}>
        <h2>Create tenant</h2>
        <p className="muted" style={{ marginBottom: "1rem" }}>
          Optionally create the first tenant admin in the same step.
        </p>
        <form onSubmit={onSubmit} className="grid-2">
          <div>
            <label>Agency name</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </div>
          <div>
            <label>Agency email</label>
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
            />
          </div>
          <div>
            <label>Phone</label>
            <input
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              required
            />
          </div>
          <div>
            <label>Industry vertical</label>
            <select
              value={form.vertical}
              onChange={(e) =>
                setForm({
                  ...form,
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
              {verticals.find((v) => v.id === form.vertical)?.description}
            </p>
          </div>
          <div>
            <label>Theme</label>
            <select
              value={form.theme}
              onChange={(e) => setForm({ ...form, theme: e.target.value })}
            >
              <option value="classic">Classic</option>
              <option value="ocean">Ocean</option>
              <option value="warm">Warm</option>
            </select>
          </div>
          <div>
            <label>City</label>
            <input
              value={form.city}
              onChange={(e) => setForm({ ...form, city: e.target.value })}
              required
            />
          </div>
          <div>
            <label>State</label>
            <input
              value={form.state}
              onChange={(e) => setForm({ ...form, state: e.target.value })}
              required
            />
          </div>
          <div>
            <label>Market</label>
            <select
              value={form.market}
              onChange={(e) => {
                const market = e.target.value;
                setForm({
                  ...form,
                  market,
                  country: market === "US" ? "United States" : "India",
                });
              }}
            >
              {markets.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label} ({m.currency})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Country</label>
            <input
              value={form.country}
              onChange={(e) => setForm({ ...form, country: e.target.value })}
              required
            />
          </div>
          <div style={{ gridColumn: "1 / -1" }}>
            <label>Address</label>
            <input
              value={form.address}
              onChange={(e) => setForm({ ...form, address: e.target.value })}
              required
            />
          </div>
          <div className="form-section" style={{ gridColumn: "1 / -1" }}>
            <h3>First tenant admin (optional)</h3>
            <div className="grid-2">
              <div>
                <label>Admin email</label>
                <input
                  type="email"
                  value={form.admin_email}
                  onChange={(e) =>
                    setForm({ ...form, admin_email: e.target.value })
                  }
                />
              </div>
              <div>
                <label>Admin password</label>
                <input
                  type="password"
                  value={form.admin_password}
                  onChange={(e) =>
                    setForm({ ...form, admin_password: e.target.value })
                  }
                  minLength={8}
                />
              </div>
              <div>
                <label>Admin first name</label>
                <input
                  value={form.admin_first_name}
                  onChange={(e) =>
                    setForm({ ...form, admin_first_name: e.target.value })
                  }
                />
              </div>
              <div>
                <label>Admin last name</label>
                <input
                  value={form.admin_last_name}
                  onChange={(e) =>
                    setForm({ ...form, admin_last_name: e.target.value })
                  }
                />
              </div>
            </div>
          </div>
          <div>
            <button type="submit">Create tenant</button>
          </div>
        </form>
      </div>
      <div className="card">
        <h2>All tenants</h2>
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Contact</th>
              <th>Location</th>
              <th>Market</th>
              <th>Vertical</th>
              <th>Theme</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {tenants.map((t) => (
              <tr key={t.id}>
                <td>{t.id}</td>
                <td>
                  <strong>{t.name}</strong>
                  <br />
                  <span className="muted" style={{ fontSize: "0.8rem" }}>
                    {t.email}
                  </span>
                </td>
                <td>{t.phone}</td>
                <td>
                  {t.city}, {t.state}
                </td>
                <td>{t.market || "IN"}</td>
                <td>{verticalLabel(t.vertical)}</td>
                <td>{t.theme || "classic"}</td>
                <td>{t.status}</td>
                <td style={{ whiteSpace: "nowrap" }}>
                  <Link href={`/tenants/${t.id}`}>Edit</Link>
                  {" · "}
                  <Link
                    href={`/tenants/${t.id}#purge`}
                    style={{ color: "var(--danger, #c62828)" }}
                  >
                    Purge
                  </Link>
                  {" · "}
                  {t.status === "ACTIVE" ? (
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => setTenantStatus(t, "INACTIVE")}
                    >
                      Deactivate
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => setTenantStatus(t, "ACTIVE")}
                    >
                      Activate
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
