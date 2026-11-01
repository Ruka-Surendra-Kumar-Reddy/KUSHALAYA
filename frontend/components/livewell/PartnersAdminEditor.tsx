"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Flash } from "@/components/Flash";
import { DEFAULT_SUPPLIER_DIRECTORY } from "@/lib/livewell/supplier-defaults";
import { fetchAdminSuppliers, saveAdminSuppliers } from "@/lib/livewell/supplierApi";
import { normalizeSupplierDirectory } from "@/lib/livewell/suppliers";
import type { PartnerRole, PartnerTier, Supplier, SupplierDirectory } from "@/lib/livewell/supplier-types";
import {
  displayPartnerRating,
  PARTNER_CATEGORIES,
  partnerRolesLabel,
  partnerTierLabel,
  MIN_RATINGS_FOR_ROLLING,
} from "@/lib/livewell/supplier-types";

function newPartnerId(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "")
    .slice(0, 24);
  return `sup_${slug || "partner"}_${Date.now().toString(36)}`;
}

function emptyPartner(sortOrder: number): Supplier {
  return {
    id: newPartnerId("New partner"),
    name: "New partner",
    contact: "",
    phone: "",
    email: "",
    city: "Hyderabad",
    rating: null,
    roles: ["installer"],
    category: "",
    partner_tier: "",
    rolling_rating: null,
    rolling_rating_count: 0,
    rolling_window: 5,
    active: true,
    sort_order: sortOrder,
  };
}

function toggleRole(roles: PartnerRole[], role: PartnerRole): PartnerRole[] {
  if (roles.includes(role)) {
    const next = roles.filter((r) => r !== role);
    return next.length ? next : ["supplier"];
  }
  return [...roles, role];
}

