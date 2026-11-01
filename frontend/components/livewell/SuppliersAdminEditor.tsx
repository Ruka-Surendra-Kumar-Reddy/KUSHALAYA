"use client";

import { useEffect, useMemo, useState } from "react";
import { Flash } from "@/components/Flash";
import { DEFAULT_SAFETY_CATALOG } from "@/lib/livewell/catalog-defaults";
import { fetchAdminCatalog } from "@/lib/livewell/catalogApi";
import type { SafetyCatalog } from "@/lib/livewell/catalog-types";
import { formatInr } from "@/lib/livewell/catalog";
import { DEFAULT_SUPPLIER_DIRECTORY } from "@/lib/livewell/supplier-defaults";
import { fetchAdminSuppliers, saveAdminSuppliers } from "@/lib/livewell/supplierApi";
import { selectVendorOffer } from "@/lib/livewell/supplier-selection";
import {
  normalizeSupplierDirectory,
  resetLocalSupplierDirectory,
} from "@/lib/livewell/suppliers";
import {
  exportSupplierWorkbook,
  parseSupplierWorkbookFile,
  supplierWorkbookFilePrefix,
} from "@/lib/livewell/supplier-workbook";
import { withPublicBrand } from "@/lib/public-brand";
import type {
  ProductSupplierOffer,
  Supplier,
  SupplierDirectory,
} from "@/lib/livewell/supplier-types";

function newSupplierId(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "")
    .slice(0, 24);
  return `sup_${slug || "vendor"}_${Date.now().toString(36)}`;
}

function offerId(productId: string, supplierId: string): string {
  return `offer_${productId}_${supplierId}`;
}

export function SuppliersAdminEditor() {
  const [directory, setDirectory] = useState<SupplierDirectory>(DEFAULT_SUPPLIER_DIRECTORY);
  const [catalog, setCatalog] = useState<SafetyCatalog>(DEFAULT_SAFETY_CATALOG);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [filterProductId, setFilterProductId] = useState("");

  async function importWorkbook(file: File) {
    setError("");
    try {
      const text = await file.text();
      const imported = parseSupplierWorkbookFile(file.name, text);
      const merged = normalizeSupplierDirectory(
        {
          suppliers: [
            ...directory.suppliers,
            ...imported.suppliers.filter(
              (s) => !directory.suppliers.some((existing) => existing.id === s.id),
            ),
          ],
          offers: [
            ...directory.offers.filter(
              (o) =>
                !imported.offers.some(
                  (n) => n.product_id === o.product_id && n.supplier_id === o.supplier_id,
                ),
            ),
            ...imported.offers,
          ],
        },
        { validProductIds: new Set(catalog.products.map((p) => p.id)) },
      );
      setDirectory(merged);
      setMessage(
        `Imported ${imported.suppliers.length} vendor(s) and ${imported.offers.length} offer(s) — click Save to push to server.`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
    }
  }

  useEffect(() => {
    Promise.all([
      fetchAdminSuppliers().catch(() => DEFAULT_SUPPLIER_DIRECTORY),
      fetchAdminCatalog().catch(() => DEFAULT_SAFETY_CATALOG),
    ])
      .then(([suppliers, cat]) => {
        setDirectory(suppliers);
        setCatalog(cat);
      })
      .finally(() => setLoading(false));
  }, []);

  const normalized = useMemo(
    () =>
      normalizeSupplierDirectory(directory, {
        validProductIds: new Set(catalog.products.map((p) => p.id)),
      }),
    [directory, catalog.products],
  );

  const productById = useMemo(
    () => new Map(catalog.products.map((p) => [p.id, p])),
    [catalog.products],
  );

  const supplierById = useMemo(
    () => new Map(normalized.suppliers.map((s) => [s.id, s])),
    [normalized.suppliers],
  );

  const filteredOffers = filterProductId
    ? normalized.offers.filter((o) => o.product_id === filterProductId)
    : normalized.offers;

  function persist(next: SupplierDirectory) {
    setDirectory(
      normalizeSupplierDirectory(next, {
        validProductIds: new Set(catalog.products.map((p) => p.id)),
      }),
    );
  }

  async function saveDirectory() {
    setError("");
    try {
      const saved = await saveAdminSuppliers(normalized);
      setDirectory(saved);
      setMessage("Supplier directory saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    }
  }

  function resetDirectory() {
    if (!window.confirm("Reset suppliers to factory defaults?")) return;
    setDirectory(resetLocalSupplierDirectory());
    setMessage("Reset locally — click Save to push to server.");
  }

  function updateSupplier(id: string, patch: Partial<Supplier>) {
    persist({
      ...directory,
      suppliers: directory.suppliers.map((s) => (s.id === id ? { ...s, ...patch } : s)),
    });
  }

  function addSupplier() {
    const name = "New vendor";
    persist({
      ...directory,
      suppliers: [
        ...directory.suppliers,
        {
          id: newSupplierId(name),
          name,
          contact: "",
          phone: "",
          email: "",
          city: "",
          rating: null,
          roles: ["supplier"],
          category: "",
          partner_tier: "",
          rolling_rating: null,
          rolling_rating_count: 0,
          rolling_window: 5,
          active: true,
          sort_order: directory.suppliers.length + 1,
        },
      ],
    });
  }

  function removeSupplier(id: string) {
    if (!window.confirm("Remove this vendor and all product offers?")) return;
    persist({
      suppliers: directory.suppliers.filter((s) => s.id !== id),
      offers: directory.offers.filter((o) => o.supplier_id !== id),
    });
  }

  function updateOffer(id: string, patch: Partial<ProductSupplierOffer>) {
    persist({
      ...directory,
      offers: directory.offers.map((o) => (o.id === id ? { ...o, ...patch } : o)),
    });
  }

  function setPreferredOffer(productId: string, offerIdToPrefer: string) {
    persist({
      ...directory,
      offers: directory.offers.map((o) =>
        o.product_id === productId ? { ...o, preferred: o.id === offerIdToPrefer } : o,
      ),
    });
  }

  function addOffer() {
    const productId = filterProductId || catalog.products[0]?.id;
    const supplierId = directory.suppliers.find((s) => s.active)?.id;
    if (!productId || !supplierId) {
      setError("Add at least one vendor and ensure the catalog has products.");
      return;
    }
    if (directory.offers.some((o) => o.product_id === productId && o.supplier_id === supplierId)) {
      setError("An offer for this product and vendor already exists.");
      return;
    }
    persist({
      ...directory,
      offers: [
        ...directory.offers,
        {
          id: offerId(productId, supplierId),
          product_id: productId,
          supplier_id: supplierId,
          supplier_cost_inr: 0,
          preferred: !directory.offers.some((o) => o.product_id === productId),
          moq: 1,
          lead_time_days: 3,
          vendor_sku: "",
          active: true,
        },
      ],
    });
  }

  function removeOffer(id: string) {
    persist({ ...directory, offers: directory.offers.filter((o) => o.id !== id) });
  }

  if (loading) return <p className="muted">Loading suppliers…</p>;

  return (
    <div className="home-safety-suppliers-admin home-safety-rubric-admin">
      <Flash message={message} error={error} onClear={() => { setMessage(""); setError(""); }} />

      <p className="muted">
        Link multiple vendors to the same catalog SKU with cost, MOQ, and lead time. Customer quotes
        still use catalog sell prices; vendor selection is used for procurement and margin analysis.
      </p>

      <div className="home-safety-rubric-admin actions" style={{ marginBottom: "1rem" }}>
        <button type="button" className="primary" onClick={() => void saveDirectory()}>
          Save suppliers
        </button>
        <button type="button" className="secondary" onClick={resetDirectory}>
          Reset defaults
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() => exportSupplierWorkbook(normalized)}
        >
          Export workbook
        </button>
        <label className="secondary" style={{ display: "inline-block", cursor: "pointer" }}>
          Import workbook
          <input
            type="file"
            accept=".json,.csv"
            style={{ display: "none" }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void importWorkbook(file);
              e.target.value = "";
            }}
          />
        </label>
      </div>

      <p className="muted" style={{ marginBottom: "1rem" }}>
        Master workbook: export downloads <code>{supplierWorkbookFilePrefix()}.json</code> plus{" "}
        <code>07_Suppliers.csv</code> and <code>08_ProductSuppliers.csv</code> for Excel. Import
        accepts the JSON bundle or either CSV sheet.
      </p>

      <section className="card home-safety-solutions-section">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ marginTop: 0 }}>Vendors ({normalized.suppliers.length})</h2>
          <button type="button" className="secondary" onClick={addSupplier}>
            Add vendor
          </button>
        </div>

        {normalized.suppliers.length === 0 ? (
          <p className="muted">No vendors yet.</p>
        ) : (
          <div className="home-safety-suppliers-list">
            {normalized.suppliers.map((supplier) => (
              <details key={supplier.id} className="home-safety-supplier-card" open>
                <summary>
                  <strong>{supplier.name}</strong>
                  {!supplier.active && <span className="muted"> (inactive)</span>}
                  {supplier.city ? <span className="muted"> · {supplier.city}</span> : null}
                </summary>
                <div className="home-safety-field-row" style={{ marginTop: "0.75rem" }}>
                  <label className="home-safety-field">
                    Name
                    <input
                      value={supplier.name}
                      onChange={(e) => updateSupplier(supplier.id, { name: e.target.value })}
                    />
                  </label>
                  <label className="home-safety-field">
                    City
                    <input
                      value={supplier.city}
                      onChange={(e) => updateSupplier(supplier.id, { city: e.target.value })}
                    />
                  </label>
                  <label className="home-safety-field">
                    Rating (0–5)
                    <input
                      type="number"
                      min={0}
                      max={5}
                      step={0.1}
                      value={supplier.rating ?? ""}
                      onChange={(e) =>
                        updateSupplier(supplier.id, {
                          rating: e.target.value === "" ? null : Number(e.target.value),
                        })
                      }
                    />
                  </label>
                </div>
                <div className="home-safety-field-row">
                  <label className="home-safety-field">
                    Contact
                    <input
                      value={supplier.contact}
                      onChange={(e) => updateSupplier(supplier.id, { contact: e.target.value })}
                    />
                  </label>
                  <label className="home-safety-field">
                    Phone
                    <input
                      value={supplier.phone}
                      onChange={(e) => updateSupplier(supplier.id, { phone: e.target.value })}
                    />
                  </label>
                  <label className="home-safety-field">
                    Email
                    <input
                      type="email"
                      value={supplier.email}
                      onChange={(e) => updateSupplier(supplier.id, { email: e.target.value })}
                    />
                  </label>
                </div>
                <label className="home-safety-field" style={{ display: "inline-flex", gap: "0.5rem" }}>
                  <input
                    type="checkbox"
                    checked={supplier.active}
                    onChange={(e) => updateSupplier(supplier.id, { active: e.target.checked })}
                  />
                  Active
                </label>
                <button
                  type="button"
                  className="danger"
                  style={{ marginLeft: "1rem" }}
                  onClick={() => removeSupplier(supplier.id)}
                >
                  Remove
                </button>
              </details>
            ))}
          </div>
        )}
      </section>

      <section className="card home-safety-solutions-section" style={{ marginTop: "1.25rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.75rem" }}>
          <h2 style={{ margin: 0 }}>Product supply offers ({filteredOffers.length})</h2>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
            <label className="home-safety-field" style={{ margin: 0 }}>
              Filter product
              <select value={filterProductId} onChange={(e) => setFilterProductId(e.target.value)}>
                <option value="">All products</option>
                {catalog.products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.product_code ? `${p.product_code} — ` : ""}
                    {withPublicBrand(p.name)}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" className="secondary" onClick={addOffer}>
              Add offer
            </button>
          </div>
        </div>

        {filteredOffers.length === 0 ? (
          <p className="muted" style={{ marginTop: "0.75rem" }}>
            No product offers yet. Filter a product or add an offer linking a catalog SKU to a vendor.
          </p>
        ) : (
          <table className="table" style={{ marginTop: "0.75rem" }}>
            <thead>
              <tr>
                <th>Product</th>
                <th>Vendor</th>
                <th>Cost (₹)</th>
                <th>MOQ</th>
                <th>Lead (days)</th>
                <th>Vendor SKU</th>
                <th>Preferred</th>
                <th>Active</th>
                <th>Auto-pick</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filteredOffers.map((offer) => {
                const product = productById.get(offer.product_id);
                const supplier = supplierById.get(offer.supplier_id);
                const autoPick = selectVendorOffer(normalized, offer.product_id, { quantity: offer.moq });
                const isAuto = autoPick?.offer.id === offer.id;
                return (
                  <tr key={offer.id}>
                    <td>
                      {product?.product_code ? `${product.product_code} · ` : ""}
                      {product?.name ?? offer.product_id}
                    </td>
                    <td>{supplier?.name ?? offer.supplier_id}</td>
                    <td>
                      <input
                        type="number"
                        min={0}
                        style={{ width: "6rem" }}
                        value={offer.supplier_cost_inr}
                        onChange={(e) =>
                          updateOffer(offer.id, { supplier_cost_inr: Number(e.target.value) })
                        }
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        min={1}
                        style={{ width: "4rem" }}
                        value={offer.moq}
                        onChange={(e) => updateOffer(offer.id, { moq: Number(e.target.value) })}
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        min={0}
                        style={{ width: "4rem" }}
                        value={offer.lead_time_days}
                        onChange={(e) =>
                          updateOffer(offer.id, { lead_time_days: Number(e.target.value) })
                        }
                      />
                    </td>
                    <td>
                      <input
                        value={offer.vendor_sku}
                        onChange={(e) => updateOffer(offer.id, { vendor_sku: e.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        type="radio"
                        name={`preferred-${offer.product_id}`}
                        checked={offer.preferred}
                        onChange={() => setPreferredOffer(offer.product_id, offer.id)}
                      />
                    </td>
                    <td>
                      <input
                        type="checkbox"
                        checked={offer.active}
                        onChange={(e) => updateOffer(offer.id, { active: e.target.checked })}
                      />
                    </td>
                    <td className="muted" style={{ fontSize: "0.85rem" }}>
                      {isAuto ? `✓ ${autoPick?.reason}` : "—"}
                      {offer.supplier_cost_inr > 0 ? (
                        <div>{formatInr(offer.supplier_cost_inr, "")}</div>
                      ) : null}
                    </td>
                    <td>
                      <button type="button" className="danger" onClick={() => removeOffer(offer.id)}>
                        Remove
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