export function PartnersAdminEditor() {
  const [directory, setDirectory] = useState<SupplierDirectory>(DEFAULT_SUPPLIER_DIRECTORY);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [roleFilter, setRoleFilter] = useState<"all" | PartnerRole>("all");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchAdminSuppliers()
      .then(setDirectory)
      .catch(() => setDirectory(DEFAULT_SUPPLIER_DIRECTORY))
      .finally(() => setLoading(false));
  }, []);

  const normalized = useMemo(() => normalizeSupplierDirectory(directory), [directory]);

  const partners = useMemo(() => {
    return normalized.suppliers.filter((p) => {
      if (roleFilter === "all") return true;
      return p.roles.includes(roleFilter);
    });
  }, [normalized.suppliers, roleFilter]);

  function persist(next: SupplierDirectory) {
    setDirectory(normalizeSupplierDirectory(next));
  }

  function updatePartner(id: string, patch: Partial<Supplier>) {
    persist({
      ...directory,
      suppliers: directory.suppliers.map((s) => (s.id === id ? { ...s, ...patch } : s)),
    });
  }

  function addPartner() {
    persist({
      ...directory,
      suppliers: [...directory.suppliers, emptyPartner(directory.suppliers.length + 1)],
    });
  }

  function removePartner(id: string) {
    if (!window.confirm("Remove this partner? Product offers linked to them will also be removed.")) {
      return;
    }
    persist({
      suppliers: directory.suppliers.filter((s) => s.id !== id),
      offers: directory.offers.filter((o) => o.supplier_id !== id),
    });
  }

  async function save() {
    setSaving(true);
    setError("");
    try {
      const saved = await saveAdminSuppliers(normalized);
      setDirectory(saved);
      setMessage("Partners saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p>Loading partners…</p>;

  return (
    <div className="home-safety-partners-admin">
      <Flash message={message} error={error} onClear={() => { setMessage(""); setError(""); }} />

      <div className="home-safety-field-row" style={{ marginBottom: "1rem", alignItems: "center" }}>
        <label className="home-safety-field">
          Show
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value as "all" | PartnerRole)}
          >
            <option value="all">All partners</option>
            <option value="supplier">Suppliers</option>
            <option value="installer">Installers</option>
          </select>
        </label>
        <button type="button" className="secondary" onClick={addPartner}>
          Add partner
        </button>
        <button type="button" onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save partners"}
        </button>
        <Link href="/kushalaya/suppliers" className="muted">
          Product offers / costs →
        </Link>
      </div>

      <p className="muted" style={{ marginBottom: "1rem" }}>
        Partner <strong>rolling rating</strong> is the average of the last{" "}
        {partners[0]?.rolling_window ?? 5} family visit experience scores (shown once{" "}
        {MIN_RATINGS_FOR_ROLLING}+ reviews exist). Manual seed rating is used until then.
      </p>

      {partners.length === 0 ? (
        <p className="muted">No partners match this filter.</p>
      ) : (
        <div className="home-safety-suppliers-list">
          {partners.map((partner) => {
            const shown = displayPartnerRating(partner);
            return (
              <details key={partner.id} className="home-safety-supplier-card" open>
                <summary>
                  <strong>{partner.name}</strong>
                  <span className="muted"> · {partnerRolesLabel(partner.roles)}</span>
                  {partner.category ? <span className="muted"> · {partner.category}</span> : null}
                  {partner.partner_tier ? (
                    <span className="home-safety-pill home-safety-pill-neutral">
                      {partnerTierLabel(partner.partner_tier)}
                    </span>
                  ) : null}
                  {shown != null ? (
                    <span className="muted">
                      {" "}
                      · ★ {shown.toFixed(1)}
                      {partner.rolling_rating_count > 0
                        ? ` (${partner.rolling_rating_count} visit review${
                            partner.rolling_rating_count === 1 ? "" : "s"
                          })`
                        : " seed"}
                    </span>
                  ) : (
                    <span className="muted"> · No rating yet</span>
                  )}
                  {!partner.active ? <span className="muted"> (inactive)</span> : null}
                </summary>

                <div className="home-safety-field-row" style={{ marginTop: "0.75rem" }}>
                  <label className="home-safety-field">
                    Name
                    <input
                      value={partner.name}
                      onChange={(e) => updatePartner(partner.id, { name: e.target.value })}
                    />
                  </label>
                  <label className="home-safety-field">
                    City
                    <input
                      value={partner.city}
                      onChange={(e) => updatePartner(partner.id, { city: e.target.value })}
                    />
                  </label>
                  <label className="home-safety-field">
                    Category
                    <select
                      value={partner.category}
                      onChange={(e) => updatePartner(partner.id, { category: e.target.value })}
                    >
                      <option value="">—</option>
                      {PARTNER_CATEGORIES.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <div className="home-safety-field-row">
                  <fieldset className="home-safety-field" style={{ border: 0, padding: 0 }}>
                    <legend style={{ fontSize: "0.85rem", marginBottom: "0.35rem" }}>Roles</legend>
                    <label style={{ marginRight: "1rem" }}>
                      <input
                        type="checkbox"
                        checked={partner.roles.includes("supplier")}
                        onChange={() =>
                          updatePartner(partner.id, {
                            roles: toggleRole(partner.roles, "supplier"),
                          })
                        }
                      />{" "}
                      Supplier (products)
                    </label>
                    <label>
                      <input
                        type="checkbox"
                        checked={partner.roles.includes("installer")}
                        onChange={() =>
                          updatePartner(partner.id, {
                            roles: toggleRole(partner.roles, "installer"),
                          })
                        }
                      />{" "}
                      Installer (visits)
                    </label>
                  </fieldset>
                  <label className="home-safety-field">
                    Partner tier
                    <select
                      value={partner.partner_tier}
                      onChange={(e) =>
                        updatePartner(partner.id, {
                          partner_tier: e.target.value as PartnerTier,
                        })
                      }
                    >
                      <option value="">—</option>
                      <option value="founding_platinum">Founding Platinum</option>
                      <option value="gold">Gold</option>
                      <option value="silver">Silver</option>
                    </select>
                  </label>
                  <label className="home-safety-field">
                    Seed rating (0–5)
                    <input
                      type="number"
                      min={0}
                      max={5}
                      step={0.1}
                      value={partner.rating ?? ""}
                      onChange={(e) =>
                        updatePartner(partner.id, {
                          rating: e.target.value === "" ? null : Number(e.target.value),
                        })
                      }
                    />
                  </label>
                  <label className="home-safety-field">
                    Rolling window (N visits)
                    <input
                      type="number"
                      min={1}
                      max={20}
                      value={partner.rolling_window}
                      onChange={(e) =>
                        updatePartner(partner.id, {
                          rolling_window: Math.max(1, Number(e.target.value) || 5),
                        })
                      }
                    />
                  </label>
                </div>

                <div className="home-safety-field-row">
                  <label className="home-safety-field">
                    Contact
                    <input
                      value={partner.contact}
                      onChange={(e) => updatePartner(partner.id, { contact: e.target.value })}
                    />
                  </label>
                  <label className="home-safety-field">
                    Phone
                    <input
                      value={partner.phone}
                      onChange={(e) => updatePartner(partner.id, { phone: e.target.value })}
                    />
                  </label>
                  <label className="home-safety-field">
                    Email
                    <input
                      value={partner.email}
                      onChange={(e) => updatePartner(partner.id, { email: e.target.value })}
                    />
                  </label>
                  <label className="home-safety-field" style={{ display: "flex", alignItems: "end", gap: "0.5rem" }}>
                    <span>
                      <input
                        type="checkbox"
                        checked={partner.active}
                        onChange={(e) => updatePartner(partner.id, { active: e.target.checked })}
                      />{" "}
                      Active
                    </span>
                    <button type="button" className="secondary" onClick={() => removePartner(partner.id)}>
                      Remove
                    </button>
                  </label>
                </div>

                <p className="muted" style={{ fontSize: "0.85rem", marginTop: "0.5rem" }}>
                  Rolling rating:{" "}
                  {partner.rolling_rating != null
                    ? `★ ${partner.rolling_rating.toFixed(2)} from last ${partner.rolling_rating_count} review(s)`
                    : "none yet — assign this partner on visits; families rate the visit experience"}
                </p>
              </details>
            );
          })}
        </div>
      )}
    </div>
  );
}
